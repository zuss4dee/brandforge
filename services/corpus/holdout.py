"""Held-out evaluation set: sealing and contamination exclusion.

The hazard is specific (M1.0 §5.1). The M1.7 evaluation ceiling is real
funded-startup names, and the USPTO register contains close to every
commercially used US mark — so **most holdout names are also in the induction
corpus**. Without active exclusion we would induce weights from the very names
later used to prove the engine, and the discrimination study would be
measuring memorisation while still returning a plausible number.

Two mechanisms:

* **The seal.** A committed content hash of the holdout. Without it, the guard
  checks a file that the guard's own failure tempts you to edit.
* **Three-key exclusion.** Exact form, Double Metaphone, and edit distance ≤ 1.
  Exact-match alone would let ``Figmaa`` carry a held-out ``Figma`` straight
  through.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from metaphone import doublemetaphone

from services.corpus.errors import HoldoutSealError

SEAL_SCHEMA: Final[int] = 1

#: A holdout smaller than this cannot support the M1.7 study, and an empty one
#: would satisfy the contamination check trivially. A guard that can be
#: satisfied by degenerating its own inputs is not a guard.
MIN_HOLDOUT_SIZE: Final[int] = 50


def normalise_names(raw: Iterable[str]) -> tuple[str, ...]:
    """Canonical holdout form: casefolded, alphabetic-only, deduped, sorted."""
    cleaned = {
        name.strip().casefold()
        for name in raw
        if name.strip() and name.strip().isascii() and name.strip().isalpha()
    }
    return tuple(sorted(cleaned))


@dataclass(frozen=True, slots=True)
class HoldoutSeal:
    """Committed proof of what the holdout contained when it was sealed."""

    schema: int
    content_hash: str
    count: int
    sealed_on: str

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "schema": self.schema,
                    "content_hash": self.content_hash,
                    "count": self.count,
                    "sealed_on": self.sealed_on,
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def from_path(cls, path: Path) -> HoldoutSeal:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != SEAL_SCHEMA:
            msg = f"{path}: unsupported seal schema {payload.get('schema')!r}"
            raise HoldoutSealError(msg)
        return cls(
            schema=payload["schema"],
            content_hash=payload["content_hash"],
            count=payload["count"],
            sealed_on=payload["sealed_on"],
        )


def compute_seal_hash(names: tuple[str, ...]) -> str:
    material = "\n".join(names).encode("utf-8")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


def seal(names: Iterable[str]) -> HoldoutSeal:
    canonical = normalise_names(names)
    return HoldoutSeal(
        schema=SEAL_SCHEMA,
        content_hash=compute_seal_hash(canonical),
        count=len(canonical),
        sealed_on=datetime.now(UTC).date().isoformat(),
    )


def verify_seal(names: Iterable[str], expected: HoldoutSeal) -> None:
    """Assert the holdout is exactly what was sealed. The anti-tampering check."""
    canonical = normalise_names(names)
    actual = compute_seal_hash(canonical)
    if actual != expected.content_hash:
        msg = (
            f"holdout does not match its seal — expected {expected.content_hash} "
            f"({expected.count} names), computed {actual} ({len(canonical)} names).\n"
            f"The holdout must not be edited to make a contamination check pass. "
            f"If it genuinely changed, re-seal deliberately and commit the manifest."
        )
        raise HoldoutSealError(msg)
    if len(canonical) < MIN_HOLDOUT_SIZE:
        msg = (
            f"holdout has {len(canonical)} names, below the minimum of "
            f"{MIN_HOLDOUT_SIZE}. An undersized holdout satisfies the "
            f"contamination check without proving anything."
        )
        raise HoldoutSealError(msg)


def phonetic_key(name: str) -> str:
    """Primary Double Metaphone code. ``Corvane`` and ``Korvane`` both give KRFN.

    The single point where the untyped ``metaphone`` package is called; the
    result is coerced so nothing untyped escapes into the rest of the module.
    """
    primary, _secondary = doublemetaphone(name)
    return str(primary)


def _deletions(word: str) -> set[str]:
    """Every single-character deletion of ``word``."""
    return {word[:i] + word[i + 1 :] for i in range(len(word))}


@dataclass(frozen=True, slots=True)
class HoldoutIndex:
    """Exclusion index over a sealed holdout.

    Edit-distance-1 matching uses deletion neighbourhoods rather than pairwise
    comparison: comparing every corpus row against every holdout name would be
    millions times hundreds of comparisons. Deletion lookup is O(len(name)).

    **The index is deliberately conservative.** Deletion-set intersection can
    flag a few pairs at distance 2 (transpositions, notably). Over-exclusion
    costs a handful of rows out of millions; under-exclusion silently
    contaminates the evaluation. The asymmetry is the whole point, so the
    cheaper and safer side is chosen on purpose.
    """

    names: tuple[str, ...]
    exact: frozenset[str]
    phonetic: frozenset[str]
    deletions: frozenset[str]

    @classmethod
    def build(cls, names: Iterable[str]) -> HoldoutIndex:
        canonical = normalise_names(names)
        dele: set[str] = set()
        for name in canonical:
            dele |= _deletions(name)
        return cls(
            names=canonical,
            exact=frozenset(canonical),
            phonetic=frozenset(phonetic_key(n) for n in canonical if phonetic_key(n)),
            deletions=frozenset(dele),
        )

    def contamination_key(self, candidate: str) -> str | None:
        """Which key excludes ``candidate``, or ``None`` if it is clean."""
        name = candidate.strip().casefold()
        if not name:
            return None
        if name in self.exact:
            return "exact"
        key = phonetic_key(name)
        if key and key in self.phonetic:
            return "phonetic"
        if name in self.deletions:
            return "edit_distance"
        if _deletions(name) & (self.exact | self.deletions):
            return "edit_distance"
        return None

    def excludes(self, candidate: str) -> bool:
        return self.contamination_key(candidate) is not None

    def __len__(self) -> int:
        return len(self.names)


def load_holdout(directory: Path) -> tuple[tuple[str, ...], HoldoutSeal] | None:
    """Read and verify a sealed holdout, or ``None`` when none exists yet."""
    names_path = directory / "holdout.txt"
    seal_path = directory / "holdout.sealed.json"

    if not names_path.exists() and not seal_path.exists():
        return None
    if names_path.exists() != seal_path.exists():
        present, missing = (
            (names_path, seal_path) if names_path.exists() else (seal_path, names_path)
        )
        msg = f"{present} exists but {missing} does not — a holdout without its seal is unusable"
        raise HoldoutSealError(msg)

    names = tuple(names_path.read_text(encoding="utf-8").splitlines())
    manifest = HoldoutSeal.from_path(seal_path)
    verify_seal(names, manifest)
    return normalise_names(names), manifest
