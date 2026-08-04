"""Corpus guards — enforcement for ADR-0019 and the M1.0 holdout strategy.

Three checks, run against **persisted artifacts** rather than against the code
that produced them. That distinction is the point: an artifact can be inspected
long after the pipeline run that emitted it, and cannot lie about which
providers it drew from.

1. **Licence gate** — every provider contributing to an artifact must be
   permitted that use. ``unknown`` permits nothing.
2. **Autophagy gate** — no internal provider may feed induction, under any
   blend. Inducing on our own output is model collapse; it presents as rising
   typicality and falling diversity, which reads like improvement.
3. **Holdout contamination** — no induction artifact may contain a held-out
   name, under exact, phonetic, or edit-distance-1 matching. The holdout's own
   seal is verified first, because otherwise the guard checks a file that the
   guard's own failure tempts you to edit.

Green when there is nothing to check: an empty artifact directory means no
corpus has been built yet. The checks bite the moment one exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services.corpus.config import CorpusPaths, resolve
from services.corpus.errors import CorpusConfigError, HoldoutSealError
from services.corpus.holdout import HoldoutIndex, load_holdout
from services.corpus.licensing import permits
from services.corpus.pipeline import CorpusArtifact
from services.corpus.providers import KNOWN_PROVIDERS
from services.corpus.types import ProviderKind, Use


def check_licences(artifact: CorpusArtifact) -> list[str]:
    """Every contributing provider must be permitted this artifact's use."""
    problems: list[str] = []
    for pid in artifact.provider_ids:
        descriptor = KNOWN_PROVIDERS.get(pid)
        if descriptor is None:
            problems.append(
                f"{artifact.artifact_id}: unknown provider {pid!r} — cannot verify its "
                f"licence, so the artifact cannot be shown to be permitted"
            )
            continue
        if not permits(descriptor, artifact.use):
            problems.append(
                f"{artifact.artifact_id}: {pid!r} (licence={descriptor.licence.value}) "
                f"may not be used for {artifact.use.value!r}"
            )
    return problems


def check_autophagy(artifact: CorpusArtifact) -> list[str]:
    """No internal provider may feed induction."""
    if artifact.use is not Use.INDUCTION:
        return []
    problems: list[str] = []
    for pid in artifact.provider_ids:
        descriptor = KNOWN_PROVIDERS.get(pid)
        if descriptor is not None and descriptor.kind is ProviderKind.INTERNAL:
            problems.append(
                f"{artifact.artifact_id}: internal provider {pid!r} is feeding induction — "
                f"this is model collapse (ADR-0019 §0.3)"
            )
    return problems


def check_holdout(artifact: CorpusArtifact, index: HoldoutIndex | None) -> list[str]:
    """No induction artifact may contain a held-out name, under any of three keys."""
    if artifact.use is not Use.INDUCTION:
        return []
    if index is None:
        return [
            f"{artifact.artifact_id}: an induction artifact exists but no sealed holdout "
            f"was found. Induction without an exclusion set risks an evaluation that "
            f"measures memorisation and still returns a plausible number."
        ]

    hits = [(n, key) for n in artifact.names if (key := index.contamination_key(n)) is not None]
    return [
        f"{artifact.artifact_id}: {len(hits)} held-out name(s) present in an induction "
        f"artifact — e.g. {', '.join(f'{n!r} ({k})' for n, k in hits[:5])}"
        for _ in [1]
        if hits
    ]


def run_check(paths_config: CorpusPaths) -> int:
    # An absent artifact directory is a misconfiguration, not an empty corpus.
    # Without this distinction a typo'd path makes every check below vacuous:
    # nothing found, "nothing to check", exit 0, forever.
    try:
        paths_config.require_artifacts_dir()
    except CorpusConfigError as error:
        print("check-corpus: CONFIGURATION ERROR\n")
        print(f"  ✗ {error}")
        return 1

    artifacts_dir, holdout_dir = paths_config.artifacts, paths_config.holdout

    try:
        loaded = load_holdout(holdout_dir)
    except HoldoutSealError as error:
        print("check-corpus: HOLDOUT SEAL FAILURE\n")
        print(f"  ✗ {error}")
        return 1

    index = HoldoutIndex.build(loaded[0]) if loaded else None
    if loaded:
        print(f"check-corpus: holdout sealed, {len(loaded[0])} names, verified")

    paths = sorted(artifacts_dir.glob("*.json"))
    if not paths:
        print(f"check-corpus: no artifacts under {artifacts_dir} — nothing built yet")
        return 0

    problems: list[str] = []
    for path in paths:
        artifact = CorpusArtifact.from_path(path)
        problems.extend(check_licences(artifact))
        problems.extend(check_autophagy(artifact))
        problems.extend(check_holdout(artifact, index))

    if problems:
        print("check-corpus: CORPUS GUARD VIOLATIONS\n")
        for problem in problems:
            print(f"  ✗ {problem}")
        print("\nSee docs/adr/0019-corpus-provider-abstraction.md\n")
        return 1

    noun = "artifact" if len(paths) == 1 else "artifacts"
    print(f"check-corpus: {len(paths)} {noun} OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-corpus",
        description="Licence, autophagy and holdout guards for corpus artifacts.",
    )
    parser.add_argument("--artifacts", type=Path, default=None)
    parser.add_argument("--holdout", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        configured = resolve(Path.cwd())
    except CorpusConfigError as error:
        print("check-corpus: CONFIGURATION ERROR\n")
        print(f"  ✗ {error}")
        return 1

    return run_check(
        CorpusPaths(
            artifacts=args.artifacts if args.artifacts is not None else configured.artifacts,
            holdout=args.holdout if args.holdout is not None else configured.holdout,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
