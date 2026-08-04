"""Structural invariants of the repository itself.

M0's definition of done is "CI green on an empty vertical slice". These tests
assert the slice is actually wired up — that the packages exist, that the ADR
process has an index, and that the documents the CI guards cite are present.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import engine
import services

ROOT = Path(__file__).resolve().parent.parent


def test_engine_and_services_are_importable() -> None:
    assert engine.__doc__
    assert services.__doc__


@pytest.mark.parametrize(
    "path",
    [
        "docs/design/00-system-design.md",
        "docs/design/01-data-model.md",
        "docs/design/02-milestones.md",
        "docs/design/03-generation-engine.md",
        "docs/design/04-generation-evaluation.md",
        "docs/design/06-m1-0-corpus-assembly.md",
        "docs/design/07-corpus-provider-architecture.md",
        "docs/adr/README.md",
        "docs/ops/zone-file-access.md",
        "docs/ai/verified-facts.md",
        "docs/ai/blocked.md",
        "docs/ai/backlog.md",
        "CONTRIBUTING.md",
        "CLAUDE.md",
        "README.md",
    ],
)
def test_required_documents_exist(path: str) -> None:
    assert (ROOT / path).is_file(), f"missing {path}"


def test_every_adr_is_listed_in_the_index() -> None:
    """An ADR nobody can find is an ADR nobody will honour."""
    index = (ROOT / "docs/adr/README.md").read_text(encoding="utf-8")
    adrs = sorted(p.name for p in (ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    missing = [name for name in adrs if name not in index]
    assert not missing, f"ADRs absent from the index: {missing}"


def test_import_linter_guards_the_engine_boundary() -> None:
    """ADR-0006 is only real if the contract exists; assert it does."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)

    contracts = config["tool"]["importlinter"]["contracts"]
    engine_contracts = [c for c in contracts if c["source_modules"] == ["engine"]]
    assert engine_contracts, "no import-linter contract protects the engine"

    forbidden = {m for c in engine_contracts for m in c["forbidden_modules"]}
    assert "services" in forbidden

    # ADR-0012: determinism is structural, not a convention.
    for module in ("random", "time", "datetime"):
        assert module in forbidden, f"engine purity contract must forbid {module!r}"
