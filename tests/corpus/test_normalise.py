"""Normalisation and aggregation tests.

The governing principle under test: normalisation *tags*, it does not silently
discard. Only structural rejects remove a record; every judgement call must
survive as a tag so induction can decide later.
"""

from __future__ import annotations

import pytest

from services.corpus.normalise import (
    Lexicons,
    NormalisedRecord,
    Rejection,
    RejectionRule,
    aggregate,
    normalise,
)
from services.corpus.types import CorpusRecord, NameStatus, Tag


def record(text: str, status: NameStatus = NameStatus.LIVE, **kw: object) -> CorpusRecord:
    return CorpusRecord(
        text=text,
        provider_id=kw.pop("provider_id", "test"),  # type: ignore[arg-type]
        source_ref=kw.pop("source_ref", "ref-1"),  # type: ignore[arg-type]
        status=status,
        **kw,  # type: ignore[arg-type]
    )


def accepted(text: str, **kw: object) -> NormalisedRecord:
    result = normalise(record(text, **kw))  # type: ignore[arg-type]
    assert isinstance(result, NormalisedRecord), f"{text!r} was rejected: {result}"
    return result


# ── structural rejects ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("", RejectionRule.EMPTY_TEXT),
        ("   ", RejectionRule.EMPTY_TEXT),
        ("SOFT DRINKS", RejectionRule.MULTI_TOKEN),
        ("3M", RejectionRule.NON_ALPHABETIC),
        ("E*TRADE", RejectionRule.NON_ALPHABETIC),
        ("CAFÉ", RejectionRule.NON_ALPHABETIC),
        ("XY", RejectionRule.TOO_SHORT),
        ("SUPERCALIFRAGILISTIC", RejectionRule.TOO_LONG),
        ("INC", RejectionRule.LEGAL_ENTITY_ARTIFACT),
        ("LLC", RejectionRule.LEGAL_ENTITY_ARTIFACT),
    ],
)
def test_structural_rejects(text: str, rule: RejectionRule) -> None:
    result = normalise(record(text))
    assert isinstance(result, Rejection)
    assert result.rule is rule


def test_rejection_carries_provenance() -> None:
    """The funnel must be measurable and traceable back to a source row."""
    result = normalise(record("SOFT DRINKS", provider_id="uspto", source_ref="78123456"))
    assert isinstance(result, Rejection)
    assert result.provider_id == "uspto"
    assert result.source_ref == "78123456"


def test_legal_entity_token_only_rejected_when_it_is_the_whole_name() -> None:
    """'INC' is filing noise; 'INCEPTION' is a brand."""
    assert accepted("INCEPTION").normalized == "inception"


# ── acceptance and casing ────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["CORVANE", "Corvane", "corvane", "  Corvane  "])
def test_casing_and_whitespace_normalise_to_one_form(text: str) -> None:
    assert accepted(text).normalized == "corvane"


def test_display_form_preserves_source_casing() -> None:
    """The register stores uppercase; we must not pretend to know true casing."""
    assert accepted("Corvane").display == "Corvane"


# ── tags, not rejects ────────────────────────────────────────────────────────


def test_dictionary_words_are_tagged_not_rejected() -> None:
    """Apple is a real brand. Whether to down-weight it is induction's call."""
    result = normalise(record("APPLE"), Lexicons(dictionary={"apple"}))
    assert isinstance(result, NormalisedRecord)
    assert Tag.DICTIONARY_WORD in result.tags


def test_profanity_is_tagged_not_rejected() -> None:
    """The safety subsystem needs these; deleting them destroys its input."""
    result = normalise(record("BADWORD"), Lexicons(profanity={"badword"}))
    assert isinstance(result, NormalisedRecord)
    assert Tag.PROFANITY_SIGNAL in result.tags


def test_vowelless_names_are_tagged_as_probable_acronyms() -> None:
    assert Tag.PROBABLE_ACRONYM in accepted("BXTR").tags
    assert Tag.PROBABLE_ACRONYM not in accepted("CORVANE").tags


def test_status_becomes_a_tag() -> None:
    assert Tag.LIVE_REGISTRATION in accepted("CORVANE", status=NameStatus.LIVE).tags
    assert Tag.ABANDONED in accepted("CORVANE", status=NameStatus.DEAD).tags


def test_international_registration_is_tagged_from_source_fields() -> None:
    """Foreign-origin marks follow different phonotactics and must be separable."""
    result = normalise(
        CorpusRecord(
            text="ONDARA",
            provider_id="uspto",
            source_ref="1",
            source_fields={"international_registration": True},
        )
    )
    assert isinstance(result, NormalisedRecord)
    assert Tag.INTERNATIONAL_REGISTRATION in result.tags


# ── aggregation is saturation measurement ────────────────────────────────────


def test_aggregation_counts_rather_than_deduplicates() -> None:
    """The count IS the saturation signal; collapsing to a set would delete it."""
    records = [accepted("LUMINA") for _ in range(5)]
    result = aggregate(records)
    assert result["lumina"].total_count == 5


def test_counts_are_kept_per_provider() -> None:
    """'300 USPTO marks' and '300 GitHub orgs' are different facts, never summed."""
    records = [
        accepted("CORVANE", provider_id="uspto"),
        accepted("CORVANE", provider_id="uspto"),
        accepted("CORVANE", provider_id="github"),
    ]
    agg = aggregate(records)["corvane"]
    assert agg.per_provider["uspto"].count == 2
    assert agg.per_provider["github"].count == 1
    assert agg.total_count == 3


def test_convergent_provider_count_is_a_quality_signal() -> None:
    """A name present across independent sources is genuinely used, not a filing."""
    agg = aggregate(
        [accepted("CORVANE", provider_id="uspto"), accepted("CORVANE", provider_id="yc")]
    )["corvane"]
    assert agg.convergent_provider_count == 2


def test_live_and_dead_are_counted_separately() -> None:
    agg = aggregate(
        [
            accepted("CORVANE", status=NameStatus.LIVE),
            accepted("CORVANE", status=NameStatus.DEAD),
            accepted("CORVANE", status=NameStatus.DEAD),
        ]
    )["corvane"]
    assert agg.per_provider["test"].live == 1
    assert agg.per_provider["test"].dead == 2


def test_earliest_year_is_retained_across_records() -> None:
    agg = aggregate(
        [
            accepted("CORVANE", first_seen_year=2015),
            accepted("CORVANE", first_seen_year=1998),
            accepted("CORVANE", first_seen_year=2020),
        ]
    )["corvane"]
    assert agg.per_provider["test"].earliest_year == 1998


def test_tags_union_across_occurrences() -> None:
    agg = aggregate(
        [accepted("CORVANE", status=NameStatus.LIVE), accepted("CORVANE", status=NameStatus.DEAD)]
    )["corvane"]
    assert {Tag.LIVE_REGISTRATION, Tag.ABANDONED} <= agg.tags


def test_aggregating_nothing_yields_nothing() -> None:
    assert aggregate([]) == {}
