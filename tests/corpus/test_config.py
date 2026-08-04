"""Corpus path resolution.

Untested before this fix, and that was the highest-impact finding in review: a
typo'd or renamed artifact path made ``check-corpus`` scan an empty directory,
print "nothing to check", and exit 0 — reporting green while protecting
nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.corpus.config import DEFAULT_ARTIFACTS, DEFAULT_HOLDOUT, CorpusPaths, resolve
from services.corpus.errors import CorpusConfigError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def write_pyproject(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(body, encoding="utf-8")
    return root


# ── resolution ───────────────────────────────────────────────────────────────


def test_reads_configured_paths(tmp_path: Path) -> None:
    root = write_pyproject(
        tmp_path,
        '[tool.brandforge.corpus]\nartifacts = "out/arts"\nholdout = "out/hold"\n',
    )
    paths = resolve(root)
    assert paths.artifacts == root / "out/arts"
    assert paths.holdout == root / "out/hold"


def test_falls_back_to_defaults_without_a_section(tmp_path: Path) -> None:
    root = write_pyproject(tmp_path, '[project]\nname = "x"\n')
    paths = resolve(root)
    assert paths.artifacts == root / DEFAULT_ARTIFACTS
    assert paths.holdout == root / DEFAULT_HOLDOUT


def test_falls_back_to_defaults_without_a_pyproject(tmp_path: Path) -> None:
    assert resolve(tmp_path).artifacts == tmp_path / DEFAULT_ARTIFACTS


def test_partial_configuration_keeps_the_other_default(tmp_path: Path) -> None:
    root = write_pyproject(tmp_path, '[tool.brandforge.corpus]\nartifacts = "only/arts"\n')
    paths = resolve(root)
    assert paths.artifacts == root / "only/arts"
    assert paths.holdout == root / DEFAULT_HOLDOUT


# ── rejected configurations ──────────────────────────────────────────────────


def test_empty_path_is_rejected(tmp_path: Path) -> None:
    root = write_pyproject(tmp_path, '[tool.brandforge.corpus]\nartifacts = ""\n')
    with pytest.raises(CorpusConfigError, match="empty"):
        resolve(root)


def test_absolute_path_is_rejected(tmp_path: Path) -> None:
    """An absolute path would escape the repo and defeat reproducibility."""
    root = write_pyproject(tmp_path, '[tool.brandforge.corpus]\nholdout = "/etc/holdout"\n')
    with pytest.raises(CorpusConfigError, match="repository-relative"):
        resolve(root)


# ── the absent/empty distinction ─────────────────────────────────────────────


def test_absent_artifact_dir_is_a_configuration_error(tmp_path: Path) -> None:
    paths = CorpusPaths(artifacts=tmp_path / "nope", holdout=tmp_path / "h")
    with pytest.raises(CorpusConfigError, match="does not exist"):
        paths.require_artifacts_dir()


def test_empty_artifact_dir_is_fine(tmp_path: Path) -> None:
    """Nothing built yet is a legitimate state and must not fail."""
    artifacts = tmp_path / "arts"
    artifacts.mkdir()
    CorpusPaths(artifacts=artifacts, holdout=tmp_path / "h").require_artifacts_dir()


def test_artifact_path_that_is_a_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "arts"
    target.write_text("", encoding="utf-8")
    with pytest.raises(CorpusConfigError, match="not a directory"):
        CorpusPaths(artifacts=target, holdout=tmp_path / "h").require_artifacts_dir()


# ── the real repository ──────────────────────────────────────────────────────


def test_this_repository_is_correctly_configured() -> None:
    """Catches a rename or typo landing in pyproject.toml.

    Without this, the configured path could drift away from the directory the
    pipeline actually writes to and nothing would notice — which is precisely
    the vacuous-pass failure.
    """
    resolve(REPO_ROOT).require_artifacts_dir()


def test_the_tracked_gitkeep_exists() -> None:
    """The marker that makes the absent/empty distinction possible at all."""
    assert (resolve(REPO_ROOT).artifacts / ".gitkeep").is_file()
