"""The corpus CI guard, exercised against persisted artifacts.

Each of the three checks is proven to *fail* on a deliberate violation, not
merely to pass on clean input. A guard nobody has watched fire is not proven.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.corpus.config import CorpusPaths
from services.corpus.errors import ArtifactSchemaError
from services.corpus.holdout import MIN_HOLDOUT_SIZE, seal
from services.corpus.pipeline import ARTIFACT_SCHEMA, CorpusArtifact
from services.corpus.providers import KNOWN_PROVIDERS
from services.corpus.types import LicenceClass, ProviderDescriptor, ProviderKind, Use
from tools.check_corpus import run_check as _run_check


def run_check(artifacts: Path, holdout: Path) -> int:
    """Adapter keeping these tests focused on guard behaviour, not plumbing."""
    return _run_check(CorpusPaths(artifacts=artifacts, holdout=holdout))


def pad_names(count: int) -> list[str]:
    """Alphabetic filler to clear MIN_HOLDOUT_SIZE.

    Must contain no digits: ``normalise_names`` strips non-alphabetic entries,
    so digit-padded fixtures silently shrink the holdout below its minimum.
    """
    return [f"pad{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(count)]


HOLDOUT_NAMES = ["figma", *pad_names(MIN_HOLDOUT_SIZE + 5)]


def write_artifact(
    directory: Path,
    *,
    use: Use = Use.INDUCTION,
    providers: tuple[str, ...] = ("uspto.case_files",),
    names: tuple[str, ...] = ("corvane", "lumeris"),
    stem: str = "artifact",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    artifact = CorpusArtifact(
        artifact_id=f"sha256:{stem}",
        use=use,
        blend_id="test.blend",
        provider_ids=providers,
        names=names,
    )
    path = directory / f"{stem}.json"
    path.write_text(artifact.to_json(), encoding="utf-8")
    return path


def write_holdout(directory: Path, names: list[str] = HOLDOUT_NAMES) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "holdout.txt").write_text("\n".join(names), encoding="utf-8")
    (directory / "holdout.sealed.json").write_text(seal(names).to_json(), encoding="utf-8")
    return directory


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "artifacts", tmp_path / "holdout"


# ── nothing to check ─────────────────────────────────────────────────────────


def test_green_when_artifact_dir_exists_but_is_empty(dirs: tuple[Path, Path]) -> None:
    """M1.0 ships the guard before the corpus. That state must be green."""
    artifacts, holdout = dirs
    artifacts.mkdir(parents=True)
    assert run_check(artifacts, holdout) == 0


def test_absent_artifact_dir_fails_rather_than_passing_vacuously(
    dirs: tuple[Path, Path],
) -> None:
    """The finding this fix exists for.

    A typo'd or renamed artifact path used to yield "nothing to check" and
    exit 0 — a guard reporting green while protecting nothing. An absent
    directory is now a configuration error; only an *empty* one is benign.
    """
    artifacts, holdout = dirs
    assert not artifacts.exists()
    assert run_check(artifacts, holdout) == 1


def test_artifact_path_pointing_at_a_file_fails(dirs: tuple[Path, Path], tmp_path: Path) -> None:
    _, holdout = dirs
    not_a_dir = tmp_path / "oops.txt"
    not_a_dir.write_text("", encoding="utf-8")
    assert run_check(not_a_dir, holdout) == 1


def test_green_when_artifacts_exist_but_holdout_does_not_for_non_induction(
    dirs: tuple[Path, Path],
) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts, use=Use.SATURATION)
    assert run_check(artifacts, holdout) == 0


# ── licence gate ─────────────────────────────────────────────────────────────


def test_clean_induction_artifact_passes(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts)
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 0


def test_unknown_provider_fails(dirs: tuple[Path, Path]) -> None:
    """An artifact from an unverifiable source cannot be shown to be permitted."""
    artifacts, holdout = dirs
    write_artifact(artifacts, providers=("mystery.source",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


def test_restricted_licence_fails_the_gate(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts, holdout = dirs
    restricted = ProviderDescriptor(
        id="crunchbase",
        name="Crunchbase",
        kind=ProviderKind.CURATED,
        licence=LicenceClass.COMMERCIAL_LICENSED,
    )
    monkeypatch.setattr(
        "tools.check_corpus.KNOWN_PROVIDERS", {**KNOWN_PROVIDERS, "crunchbase": restricted}
    )
    write_artifact(artifacts, providers=("crunchbase",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


# ── autophagy gate ───────────────────────────────────────────────────────────


def test_internal_provider_in_an_induction_artifact_fails(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts, holdout = dirs
    internal = ProviderDescriptor(
        id="bf.internal",
        name="BrandForge inventory",
        kind=ProviderKind.INTERNAL,
        licence=LicenceClass.INTERNAL_GENERATED,
    )
    monkeypatch.setattr(
        "tools.check_corpus.KNOWN_PROVIDERS", {**KNOWN_PROVIDERS, "bf.internal": internal}
    )
    write_artifact(artifacts, providers=("bf.internal",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


def test_internal_provider_in_a_saturation_artifact_passes(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts, holdout = dirs
    internal = ProviderDescriptor(
        id="bf.internal",
        name="BrandForge inventory",
        kind=ProviderKind.INTERNAL,
        licence=LicenceClass.INTERNAL_GENERATED,
    )
    monkeypatch.setattr(
        "tools.check_corpus.KNOWN_PROVIDERS", {**KNOWN_PROVIDERS, "bf.internal": internal}
    )
    write_artifact(artifacts, use=Use.SATURATION, providers=("bf.internal",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 0


def test_autophagy_check_fires_for_a_permissively_licensed_internal_provider(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_autophagy's own branch, independent of the licence gate.

    Previous tests used INTERNAL_GENERATED, which check_licences rejects first,
    so this code path had never executed.
    """
    artifacts, holdout = dirs
    mislabelled = ProviderDescriptor(
        id="bf.internal.mislabelled",
        name="BrandForge inventory, permissively licensed by mistake",
        kind=ProviderKind.INTERNAL,
        licence=LicenceClass.PUBLIC_DOMAIN,
    )
    monkeypatch.setattr(
        "tools.check_corpus.KNOWN_PROVIDERS",
        {**KNOWN_PROVIDERS, "bf.internal.mislabelled": mislabelled},
    )
    write_artifact(artifacts, providers=("bf.internal.mislabelled",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


# ── holdout contamination ────────────────────────────────────────────────────


def test_induction_artifact_without_a_holdout_fails(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts)
    assert run_check(artifacts, holdout) == 1


def test_exact_contamination_fails(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts, names=("figma", "corvane"))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


def test_phonetic_contamination_fails(dirs: tuple[Path, Path]) -> None:
    """The near-duplicate leakage that exact matching alone would miss."""
    artifacts, holdout = dirs
    write_artifact(artifacts, names=("corvane",))
    write_holdout(holdout, ["korvane", *HOLDOUT_NAMES])
    assert run_check(artifacts, holdout) == 1


def test_edit_distance_contamination_fails(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts, names=("figmaa",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


def test_broken_seal_fails_before_anything_else(dirs: tuple[Path, Path]) -> None:
    """Editing the holdout to make a check pass must itself fail the check."""
    artifacts, holdout = dirs
    write_artifact(artifacts)
    write_holdout(holdout)
    (holdout / "holdout.txt").write_text(
        "\n".join(n for n in HOLDOUT_NAMES if n != "figma"), encoding="utf-8"
    )
    assert run_check(artifacts, holdout) == 1


def test_undersized_holdout_fails(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts)
    write_holdout(holdout, ["figma", "corvane"])
    assert run_check(artifacts, holdout) == 1


# ── multiple artifacts ───────────────────────────────────────────────────────


def test_every_artifact_is_checked_not_just_the_first(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    write_artifact(artifacts, stem="clean")
    write_artifact(artifacts, stem="dirty", names=("figma",))
    write_holdout(holdout)
    assert run_check(artifacts, holdout) == 1


def test_malformed_artifact_schema_is_rejected(dirs: tuple[Path, Path]) -> None:
    artifacts, holdout = dirs
    artifacts.mkdir(parents=True)
    (artifacts / "bad.json").write_text(json.dumps({"schema": ARTIFACT_SCHEMA + 99}), "utf-8")
    write_holdout(holdout)
    with pytest.raises(ArtifactSchemaError, match="unsupported artifact schema"):
        run_check(artifacts, holdout)
