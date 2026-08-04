"""Universal normalisation shared by every provider.

Governing principle — **normalisation tags; it does not silently discard.**

Only *structural* rejects remove a record: cases where it cannot contribute to
phonotactic induction at all. Every judgement call (dictionary word, acronym,
profanity) becomes a tag, so induction can weight or exclude it and we can
change our minds without re-ingesting. Discarding at this stage destroys
information irreversibly and hides the decision from everyone downstream.

Source-specific filtering (USPTO's mark drawing code, for instance) belongs in
the provider, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from enum import StrEnum, unique
from typing import Final

from services.corpus.types import CorpusRecord, NameStatus, Tag

MIN_LENGTH: Final[int] = 3
MAX_LENGTH: Final[int] = 16

#: Whole-mark filing artifacts. Only rejected when they constitute the *entire*
#: name — "INC" is noise, "INCEPTION" is a brand.
LEGAL_ENTITY_TOKENS: Final[frozenset[str]] = frozenset(
    {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "sa", "bv", "ag", "nv", "srl", "oy", "ab"}
)

VOWELS: Final[frozenset[str]] = frozenset("aeiouy")


@unique
class RejectionRule(StrEnum):
    """Why a record was structurally rejected. Recorded so the funnel is measurable."""

    EMPTY_TEXT = "empty_text"
    MULTI_TOKEN = "multi_token"  # noqa: S105 — a rejection reason, not a credential
    NON_ALPHABETIC = "non_alphabetic"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    LEGAL_ENTITY_ARTIFACT = "legal_entity_artifact"


@dataclass(frozen=True, slots=True)
class Rejection:
    rule: RejectionRule
    detail: str
    provider_id: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class NormalisedRecord:
    normalized: str
    display: str
    provider_id: str
    source_ref: str
    status: NameStatus
    tags: frozenset[Tag]
    categories: tuple[str, ...]
    first_seen_year: int | None


@dataclass(frozen=True, slots=True)
class Lexicons:
    """Injected reference data.

    Passed in rather than loaded here so normalisation stays a pure function of
    its inputs and is trivially testable with small fixtures.
    """

    dictionary: AbstractSet[str] = frozenset()
    profanity: AbstractSet[str] = frozenset()


#: Structural rules in cheapest-first order, so expensive checks only ever see
#: survivors. A table rather than a chain of early returns: adding a rule is a
#: one-line change, and the funnel's shape stays readable as it grows.
_STRUCTURAL_RULES: Final[tuple[tuple[RejectionRule, Callable[[str, str], bool]], ...]] = (
    (RejectionRule.EMPTY_TEXT, lambda raw, _: not raw),
    # Multi-word marks teach syntax, not brand phonotactics.
    (RejectionRule.MULTI_TOKEN, lambda raw, _: len(raw.split()) > 1),
    # Digits and punctuation pollute the character n-gram model; non-Latin
    # scripts are a different phonotactic system entirely.
    (RejectionRule.NON_ALPHABETIC, lambda raw, _: not (raw.isascii() and raw.isalpha())),
    (RejectionRule.TOO_SHORT, lambda raw, _: len(raw) < MIN_LENGTH),
    (RejectionRule.TOO_LONG, lambda raw, _: len(raw) > MAX_LENGTH),
    # Only when the token IS the whole name: "INC" is noise, "INCEPTION" is a brand.
    (RejectionRule.LEGAL_ENTITY_ARTIFACT, lambda _, norm: norm in LEGAL_ENTITY_TOKENS),
)


def _is_probable_acronym(text: str) -> bool:
    """Heuristic: no vowel at all, or short and vowel-free.

    Acronyms are a distinct naming strategy with distinct phonotactics, so they
    are tagged rather than rejected — induction decides what to do with them.
    """
    return not (set(text) & VOWELS)


def normalise(
    record: CorpusRecord, lexicons: Lexicons | None = None
) -> NormalisedRecord | Rejection:
    """Apply the universal structural rules and tags to one record.

    Rules run cheapest-first so expensive checks only ever see survivors.
    """
    lex = lexicons or Lexicons()
    raw = record.text.strip()
    normalized = raw.casefold()

    for rule, fails in _STRUCTURAL_RULES:
        if fails(raw, normalized):
            return Rejection(rule, raw or "<empty>", record.provider_id, record.source_ref)

    tags: set[Tag] = set()
    if normalized in lex.dictionary:
        tags.add(Tag.DICTIONARY_WORD)
    if normalized in lex.profanity:
        tags.add(Tag.PROFANITY_SIGNAL)
    if _is_probable_acronym(normalized):
        tags.add(Tag.PROBABLE_ACRONYM)
    if record.status is NameStatus.LIVE:
        tags.add(Tag.LIVE_REGISTRATION)
    elif record.status is NameStatus.DEAD:
        tags.add(Tag.ABANDONED)
    if record.source_fields.get("international_registration"):
        tags.add(Tag.INTERNATIONAL_REGISTRATION)

    return NormalisedRecord(
        normalized=normalized,
        display=raw,
        provider_id=record.provider_id,
        source_ref=record.source_ref,
        status=record.status,
        tags=frozenset(tags),
        categories=record.categories,
        first_seen_year=record.first_seen_year,
    )


@dataclass(frozen=True, slots=True)
class ProviderCounts:
    count: int = 0
    live: int = 0
    dead: int = 0
    earliest_year: int | None = None


@dataclass(frozen=True, slots=True)
class AggregatedName:
    """One distinct name with per-provider evidence.

    Deduplication **aggregates**; it does not discard. ``count`` is the
    saturation input — a mark text registered 300 times is exhausted, one
    registered once is not. Collapsing to a distinct set would delete exactly
    the signal we most need.

    Counts stay per-provider because "registered 300 times at USPTO" and
    "300 GitHub organisations" are different facts and must not be summed.
    """

    normalized: str
    display: str
    per_provider: dict[str, ProviderCounts]
    tags: frozenset[Tag]
    categories: frozenset[str]

    @property
    def convergent_provider_count(self) -> int:
        """Independent sources carrying this name — a weak quality signal."""
        return len(self.per_provider)

    @property
    def total_count(self) -> int:
        return sum(c.count for c in self.per_provider.values())


def aggregate(records: list[NormalisedRecord]) -> dict[str, AggregatedName]:
    """Collapse normalised records to distinct names, preserving evidence."""
    out: dict[str, AggregatedName] = {}

    for rec in records:
        existing = out.get(rec.normalized)
        if existing is None:
            existing = AggregatedName(
                normalized=rec.normalized,
                display=rec.display,
                per_provider={},
                tags=frozenset(),
                categories=frozenset(),
            )

        prev = existing.per_provider.get(rec.provider_id, ProviderCounts())
        earliest = min(
            (y for y in (prev.earliest_year, rec.first_seen_year) if y is not None),
            default=None,
        )
        updated = ProviderCounts(
            count=prev.count + 1,
            live=prev.live + (rec.status is NameStatus.LIVE),
            dead=prev.dead + (rec.status is NameStatus.DEAD),
            earliest_year=earliest,
        )

        out[rec.normalized] = replace(
            existing,
            per_provider={**existing.per_provider, rec.provider_id: updated},
            tags=existing.tags | rec.tags,
            categories=existing.categories | frozenset(rec.categories),
        )

    return out
