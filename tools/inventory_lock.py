"""Append-only guard for ruleset inventories — the enforcement for ADR-0014.

Why this exists
---------------
A candidate's identity is its *index* in a mixed-radix address space (ADR-0012).
The radix of each digit is the size of an inventory. Removing or reordering a
single inventory entry shifts every subsequent digit and silently re-points
every index in the system: every stored provenance replays to a different name
than the one recorded.

The failure raises no error. Nothing crashes, nothing logs, no test fails unless
one specifically checks for it. This module is that check.

Mechanism
---------
Each inventory YAML has a sibling ``<stem>.lock.json`` recording the ordered
list of entry ids and a fingerprint of each entry's *address-relevant* fields.
``check`` fails on removal, reordering, truncation, or mutation. ``update``
regenerates the locks — and the resulting lockfile diff is the reviewable
artifact, the same philosophy as golden fixtures.

Descriptive fields (``gloss``, ``notes``, ``status`` …) may change freely: they
do not participate in ``build()`` and therefore cannot move the address space.
Everything else — including ``weight``, which feeds quantised slot expansion —
is address-relevant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

LOCK_SCHEMA: Final[int] = 1
LOCK_SUFFIX: Final[str] = ".lock.json"

#: Fields that do not affect ``build()`` and may therefore change without
#: perturbing the address space. Deliberately minimal — when in doubt, a field
#: is address-relevant. ``status`` is safe because deprecated entries keep their
#: position and are excluded by *gates*, never removed from the inventory.
DESCRIPTIVE_FIELDS: Final[frozenset[str]] = frozenset(
    {"gloss", "notes", "attested", "exemplars", "description", "status", "added_in"}
)


@dataclass(frozen=True, slots=True)
class Violation:
    """A single append-only breach, rendered as one line of CI output."""

    inventory: Path
    message: str

    def __str__(self) -> str:
        return f"{self.inventory}: {self.message}"


def canonical_fingerprint(entry: dict[str, Any]) -> str:
    """Hash an entry's address-relevant fields.

    Canonical JSON with sorted keys, so formatting changes in the YAML (key
    order, quoting, comments) never register as a violation. Only semantics do.
    """
    material = {k: v for k, v in entry.items() if k not in DESCRIPTIVE_FIELDS}
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.blake2b(encoded.encode("utf-8"), digest_size=16).hexdigest()


def load_entries(path: Path) -> list[dict[str, Any]]:
    """Read an inventory YAML as an ordered list of entries."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, list):
        msg = f"{path}: inventory must be a YAML list, got {type(raw).__name__}"
        raise ValueError(msg)

    entries: list[dict[str, Any]] = []
    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            msg = f"{path}: entry {position} must be a mapping, got {type(item).__name__}"
            raise ValueError(msg)
        if "id" not in item:
            msg = f"{path}: entry {position} has no 'id' field"
            raise ValueError(msg)
        entries.append(item)

    ids = [str(e["id"]) for e in entries]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        msg = f"{path}: duplicate ids {sorted(duplicates)}"
        raise ValueError(msg)

    return entries


def build_lock(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Render the lockfile payload for an inventory."""
    return {
        "schema": LOCK_SCHEMA,
        "count": len(entries),
        "entries": [{"id": str(e["id"]), "fingerprint": canonical_fingerprint(e)} for e in entries],
    }


def load_lock(path: Path) -> dict[str, Any] | None:
    """Read a lockfile, or ``None`` when the inventory has never been locked."""
    if not path.exists():
        return None
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{path}: lockfile must be a JSON object"
        raise ValueError(msg)
    return payload


def compare(
    inventory: Path, entries: list[dict[str, Any]], lock: dict[str, Any]
) -> list[Violation]:
    """Diff an inventory against its lock, returning every append-only breach."""
    violations: list[Violation] = []

    schema = lock.get("schema")
    if schema != LOCK_SCHEMA:
        return [
            Violation(inventory, f"lockfile schema {schema!r} unsupported (expected {LOCK_SCHEMA})")
        ]

    locked_raw: object = lock.get("entries", [])
    if not isinstance(locked_raw, list):
        return [Violation(inventory, "lockfile 'entries' must be a list")]
    locked: list[dict[str, Any]] = [e for e in locked_raw if isinstance(e, dict)]

    if len(entries) < len(locked):
        violations.append(
            Violation(
                inventory,
                f"inventory shrank from {len(locked)} to {len(entries)} entries — "
                f"entries are append-only and must never be removed (ADR-0014)",
            )
        )

    for position, locked_entry in enumerate(locked):
        if position >= len(entries):
            violations.append(
                Violation(
                    inventory,
                    f"position {position}: entry {locked_entry.get('id')!r} was removed",
                )
            )
            continue

        current = entries[position]
        current_id = str(current["id"])
        locked_id = str(locked_entry.get("id"))

        if current_id != locked_id:
            violations.append(
                Violation(
                    inventory,
                    f"position {position}: expected {locked_id!r}, found {current_id!r} — "
                    f"reordering re-points every downstream index",
                )
            )
            continue

        current_fp = canonical_fingerprint(current)
        if current_fp != locked_entry.get("fingerprint"):
            violations.append(
                Violation(
                    inventory,
                    f"position {position}: entry {current_id!r} changed an address-relevant "
                    f"field — this alters what that index generates",
                )
            )

    return violations


def inventory_root(project_root: Path) -> Path:
    """Resolve the configured inventory directory from pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    configured = "engine/rulesets"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        section = data.get("tool", {}).get("brandforge", {}).get("inventory", {})
        if isinstance(section, dict):
            configured = str(section.get("root", configured))
    return project_root / configured


def discover(root: Path) -> list[Path]:
    """Find every inventory YAML beneath ``root``, in stable order."""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.yaml") if not p.name.endswith(LOCK_SUFFIX))


def lock_path_for(inventory: Path) -> Path:
    return inventory.with_suffix(LOCK_SUFFIX)


def run_check(root: Path) -> int:
    inventories = discover(root)
    if not inventories:
        print(f"inventory-lock: no inventories under {root} — nothing to check")
        return 0

    violations: list[Violation] = []
    unlocked: list[Path] = []

    for inventory in inventories:
        entries = load_entries(inventory)
        lock = load_lock(lock_path_for(inventory))
        if lock is None:
            unlocked.append(inventory)
            continue
        violations.extend(compare(inventory, entries, lock))

    for path in unlocked:
        violations.append(
            Violation(path, "no lockfile — run 'make inventory-lock' and commit the result")
        )

    if violations:
        print("inventory-lock: APPEND-ONLY VIOLATIONS (ADR-0014)\n")
        for violation in violations:
            print(f"  ✗ {violation}")
        print(
            "\nInventories are append-only. Removing or reordering an entry silently\n"
            "re-points every stored index to a different name, with no error raised.\n"
            "If this change is genuinely intended, it requires minting a new address\n"
            "space — not editing this one in place. See docs/adr/0014-append-only-rulesets.md\n"
        )
        return 1

    noun = "inventory" if len(inventories) == 1 else "inventories"
    print(f"inventory-lock: {len(inventories)} {noun} OK")
    return 0


def run_update(root: Path) -> int:
    inventories = discover(root)
    if not inventories:
        print(f"inventory-lock: no inventories under {root} — nothing to lock")
        return 0

    for inventory in inventories:
        entries = load_entries(inventory)
        payload = build_lock(entries)
        lock_path_for(inventory).write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        print(f"inventory-lock: wrote {lock_path_for(inventory)} ({len(entries)} entries)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inventory-lock",
        description="Append-only guard for ruleset inventories (ADR-0014).",
    )
    parser.add_argument(
        "command", choices=("check", "update"), help="verify locks, or regenerate them"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="inventory directory (defaults to [tool.brandforge.inventory].root)",
    )
    args = parser.parse_args(argv)

    root = args.root if args.root is not None else inventory_root(Path.cwd())
    return run_check(root) if args.command == "check" else run_update(root)


if __name__ == "__main__":
    sys.exit(main())
