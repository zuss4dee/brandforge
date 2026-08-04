"""Holdout sealing and three-key contamination exclusion.

Contamination is invisible from the outside: a contaminated study still
produces a number, and the number looks fine. Every assertion here exists
because the failure it prevents is silent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.corpus.errors import HoldoutSealError
from services.corpus.holdout import (
    MIN_HOLDOUT_SIZE,
    HoldoutIndex,
    load_holdout,
    normalise_names,
    phonetic_key,
    seal,
    verify_seal,
)


def pad_names(count: int) -> list[str]:
    """Alphabetic filler to clear MIN_HOLDOUT_SIZE.

    Must contain no digits: ``normalise_names`` strips non-alphabetic entries,
    so digit-padded fixtures silently shrink the holdout below its minimum.
    """
    return [f"pad{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(count)]


NAMES = pad_names(MIN_HOLDOUT_SIZE + 10)


def write_holdout(directory: Path, names: list[str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "holdout.txt").write_text("\n".join(names), encoding="utf-8")
    (directory / "holdout.sealed.json").write_text(seal(names).to_json(), encoding="utf-8")
    return directory


# ── the seal ─────────────────────────────────────────────────────────────────


def test_seal_verifies_its_own_holdout() -> None:
    verify_seal(NAMES, seal(NAMES))


def test_editing_the_holdout_breaks_the_seal() -> None:
    """The anti-tampering property: you cannot quietly delete a contaminating name."""
    manifest = seal(NAMES)
    with pytest.raises(HoldoutSealError, match="does not match its seal"):
        verify_seal(NAMES[:-1], manifest)


def test_adding_a_name_breaks_the_seal() -> None:
    manifest = seal(NAMES)
    with pytest.raises(HoldoutSealError, match="does not match its seal"):
        verify_seal([*NAMES, "sneaky"], manifest)


def test_undersized_holdout_is_rejected() -> None:
    """A guard satisfiable by degenerating its own inputs is not a guard."""
    tiny = ["alpha", "beta"]
    with pytest.raises(HoldoutSealError, match="below the minimum"):
        verify_seal(tiny, seal(tiny))


def test_seal_is_order_and_case_insensitive() -> None:
    verify_seal([n.upper() for n in reversed(NAMES)], seal(NAMES))


def test_normalisation_drops_non_alphabetic_entries() -> None:
    assert normalise_names(["Corvane", "3M", "soft drinks", "", "  "]) == ("corvane",)


# ── three-key exclusion ──────────────────────────────────────────────────────


def test_exact_match_is_excluded() -> None:
    index = HoldoutIndex.build(["figma", *NAMES])
    assert index.contamination_key("FIGMA") == "exact"


def test_phonetic_near_duplicate_is_excluded() -> None:
    """Korvane and Corvane both give Double Metaphone KRFN — the leakage case."""
    index = HoldoutIndex.build(["corvane", *NAMES])
    assert index.contamination_key("korvane") == "phonetic"


def test_edit_distance_one_is_excluded() -> None:
    """Exact-match exclusion alone would let 'figmaa' carry 'figma' through."""
    index = HoldoutIndex.build(["figma", *NAMES])
    for variant in ("figmaa", "figm", "figna"):
        assert index.contamination_key(variant) is not None, variant


def test_unrelated_names_are_not_excluded() -> None:
    index = HoldoutIndex.build(["figma", "corvane", *NAMES])
    for clean in ("zeprix", "ondara", "lumeris"):
        assert index.contamination_key(clean) is None, clean


def test_exclusion_is_conservative_by_design() -> None:
    """Over-exclusion costs a few rows; under-exclusion silently contaminates."""
    index = HoldoutIndex.build(["figma", *NAMES])
    assert index.excludes("figma")
    assert not index.excludes("completelydifferent")


def test_empty_candidate_is_not_excluded() -> None:
    assert HoldoutIndex.build(NAMES).contamination_key("   ") is None


def test_phonetic_key_is_stable() -> None:
    assert phonetic_key("Corvane") == phonetic_key("korvane") != ""


def test_index_length_reflects_deduplicated_names() -> None:
    assert len(HoldoutIndex.build([*NAMES, *NAMES])) == len(NAMES)


# ── loading from disk ────────────────────────────────────────────────────────


def test_load_returns_none_when_no_holdout_exists(tmp_path: Path) -> None:
    """M1.0 ships the machinery before the funded-startup list exists."""
    assert load_holdout(tmp_path / "absent") is None


def test_load_verifies_the_seal(tmp_path: Path) -> None:
    directory = write_holdout(tmp_path / "holdout", NAMES)
    loaded = load_holdout(directory)
    assert loaded is not None
    names, manifest = loaded
    assert manifest.count == len(NAMES)
    assert len(names) == len(NAMES)


def test_load_fails_when_the_names_were_edited_after_sealing(tmp_path: Path) -> None:
    directory = write_holdout(tmp_path / "holdout", NAMES)
    (directory / "holdout.txt").write_text("\n".join(NAMES[:-5]), encoding="utf-8")
    with pytest.raises(HoldoutSealError, match="does not match its seal"):
        load_holdout(directory)


def test_names_without_a_seal_are_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "holdout"
    directory.mkdir()
    (directory / "holdout.txt").write_text("\n".join(NAMES), encoding="utf-8")
    with pytest.raises(HoldoutSealError, match="without its seal"):
        load_holdout(directory)
