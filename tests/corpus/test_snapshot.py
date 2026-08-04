"""Snapshot integrity and the truncation guard.

A truncated download does not raise and does not log. It produces a corpus that
is quietly smaller than it should be, with every downstream metric still
computing and every one of them wrong. These tests are the only thing that
notices.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.corpus.errors import SnapshotValidationError
from services.corpus.protocol import Snapshot
from services.corpus.snapshot import (
    SnapshotLedger,
    compute_content_hash,
    validate_against_previous,
    verify_integrity,
)


def make_snapshot(path: Path, payload: bytes, provider: str = "p") -> Snapshot:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return Snapshot(
        provider_id=provider,
        content_hash=compute_content_hash(path),
        location=path,
        byte_size=len(payload),
        vintage="2023",
    )


# ── integrity ────────────────────────────────────────────────────────────────


def test_valid_snapshot_passes(tmp_path: Path) -> None:
    verify_integrity(make_snapshot(tmp_path / "a.dat", b"x" * 1000))


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    snap = Snapshot("p", "sha256:0", tmp_path / "gone.dat", 10, "2023")
    with pytest.raises(SnapshotValidationError, match="missing"):
        verify_integrity(snap)


def test_size_mismatch_is_rejected(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path / "a.dat", b"x" * 1000)
    tampered = Snapshot("p", snap.content_hash, snap.location, 999, "2023")
    with pytest.raises(SnapshotValidationError, match="size mismatch"):
        verify_integrity(tampered)


def test_content_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path / "a.dat", b"x" * 1000)
    tampered = Snapshot("p", "sha256:deadbeef", snap.location, snap.byte_size, "2023")
    with pytest.raises(SnapshotValidationError, match="content hash mismatch"):
        verify_integrity(tampered)


def test_hash_is_stable_and_content_sensitive(tmp_path: Path) -> None:
    a = make_snapshot(tmp_path / "a.dat", b"identical")
    b = make_snapshot(tmp_path / "b.dat", b"identical")
    c = make_snapshot(tmp_path / "c.dat", b"different")
    assert a.content_hash == b.content_hash
    assert a.content_hash != c.content_hash


# ── the truncation guard ─────────────────────────────────────────────────────


def test_truncated_snapshot_is_refused(tmp_path: Path) -> None:
    """The failure this whole module exists for."""
    previous = SnapshotLedger(tmp_path / "ledger.json").record(
        make_snapshot(tmp_path / "full.dat", b"x" * 10_000)
    )
    truncated = make_snapshot(tmp_path / "trunc.dat", b"x" * 4_000)

    with pytest.raises(SnapshotValidationError, match="shrank"):
        validate_against_previous(truncated, previous)


def test_small_shrink_within_tolerance_is_accepted(tmp_path: Path) -> None:
    """Registers do shrink slightly as dead records are purged."""
    previous = SnapshotLedger(tmp_path / "l.json").record(
        make_snapshot(tmp_path / "a.dat", b"x" * 10_000)
    )
    validate_against_previous(make_snapshot(tmp_path / "b.dat", b"x" * 9_500), previous)


def test_growth_is_always_accepted(tmp_path: Path) -> None:
    previous = SnapshotLedger(tmp_path / "l.json").record(
        make_snapshot(tmp_path / "a.dat", b"x" * 10_000)
    )
    validate_against_previous(make_snapshot(tmp_path / "b.dat", b"x" * 50_000), previous)


def test_first_snapshot_has_nothing_to_compare_against(tmp_path: Path) -> None:
    validate_against_previous(make_snapshot(tmp_path / "a.dat", b"x" * 10), None)


def test_tolerance_is_configurable(tmp_path: Path) -> None:
    previous = SnapshotLedger(tmp_path / "l.json").record(
        make_snapshot(tmp_path / "a.dat", b"x" * 10_000)
    )
    shrunk = make_snapshot(tmp_path / "b.dat", b"x" * 8_000)
    validate_against_previous(shrunk, previous, tolerance=0.50)
    with pytest.raises(SnapshotValidationError):
        validate_against_previous(shrunk, previous, tolerance=0.05)


# ── ledger ───────────────────────────────────────────────────────────────────


def test_ledger_returns_the_most_recent_entry_per_provider(tmp_path: Path) -> None:
    ledger = SnapshotLedger(tmp_path / "ledger.json")
    ledger.record(make_snapshot(tmp_path / "a.dat", b"a" * 100, provider="alpha"))
    ledger.record(make_snapshot(tmp_path / "b.dat", b"b" * 200, provider="beta"))
    ledger.record(make_snapshot(tmp_path / "c.dat", b"a" * 300, provider="alpha"))

    latest = ledger.latest("alpha")
    assert latest is not None and latest.byte_size == 300
    beta = ledger.latest("beta")
    assert beta is not None and beta.byte_size == 200


def test_ledger_is_empty_before_first_record(tmp_path: Path) -> None:
    assert SnapshotLedger(tmp_path / "none.json").latest("p") is None


def test_accept_verifies_compares_and_records(tmp_path: Path) -> None:
    ledger = SnapshotLedger(tmp_path / "ledger.json")
    ledger.accept(make_snapshot(tmp_path / "a.dat", b"x" * 10_000))

    with pytest.raises(SnapshotValidationError, match="shrank"):
        ledger.accept(make_snapshot(tmp_path / "b.dat", b"x" * 100))

    latest = ledger.latest("p")
    assert latest is not None and latest.byte_size == 10_000, "rejected snapshot must not record"
