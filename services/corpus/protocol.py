"""The corpus provider contract (ADR-0019).

Adding a corpus means implementing this protocol. Nothing in the engine, the
normalisation rules, the tiering, or the holdout logic changes.

Duties are split deliberately:

* **Provider** — acquire (network, auth, pagination), extract (unzip, parse,
  stream), map to ``CorpusRecord``, and apply *source-specific* filtering
  (e.g. USPTO's standard-character mark drawing code).
* **Pipeline** — universal structural rules, tagging, deduplication,
  saturation aggregation, tiering, blending.

A provider that reaches for phonotactics or induction has taken on the
pipeline's job and should be reviewed as a design change, not merged.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from services.corpus.types import CorpusRecord, ProviderDescriptor


@dataclass(frozen=True, slots=True)
class Snapshot:
    """An immutable, content-addressed acquisition.

    Every stage downstream reads a snapshot rather than the network, so any
    stage can be re-run without re-downloading gigabytes — and a corpus can be
    rebuilt years later from the exact bytes that produced it.
    """

    provider_id: str
    content_hash: str
    location: Path
    byte_size: int
    vintage: str
    """Source-declared edition (e.g. '2023'), not the acquisition date."""


@runtime_checkable
class CorpusProvider(Protocol):
    """A source of brand-name evidence."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """Static declaration of what this source is. Must be constant."""
        ...

    def acquire(self, destination: Path) -> Snapshot:
        """Fetch the source to ``destination`` and return a content-addressed snapshot.

        Implementations must verify integrity before returning — at minimum a
        size comparison against the previous snapshot, refusing an unexplained
        shrink. A truncated download produces a corpus that is quietly wrong
        rather than one that fails, which is the worse outcome by far.
        """
        ...

    def extract(self, snapshot: Snapshot) -> Iterator[CorpusRecord]:
        """Stream records from a snapshot.

        Streaming, not materialising: registry sources run to millions of rows.
        Source-specific filtering belongs here. Malformed records are
        quarantined by the caller, never silently dropped.
        """
        ...
