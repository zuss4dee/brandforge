"""Corpus path resolution — one source of truth for writer and guard alike.

**Why this module exists.** The artifact directory used to be resolved inside
``tools/check_corpus.py``. Had the pipeline ever written somewhere else — a
rename, a typo in ``pyproject.toml``, a refactor that touched one side only —
the guard would have scanned an empty directory, printed "nothing to check",
and exited 0. Permanently green, protecting nothing.

Both the writer and the guard now resolve paths here, so they cannot diverge.

**The absent/empty distinction is load-bearing.** A configured directory that
does not exist is a *misconfiguration* and fails. A directory that exists and
is empty means *no corpus has been built yet* and passes. Collapsing those two
states into "found no files, all good" is exactly what made the guard vacuous.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from services.corpus.errors import CorpusConfigError

DEFAULT_ARTIFACTS: Final[str] = "data/corpus/artifacts"
DEFAULT_HOLDOUT: Final[str] = "evals/holdout"


@dataclass(frozen=True, slots=True)
class CorpusPaths:
    """Resolved locations for corpus artifacts and the sealed holdout."""

    artifacts: Path
    holdout: Path

    def require_artifacts_dir(self) -> None:
        """Fail when the artifact directory is absent rather than merely empty.

        The repository commits ``data/corpus/artifacts/.gitkeep`` precisely so
        this check can tell the two apart.
        """
        if not self.artifacts.exists():
            msg = (
                f"corpus artifact directory {self.artifacts} does not exist.\n"
                f"An absent directory is a misconfiguration, not an empty corpus — "
                f"a guard pointed at the wrong path finds nothing, reports success, "
                f"and protects nothing.\n"
                f"Check [tool.brandforge.corpus].artifacts in pyproject.toml."
            )
            raise CorpusConfigError(msg)
        if not self.artifacts.is_dir():
            msg = f"corpus artifact path {self.artifacts} exists but is not a directory"
            raise CorpusConfigError(msg)


def resolve(project_root: Path) -> CorpusPaths:
    """Read corpus paths from ``pyproject.toml``, falling back to defaults."""
    artifacts, holdout = DEFAULT_ARTIFACTS, DEFAULT_HOLDOUT

    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        section = data.get("tool", {}).get("brandforge", {}).get("corpus", {})
        if isinstance(section, dict):
            artifacts = str(section.get("artifacts", artifacts))
            holdout = str(section.get("holdout", holdout))

    for label, value in (("artifacts", artifacts), ("holdout", holdout)):
        if not value.strip():
            msg = f"[tool.brandforge.corpus].{label} is empty in {pyproject}"
            raise CorpusConfigError(msg)
        if Path(value).is_absolute():
            msg = (
                f"[tool.brandforge.corpus].{label} must be repository-relative, "
                f"got absolute path {value!r}"
            )
            raise CorpusConfigError(msg)

    return CorpusPaths(artifacts=project_root / artifacts, holdout=project_root / holdout)
