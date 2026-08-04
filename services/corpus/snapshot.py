"""Snapshot integrity and the truncation guard.

A truncated download is the worst failure available to an ingestion pipeline:
it does not raise, it does not log, and it produces a corpus that is quietly
smaller than it should be. Every downstream metric still computes, and every
one of them is wrong.

The defence is a size comparison against the previous snapshot. It is the same
lesson as the zone-file ingest (docs/ops/zone-file-access.md §5): refuse a
shrink you cannot explain, rather than trusting that a completed HTTP response
means complete data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from services.corpus.errors import SnapshotValidationError
from services.corpus.protocol import Snapshot

#: How much a source may legitimately shrink between editions before we refuse
#: it. Registers do shrink slightly as dead records are purged; they do not
#: halve. Conservative on purpose — a false alarm costs a conversation, a
#: missed truncation costs a silently wrong corpus.
DEFAULT_SHRINK_TOLERANCE: Final[float] = 0.10

_HASH_CHUNK: Final[int] = 1 << 20


def compute_content_hash(path: Path) -> str:
    """Stream a SHA-256 over the file. Streamed because sources run to gigabytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def verify_integrity(snapshot: Snapshot) -> None:
    """Assert the file on disk is what the snapshot claims."""
    if not snapshot.location.exists():
        msg = f"{snapshot.provider_id}: snapshot file missing at {snapshot.location}"
        raise SnapshotValidationError(msg)

    actual_size = snapshot.location.stat().st_size
    if actual_size != snapshot.byte_size:
        msg = (
            f"{snapshot.provider_id}: size mismatch — snapshot declares "
            f"{snapshot.byte_size} bytes, file is {actual_size}"
        )
        raise SnapshotValidationError(msg)

    actual_hash = compute_content_hash(snapshot.location)
    if actual_hash != snapshot.content_hash:
        msg = (
            f"{snapshot.provider_id}: content hash mismatch — declared "
            f"{snapshot.content_hash}, computed {actual_hash}"
        )
        raise SnapshotValidationError(msg)


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """A previously accepted snapshot, for comparison against the next one."""

    provider_id: str
    content_hash: str
    byte_size: int
    vintage: str
    recorded_at: str

    @classmethod
    def of(cls, snapshot: Snapshot) -> SnapshotRecord:
        return cls(
            provider_id=snapshot.provider_id,
            content_hash=snapshot.content_hash,
            byte_size=snapshot.byte_size,
            vintage=snapshot.vintage,
            recorded_at=datetime.now(UTC).isoformat(),
        )


def validate_against_previous(
    snapshot: Snapshot,
    previous: SnapshotRecord | None,
    tolerance: float = DEFAULT_SHRINK_TOLERANCE,
) -> None:
    """Refuse a snapshot that shrank more than ``tolerance`` since last time.

    A first snapshot has nothing to compare against and is accepted — the guard
    protects against *regression*, and cannot detect a first download that was
    truncated. That limitation is real; the row-count assertion at validation
    time is what covers it.
    """
    if previous is None:
        return

    floor = previous.byte_size * (1.0 - tolerance)
    if snapshot.byte_size < floor:
        shrink = 1.0 - (snapshot.byte_size / previous.byte_size)
        msg = (
            f"{snapshot.provider_id}: snapshot shrank {shrink:.1%} "
            f"({previous.byte_size} → {snapshot.byte_size} bytes), exceeding the "
            f"{tolerance:.0%} tolerance.\n"
            f"A truncated download produces a corpus that is quietly wrong rather "
            f"than one that fails. Re-download and verify before overriding."
        )
        raise SnapshotValidationError(msg)


class SnapshotLedger:
    """Append-only record of accepted snapshots, one entry per acquisition."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        payload: object = json.loads(self.path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def latest(self, provider_id: str) -> SnapshotRecord | None:
        entries = [e for e in self._load() if e.get("provider_id") == provider_id]
        return SnapshotRecord(**entries[-1]) if entries else None

    def record(self, snapshot: Snapshot) -> SnapshotRecord:
        entry = SnapshotRecord.of(snapshot)
        entries = [*self._load(), asdict(entry)]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        return entry

    def accept(
        self, snapshot: Snapshot, tolerance: float = DEFAULT_SHRINK_TOLERANCE
    ) -> SnapshotRecord:
        """Verify, compare against history, and record. Raises rather than warns."""
        verify_integrity(snapshot)
        validate_against_previous(snapshot, self.latest(snapshot.provider_id), tolerance)
        return self.record(snapshot)
