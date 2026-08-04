"""In-memory provider used to prove the abstraction (ADR-0019 §4).

An interface validated against one implementation is a guess. This provider
exists so the full pipeline runs in CI with **no network and no API key**, and
so USPTO-specific assumptions are forced out before they become load-bearing.

It is the same trick as the toy language pack in the engine design, for the
same reason: an abstraction with one instance is USPTO with extra indirection.

Its descriptor is deliberately a different ``kind`` and ``LicenceClass`` from
the USPTO provider, so blending and licence gating are both exercised.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from pathlib import Path

from services.corpus.protocol import Snapshot
from services.corpus.types import (
    CorpusRecord,
    LicenceClass,
    NameStatus,
    ProviderDescriptor,
    ProviderKind,
)

DEFAULT_NAMES: tuple[tuple[str, NameStatus], ...] = (
    ("Corvane", NameStatus.LIVE),
    ("Lumeris", NameStatus.LIVE),
    ("Zeprix", NameStatus.DEAD),
    ("Ondara", NameStatus.LIVE),
    ("SOFT DRINKS", NameStatus.LIVE),  # rejected: multi-token
    ("3M", NameStatus.LIVE),  # rejected: non-alphabetic
    ("XY", NameStatus.LIVE),  # rejected: too short
    ("INC", NameStatus.DEAD),  # rejected: legal-entity artifact
)


class FakeProvider:
    """A tiny curated source. Satisfies :class:`CorpusProvider` structurally."""

    def __init__(
        self,
        provider_id: str = "fake.curated",
        licence: LicenceClass = LicenceClass.OPEN_ATTRIBUTION,
        kind: ProviderKind = ProviderKind.CURATED,
        names: Sequence[tuple[str, NameStatus]] = DEFAULT_NAMES,
    ) -> None:
        self._names = tuple(names)
        self._descriptor = ProviderDescriptor(
            id=provider_id,
            name="Fake curated corpus (test fixture)",
            kind=kind,
            licence=licence,
            locale="en-US",
            cadence="static",
            expected_scale=len(self._names),
            trust_tier=1,
            attribution_required=licence is LicenceClass.OPEN_ATTRIBUTION,
            attribution="BrandForge test fixture"
            if licence is LicenceClass.OPEN_ATTRIBUTION
            else None,
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def acquire(self, destination: Path) -> Snapshot:
        """Write the fixture to disk so the snapshot contract is genuinely exercised."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(f"{n}\t{s.value}" for n, s in self._names).encode("utf-8")
        destination.write_bytes(payload)
        return Snapshot(
            provider_id=self._descriptor.id,
            content_hash=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            location=destination,
            byte_size=len(payload),
            vintage="static",
        )

    def extract(self, snapshot: Snapshot) -> Iterator[CorpusRecord]:
        for line in snapshot.location.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            text, status = line.split("\t")
            yield CorpusRecord(
                text=text,
                provider_id=self._descriptor.id,
                source_ref=text.casefold(),
                status=NameStatus(status),
                first_seen_year=2020,
            )
