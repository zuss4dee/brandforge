"""Canonical corpus types shared by every provider (ADR-0019).

The shapes here are deliberately small. A provider knows about *its source*;
it knows nothing about phonotactics, tiers, or induction. Anything a provider
knows that this common shape cannot hold goes in ``source_fields`` — retained
rather than discarded, because normalisation tags rather than discards.

Frozen slotted dataclasses rather than Pydantic models: these types sit on the
hot path for millions of rows per ingest, where per-record validation cost is
real. Pydantic remains the canonical choice at API boundaries (ADR-0004).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, unique
from typing import Any, Final

MIN_TRUST_TIER: Final[int] = 1
MAX_TRUST_TIER: Final[int] = 4


@unique
class ProviderKind(StrEnum):
    """What *kind* of source this is — determines how it may be weighted.

    These are not interchangeable. A registry is exhaustive and mostly
    unremarkable; a curated source is small, high-signal and survivorship-biased.
    Blending them by row count lets ~8M registry rows outvote ~5k curated names
    roughly 1600:1, so adding the better source would dilute rather than improve.
    """

    REGISTRY = "registry"
    CURATED = "curated"
    USAGE = "usage"
    INTERNAL = "internal"


@unique
class LicenceClass(StrEnum):
    """Legal basis for use. Drives permitted uses mechanically — see licensing.py.

    ``UNKNOWN`` is the default for a reason: a provider whose licence has not
    been established must contribute to nothing, loudly, rather than defaulting
    into induction quietly.
    """

    PUBLIC_DOMAIN = "public_domain"
    OPEN_ATTRIBUTION = "open_attribution"
    COMMERCIAL_LICENSED = "commercial_licensed"
    TOS_RESTRICTED = "tos_restricted"
    INTERNAL_GENERATED = "internal_generated"
    UNKNOWN = "unknown"


@unique
class Use(StrEnum):
    """What a corpus record may be used for."""

    INDUCTION = "induction"
    """Feeds phonotactic weights, templates, typicality. The gated one."""

    SATURATION = "saturation"
    NOVELTY_REFERENCE = "novelty_reference"
    EVALUATION = "evaluation"
    DISPLAY = "display"


@unique
class NameStatus(StrEnum):
    LIVE = "live"
    DEAD = "dead"
    UNKNOWN = "unknown"


@unique
class Tag(StrEnum):
    """Non-structural observations. Never a reason to discard a record."""

    DICTIONARY_WORD = "dictionary_word"
    PROBABLE_ACRONYM = "probable_acronym"
    LIVE_REGISTRATION = "live_registration"
    ABANDONED = "abandoned"
    INTERNATIONAL_REGISTRATION = "international_registration"
    PROFANITY_SIGNAL = "profanity_signal"


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Static declaration of what a source is.

    ``licence`` and ``kind`` are the load-bearing fields: the first gates use,
    the second informs blending weight. Everything else is metadata.
    """

    id: str
    name: str
    kind: ProviderKind
    licence: LicenceClass
    jurisdiction: str | None = None
    locale: str | None = None
    cadence: str | None = None
    expected_scale: int | None = None
    trust_tier: int = 4
    attribution_required: bool = False
    attribution: str | None = None

    def __post_init__(self) -> None:
        if not self.id or " " in self.id:
            msg = f"provider id must be non-empty and space-free, got {self.id!r}"
            raise ValueError(msg)
        if not MIN_TRUST_TIER <= self.trust_tier <= MAX_TRUST_TIER:
            msg = f"trust_tier must be {MIN_TRUST_TIER}..{MAX_TRUST_TIER}, got {self.trust_tier}"
            raise ValueError(msg)
        if self.attribution_required and not self.attribution:
            msg = f"{self.id}: attribution_required is set but no attribution text given"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    """One name as published by one source, before normalisation."""

    text: str
    provider_id: str
    source_ref: str
    status: NameStatus = NameStatus.UNKNOWN
    first_seen_year: int | None = None
    categories: tuple[str, ...] = ()
    source_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BlendEntry:
    """One provider's contribution to a blend."""

    provider_id: str
    roles: frozenset[Use]
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.weight <= 0:
            msg = f"{self.provider_id}: blend weight must be positive, got {self.weight}"
            raise ValueError(msg)
        if not self.roles:
            msg = f"{self.provider_id}: blend entry declares no roles"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CorpusBlend:
    """How sources combine — a reviewable artifact, not a constant in a script.

    Changing a blend changes induced weights, which under ADR-0017 mints a new
    address space rather than mutating the current one.
    """

    blend_id: str
    entries: tuple[BlendEntry, ...]

    def entry_for(self, provider_id: str) -> BlendEntry | None:
        return next((e for e in self.entries if e.provider_id == provider_id), None)

    def providers_for(self, use: Use) -> tuple[str, ...]:
        return tuple(e.provider_id for e in self.entries if use in e.roles)
