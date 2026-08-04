"""Pipeline orchestration, funnel reporting, and build-time guard enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.corpus.errors import (
    ArtifactSchemaError,
    AutophagyError,
    GuardViolationError,
    LicenceViolationError,
)
from services.corpus.holdout import HoldoutIndex
from services.corpus.pipeline import CorpusArtifact, build_artifact, ingest
from services.corpus.providers.fake import DEFAULT_NAMES, FakeProvider
from services.corpus.types import (
    BlendEntry,
    CorpusBlend,
    LicenceClass,
    NameStatus,
    ProviderKind,
    Use,
)

ALL_ROLES = frozenset({Use.INDUCTION, Use.SATURATION, Use.NOVELTY_REFERENCE})


def pad_names(count: int) -> list[str]:
    """Alphabetic filler to clear MIN_HOLDOUT_SIZE.

    Must contain no digits: ``normalise_names`` strips non-alphabetic entries,
    so digit-padded fixtures silently shrink the holdout below its minimum.
    """
    return [f"pad{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(count)]


def result_for(provider: FakeProvider, tmp_path: Path):  # type: ignore[no-untyped-def]
    snapshot = provider.acquire(tmp_path / f"{provider.descriptor.id}.dat")
    return ingest(provider, snapshot)


def blend_of(*provider_ids: str, roles: frozenset[Use] = ALL_ROLES) -> CorpusBlend:
    return CorpusBlend(
        blend_id="test.blend",
        entries=tuple(BlendEntry(pid, roles) for pid in provider_ids),
    )


# ── funnel ───────────────────────────────────────────────────────────────────


def test_funnel_counts_every_row(tmp_path: Path) -> None:
    """extracted == accepted + rejected. If this drifts, rows vanished silently."""
    report = result_for(FakeProvider(), tmp_path).report
    assert report.extracted == len(DEFAULT_NAMES)
    assert report.extracted == report.accepted + report.rejected_total


def test_funnel_attributes_each_rejection_to_a_rule(tmp_path: Path) -> None:
    """The fixture is built to trip one of each structural rule."""
    report = result_for(FakeProvider(), tmp_path).report
    assert set(report.rejected) == {
        "multi_token",
        "non_alphabetic",
        "too_short",
        "legal_entity_artifact",
    }
    assert report.accepted == 4  # Corvane, Lumeris, Zeprix, Ondara


def test_funnel_renders_readably(tmp_path: Path) -> None:
    rendered = result_for(FakeProvider(), tmp_path).report.render()
    assert "extracted" in rendered
    assert "multi_token" in rendered


def test_empty_source_yields_a_zero_funnel(tmp_path: Path) -> None:
    report = result_for(FakeProvider(names=()), tmp_path).report
    assert (report.extracted, report.accepted, report.acceptance_rate) == (0, 0, 0.0)


def test_aggregation_collapses_duplicates_but_keeps_counts(tmp_path: Path) -> None:
    provider = FakeProvider(names=[("Corvane", NameStatus.LIVE)] * 3)
    result = result_for(provider, tmp_path)
    assert result.report.accepted == 3
    assert result.report.distinct == 1
    assert result.names["corvane"].total_count == 3


# ── the licence gate at build time ───────────────────────────────────────────


def test_permitted_provider_builds_an_induction_artifact(tmp_path: Path) -> None:
    provider = FakeProvider(licence=LicenceClass.OPEN_ATTRIBUTION)
    artifact = build_artifact(
        Use.INDUCTION, blend_of(provider.descriptor.id), [result_for(provider, tmp_path)]
    )
    assert set(artifact.names) == {"corvane", "lumeris", "zeprix", "ondara"}


def test_commercially_licensed_provider_cannot_feed_induction(tmp_path: Path) -> None:
    provider = FakeProvider(provider_id="crunchbase", licence=LicenceClass.COMMERCIAL_LICENSED)
    with pytest.raises(LicenceViolationError, match="induction"):
        build_artifact(Use.INDUCTION, blend_of("crunchbase"), [result_for(provider, tmp_path)])


def test_unknown_licence_fails_closed(tmp_path: Path) -> None:
    provider = FakeProvider(provider_id="mystery", licence=LicenceClass.UNKNOWN)
    with pytest.raises(LicenceViolationError):
        build_artifact(Use.SATURATION, blend_of("mystery"), [result_for(provider, tmp_path)])


def test_a_restricted_provider_may_still_serve_a_permitted_use(tmp_path: Path) -> None:
    provider = FakeProvider(provider_id="crunchbase", licence=LicenceClass.COMMERCIAL_LICENSED)
    artifact = build_artifact(
        Use.SATURATION,
        blend_of("crunchbase", roles=frozenset({Use.SATURATION})),
        [result_for(provider, tmp_path)],
    )
    assert artifact.names


# ── the autophagy gate ───────────────────────────────────────────────────────


def test_internal_provider_cannot_feed_induction(tmp_path: Path) -> None:
    """Model collapse: inducing on our own output amplifies our own priors."""
    provider = FakeProvider(
        provider_id="bf.internal",
        licence=LicenceClass.INTERNAL_GENERATED,
        kind=ProviderKind.INTERNAL,
    )
    with pytest.raises(LicenceViolationError, match="induction"):
        build_artifact(Use.INDUCTION, blend_of("bf.internal"), [result_for(provider, tmp_path)])


def test_autophagy_branch_fires_for_a_permissively_licensed_internal_provider(
    tmp_path: Path,
) -> None:
    """The case the licence gate CANNOT catch, and the reason this gate exists.

    Review found every previous 'autophagy' test used INTERNAL_GENERATED, whose
    licence already forbids induction — so ``require()`` raised first and this
    branch never executed. An internal provider carrying a permissive licence
    is exactly the misconfiguration the kind check is for.
    """
    provider = FakeProvider(
        provider_id="bf.internal.mislabelled",
        licence=LicenceClass.PUBLIC_DOMAIN,  # licence gate would wave this through
        kind=ProviderKind.INTERNAL,
    )
    with pytest.raises(AutophagyError, match="internal provider"):
        build_artifact(
            Use.INDUCTION,
            blend_of("bf.internal.mislabelled"),
            [result_for(provider, tmp_path)],
        )


def test_autophagy_error_is_catchable_as_a_guard_violation(tmp_path: Path) -> None:
    """One base type for 'a corpus guard rejected this', across both gates."""
    provider = FakeProvider(
        provider_id="bf.internal.mislabelled",
        licence=LicenceClass.PUBLIC_DOMAIN,
        kind=ProviderKind.INTERNAL,
    )
    with pytest.raises(GuardViolationError):
        build_artifact(
            Use.INDUCTION,
            blend_of("bf.internal.mislabelled"),
            [result_for(provider, tmp_path)],
        )


def test_licence_violation_is_also_a_guard_violation(tmp_path: Path) -> None:
    provider = FakeProvider(provider_id="crunchbase", licence=LicenceClass.COMMERCIAL_LICENSED)
    with pytest.raises(GuardViolationError):
        build_artifact(Use.INDUCTION, blend_of("crunchbase"), [result_for(provider, tmp_path)])


def test_internal_provider_may_feed_saturation(tmp_path: Path) -> None:
    """Our own output informs counts; it must never inform weights."""
    provider = FakeProvider(
        provider_id="bf.internal",
        licence=LicenceClass.INTERNAL_GENERATED,
        kind=ProviderKind.INTERNAL,
    )
    artifact = build_artifact(
        Use.SATURATION,
        blend_of("bf.internal", roles=frozenset({Use.SATURATION})),
        [result_for(provider, tmp_path)],
    )
    assert artifact.names


# ── holdout exclusion across the blend ───────────────────────────────────────


def test_holdout_names_are_excluded_from_induction(tmp_path: Path) -> None:
    index = HoldoutIndex.build(["corvane", *pad_names(60)])
    artifact = build_artifact(
        Use.INDUCTION,
        blend_of("fake.curated"),
        [result_for(FakeProvider(), tmp_path)],
        holdout=index,
    )
    assert "corvane" not in artifact.names
    assert artifact.excluded_by_holdout == {"exact": 1}


def test_phonetic_near_duplicates_are_excluded_too(tmp_path: Path) -> None:
    """The reason exact-match exclusion alone is insufficient."""
    provider = FakeProvider(names=[("Korvane", NameStatus.LIVE)])
    index = HoldoutIndex.build(["corvane", *pad_names(60)])
    artifact = build_artifact(
        Use.INDUCTION, blend_of("fake.curated"), [result_for(provider, tmp_path)], holdout=index
    )
    assert artifact.names == ()
    assert artifact.excluded_by_holdout == {"phonetic": 1}


def test_holdout_is_applied_across_the_blend_not_per_provider(tmp_path: Path) -> None:
    """Per-provider checks let each source pass while the blend is contaminated."""
    a = FakeProvider(provider_id="src.a", names=[("Corvane", NameStatus.LIVE)])
    b = FakeProvider(provider_id="src.b", names=[("Lumeris", NameStatus.LIVE)])
    index = HoldoutIndex.build(["corvane", *pad_names(60)])
    artifact = build_artifact(
        Use.INDUCTION,
        blend_of("src.a", "src.b"),
        [result_for(a, tmp_path), result_for(b, tmp_path)],
        holdout=index,
    )
    assert artifact.names == ("lumeris",)


def test_holdout_is_not_applied_to_non_induction_artifacts(tmp_path: Path) -> None:
    """Saturation counting legitimately includes held-out names."""
    index = HoldoutIndex.build(["corvane", *pad_names(60)])
    artifact = build_artifact(
        Use.SATURATION,
        blend_of("fake.curated", roles=frozenset({Use.SATURATION})),
        [result_for(FakeProvider(), tmp_path)],
        holdout=index,
    )
    assert "corvane" in artifact.names


# ── blend roles and serialisation ────────────────────────────────────────────


def test_providers_without_the_role_do_not_contribute(tmp_path: Path) -> None:
    a = FakeProvider(provider_id="src.a", names=[("Corvane", NameStatus.LIVE)])
    b = FakeProvider(provider_id="src.b", names=[("Lumeris", NameStatus.LIVE)])
    blend = CorpusBlend(
        blend_id="partial",
        entries=(
            BlendEntry("src.a", frozenset({Use.INDUCTION})),
            BlendEntry("src.b", frozenset({Use.SATURATION})),
        ),
    )
    artifact = build_artifact(
        Use.INDUCTION, blend, [result_for(a, tmp_path), result_for(b, tmp_path)]
    )
    assert artifact.names == ("corvane",)
    assert artifact.provider_ids == ("src.a",)


def test_artifact_id_is_content_addressed(tmp_path: Path) -> None:
    result = result_for(FakeProvider(), tmp_path)
    first = build_artifact(Use.INDUCTION, blend_of("fake.curated"), [result])
    second = build_artifact(Use.INDUCTION, blend_of("fake.curated"), [result])
    assert first.artifact_id == second.artifact_id

    smaller = build_artifact(
        Use.INDUCTION,
        blend_of("fake.curated"),
        [result_for(FakeProvider(names=[("Corvane", NameStatus.LIVE)]), tmp_path)],
    )
    assert smaller.artifact_id != first.artifact_id


def test_artifact_round_trips_through_json(tmp_path: Path) -> None:
    artifact = build_artifact(
        Use.INDUCTION, blend_of("fake.curated"), [result_for(FakeProvider(), tmp_path)]
    )
    path = tmp_path / "artifact.json"
    path.write_text(artifact.to_json(), encoding="utf-8")
    assert CorpusArtifact.from_path(path) == artifact


def test_unsupported_artifact_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(ArtifactSchemaError, match="unsupported artifact schema"):
        CorpusArtifact.from_path(path)
