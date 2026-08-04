"""Corpus pipeline orchestration: snapshot → extract → normalise → aggregate.

The ``land`` stage (typed Parquet) is deliberately absent. It is coupled to
``acquire``: both need real data, and neither can be written honestly until a
USPTO API key exists. See docs/ai/blocked.md.

Guards are enforced here at build time *and* independently by
``tools/check_corpus.py`` against the persisted artifact. That is the same
check at two points, not duplication — ADR-0019 requires the guard to operate
on the artifact rather than on intent, because an artifact cannot be reasoned
about after the fact from the code that wrote it.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.corpus.errors import ArtifactSchemaError, AutophagyError
from services.corpus.holdout import HoldoutIndex
from services.corpus.licensing import require
from services.corpus.normalise import (
    AggregatedName,
    Lexicons,
    NormalisedRecord,
    Rejection,
    aggregate,
    normalise,
)
from services.corpus.protocol import CorpusProvider, Snapshot
from services.corpus.types import CorpusBlend, ProviderDescriptor, ProviderKind, Use

ARTIFACT_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class FunnelReport:
    """Row counts at every stage, so the funnel is measurable rather than assumed."""

    provider_id: str
    extracted: int
    accepted: int
    distinct: int
    rejected: dict[str, int] = field(default_factory=dict)

    @property
    def rejected_total(self) -> int:
        return sum(self.rejected.values())

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.extracted if self.extracted else 0.0

    def render(self) -> str:
        lines = [
            f"{self.provider_id}",
            f"  extracted : {self.extracted:>10,}",
            f"  accepted  : {self.accepted:>10,}  ({self.acceptance_rate:.1%})",
            f"  distinct  : {self.distinct:>10,}",
            f"  rejected  : {self.rejected_total:>10,}",
        ]
        lines.extend(
            f"      {rule:<24} {count:>10,}"
            for rule, count in sorted(self.rejected.items(), key=lambda kv: -kv[1])
        )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ProviderResult:
    descriptor: ProviderDescriptor
    report: FunnelReport
    names: dict[str, AggregatedName]


def ingest(
    provider: CorpusProvider, snapshot: Snapshot, lexicons: Lexicons | None = None
) -> ProviderResult:
    """Extract, normalise and aggregate one provider's snapshot."""
    accepted: list[NormalisedRecord] = []
    rejected: Counter[str] = Counter()
    extracted = 0

    for record in provider.extract(snapshot):
        extracted += 1
        outcome = normalise(record, lexicons)
        if isinstance(outcome, Rejection):
            rejected[outcome.rule.value] += 1
        else:
            accepted.append(outcome)

    names = aggregate(accepted)
    return ProviderResult(
        descriptor=provider.descriptor,
        report=FunnelReport(
            provider_id=provider.descriptor.id,
            extracted=extracted,
            accepted=len(accepted),
            distinct=len(names),
            rejected=dict(rejected),
        ),
        names=names,
    )


@dataclass(frozen=True, slots=True)
class CorpusArtifact:
    """A named, content-addressed corpus built for one declared use.

    TODO(BF-001): this materialises the full name list as a JSON array. At the
    projected 2-4M Tier-A marks that is roughly a 50MB file, held entirely in
    memory here, again in ``from_path``, and again per artifact in
    ``tools/check_corpus``. Accepted technical debt for M1.0 — the fake
    provider emits eight names. It will not survive real data, and the guard
    needs a streaming read path, which is *not* covered by the deferred Parquet
    ``land`` stage. See docs/ai/backlog.md#bf-001.
    """

    artifact_id: str
    use: Use
    blend_id: str
    provider_ids: tuple[str, ...]
    names: tuple[str, ...]
    excluded_by_holdout: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "schema": ARTIFACT_SCHEMA,
                    "artifact_id": self.artifact_id,
                    "use": self.use.value,
                    "blend_id": self.blend_id,
                    "provider_ids": list(self.provider_ids),
                    "excluded_by_holdout": self.excluded_by_holdout,
                    "names": list(self.names),
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def from_path(cls, path: Path) -> CorpusArtifact:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != ARTIFACT_SCHEMA:
            msg = f"{path}: unsupported artifact schema {payload.get('schema')!r}"
            raise ArtifactSchemaError(msg)
        return cls(
            artifact_id=payload["artifact_id"],
            use=Use(payload["use"]),
            blend_id=payload["blend_id"],
            provider_ids=tuple(payload["provider_ids"]),
            names=tuple(payload["names"]),
            excluded_by_holdout=payload.get("excluded_by_holdout", {}),
        )


def _artifact_id(use: Use, blend_id: str, names: tuple[str, ...]) -> str:
    material = f"{use.value}|{blend_id}|{'|'.join(names)}".encode()
    return f"sha256:{hashlib.sha256(material).hexdigest()[:32]}"


def build_artifact(
    use: Use,
    blend: CorpusBlend,
    results: list[ProviderResult],
    holdout: HoldoutIndex | None = None,
) -> CorpusArtifact:
    """Combine provider results into an artifact for one declared use.

    Enforces, in order:

    1. **The licence gate** — every contributing provider must be permitted
       this use. ``unknown`` permits nothing, so an unestablished licence fails
       here rather than defaulting into the corpus.
    2. **The autophagy gate** — no internal provider may feed induction.
    3. **Holdout exclusion** — only for induction artifacts, across the
       *blended* set. Per-provider checks would let each source pass
       individually while the blend is contaminated.
    """
    contributing = [
        r for r in results if use in (e.roles if (e := blend.entry_for(r.descriptor.id)) else set())
    ]

    for result in contributing:
        require(result.descriptor, use)

        if use is Use.INDUCTION and result.descriptor.kind is ProviderKind.INTERNAL:
            msg = (
                f"{result.descriptor.id!r} is an internal provider and may never feed "
                f"induction. Inducing on our own output amplifies our own priors — it "
                f"presents as rising typicality and falling diversity, which reads like "
                f"improvement. See docs/adr/0019-corpus-provider-abstraction.md"
            )
            raise AutophagyError(msg)

    merged: set[str] = set()
    for result in contributing:
        merged |= set(result.names)

    excluded: Counter[str] = Counter()
    if holdout is not None and use is Use.INDUCTION:
        clean: set[str] = set()
        for name in merged:
            key = holdout.contamination_key(name)
            if key is None:
                clean.add(name)
            else:
                excluded[key] += 1
        merged = clean

    names = tuple(sorted(merged))
    return CorpusArtifact(
        artifact_id=_artifact_id(use, blend.blend_id, names),
        use=use,
        blend_id=blend.blend_id,
        provider_ids=tuple(sorted(r.descriptor.id for r in contributing)),
        names=names,
        excluded_by_holdout=dict(excluded),
    )
