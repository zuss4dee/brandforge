"""Tests for the append-only guard (ADR-0014).

The guard defends against a failure that produces no symptom: a removed or
reordered inventory entry silently re-points every stored index. These tests
are the only thing standing between that failure and production, so they cover
each breach shape explicitly rather than relying on a happy-path smoke test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools.inventory_lock import (
    DESCRIPTIVE_FIELDS,
    canonical_fingerprint,
    compare,
    discover,
    load_entries,
    lock_path_for,
    run_check,
    run_update,
)


def write_inventory(root: Path, name: str, entries: list[dict[str, object]]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.yaml"
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


BASE: list[dict[str, object]] = [
    {"id": "mor.lat.corv", "phonemic": "korv", "weight": 0.4, "gloss": "raven"},
    {"id": "mor.lat.lum", "phonemic": "lum", "weight": 0.9, "gloss": "light"},
    {"id": "mor.aff.ane", "phonemic": "ein", "weight": 0.3, "gloss": "suffix"},
]


@pytest.fixture
def locked(tmp_path: Path) -> Path:
    """An inventory with a freshly generated, passing lockfile."""
    root = tmp_path / "rulesets"
    write_inventory(root, "morphemes", BASE)
    assert run_update(root) == 0
    assert run_check(root) == 0
    return root


# ── the four breach shapes ───────────────────────────────────────────────────


def test_removal_is_rejected(locked: Path) -> None:
    write_inventory(locked, "morphemes", [BASE[0], BASE[2]])
    assert run_check(locked) == 1


def test_reordering_is_rejected(locked: Path) -> None:
    write_inventory(locked, "morphemes", [BASE[1], BASE[0], BASE[2]])
    assert run_check(locked) == 1


def test_truncation_is_rejected(locked: Path) -> None:
    write_inventory(locked, "morphemes", BASE[:2])
    assert run_check(locked) == 1


def test_address_relevant_mutation_is_rejected(locked: Path) -> None:
    """Weight feeds quantised slot expansion, so changing it moves the space."""
    mutated = [dict(e) for e in BASE]
    mutated[1]["weight"] = 0.5
    write_inventory(locked, "morphemes", mutated)
    assert run_check(locked) == 1


# ── what must remain permitted ───────────────────────────────────────────────


def test_appending_is_permitted(locked: Path) -> None:
    extended = [*BASE, {"id": "mor.gre.chron", "phonemic": "kron", "weight": 0.5}]
    write_inventory(locked, "morphemes", extended)
    assert run_check(locked) == 0


def test_descriptive_field_changes_are_permitted(locked: Path) -> None:
    """Glosses and status flags do not participate in build()."""
    edited = [dict(e) for e in BASE]
    edited[0]["gloss"] = "raven, crow, corvid"
    edited[1]["status"] = "deprecated"
    write_inventory(locked, "morphemes", edited)
    assert run_check(locked) == 0


def test_yaml_formatting_changes_are_permitted(locked: Path) -> None:
    """Key order is a formatting detail; only semantics may trip the guard."""
    reshuffled = [{k: e[k] for k in reversed(list(e))} for e in BASE]
    write_inventory(locked, "morphemes", reshuffled)
    assert run_check(locked) == 0


# ── operational behaviour ────────────────────────────────────────────────────


def test_unlocked_inventory_is_rejected(tmp_path: Path) -> None:
    """A new inventory without a lockfile must fail rather than pass silently."""
    root = tmp_path / "rulesets"
    write_inventory(root, "morphemes", BASE)
    assert run_check(root) == 1


def test_missing_root_is_not_an_error(tmp_path: Path) -> None:
    """M0 ships the guard before any inventory exists; that must be green."""
    assert run_check(tmp_path / "does-not-exist") == 0


def test_lockfile_records_order_and_fingerprints(locked: Path) -> None:
    payload = json.loads(lock_path_for(locked / "morphemes.yaml").read_text(encoding="utf-8"))
    assert payload["count"] == 3
    assert [e["id"] for e in payload["entries"]] == [e["id"] for e in BASE]
    assert all(len(e["fingerprint"]) == 32 for e in payload["entries"])


def test_lockfiles_are_not_treated_as_inventories(locked: Path) -> None:
    assert [p.name for p in discover(locked)] == ["morphemes.yaml"]


# ── input validation ─────────────────────────────────────────────────────────


def test_entry_without_id_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "rulesets"
    path = write_inventory(root, "bad", [{"phonemic": "korv"}])
    with pytest.raises(ValueError, match="no 'id' field"):
        load_entries(path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "rulesets"
    path = write_inventory(root, "bad", [{"id": "a"}, {"id": "a"}])
    with pytest.raises(ValueError, match="duplicate ids"):
        load_entries(path)


def test_non_list_inventory_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "rulesets"
    root.mkdir(parents=True)
    path = root / "bad.yaml"
    path.write_text("id: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML list"):
        load_entries(path)


def test_empty_inventory_loads_as_empty(tmp_path: Path) -> None:
    root = tmp_path / "rulesets"
    root.mkdir(parents=True)
    path = root / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_entries(path) == []


# ── fingerprint semantics ────────────────────────────────────────────────────


def test_fingerprint_ignores_exactly_the_descriptive_fields() -> None:
    entry: dict[str, object] = {"id": "x", "weight": 0.5}
    baseline = canonical_fingerprint(entry)
    for field in DESCRIPTIVE_FIELDS:
        assert canonical_fingerprint({**entry, field: "anything"}) == baseline


def test_fingerprint_detects_nested_changes() -> None:
    a = canonical_fingerprint({"id": "x", "semantics": {"valence": 0.1}})
    b = canonical_fingerprint({"id": "x", "semantics": {"valence": 0.2}})
    assert a != b


def test_compare_reports_every_violation_not_just_the_first(tmp_path: Path) -> None:
    inventory = tmp_path / "morphemes.yaml"
    lock = {
        "schema": 1,
        "count": 3,
        "entries": [
            {"id": "a", "fingerprint": canonical_fingerprint({"id": "a"})},
            {"id": "b", "fingerprint": canonical_fingerprint({"id": "b"})},
            {"id": "c", "fingerprint": canonical_fingerprint({"id": "c"})},
        ],
    }
    current: list[dict[str, object]] = [{"id": "z"}, {"id": "b", "weight": 1}, {"id": "c"}]
    violations = compare(inventory, current, lock)
    assert len(violations) == 2  # reordered 'a'→'z', plus mutated 'b'
