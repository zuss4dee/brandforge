"""Corpus error hierarchy.

Every corpus validation failure derives from :class:`CorpusError`, so a caller
can catch "a corpus guard rejected this" as one thing. Before this existed the
licence gate raised ``LicenceViolationError`` while the autophagy gate raised a
bare ``ValueError`` — two names for one class of event, which meant a test
asserting the former was silently exercising a different code path than it
claimed.

Dataclass ``__post_init__`` argument validation deliberately still raises
``ValueError``: those are ordinary bad-constructor-argument errors, not corpus
guard rejections, and conflating them would make ``except CorpusError`` mean
less than it does now.
"""

from __future__ import annotations


class CorpusError(Exception):
    """Base for every corpus acquisition, validation, or guard failure."""


# ── guard rejections ─────────────────────────────────────────────────────────


class GuardViolationError(CorpusError):
    """A corpus guard refused an operation. See ADR-0019."""


class LicenceViolationError(GuardViolationError):
    """A provider was used for something its licence does not permit."""


class AutophagyError(GuardViolationError):
    """Internally generated names reached induction.

    Distinct from :class:`LicenceViolationError` because it catches a case the
    licence gate cannot: an internal provider carrying a *permissive* licence.
    That is the misconfiguration this gate exists for, so it needs its own type
    and its own test.
    """


class HoldoutSealError(GuardViolationError):
    """The holdout does not match its seal, or is unusable."""


# ── acquisition and schema ───────────────────────────────────────────────────


class AcquisitionError(CorpusError):
    """Acquisition failed. Carries a human-actionable cause, never a bare retry."""


class SnapshotValidationError(CorpusError):
    """A snapshot failed integrity or plausibility checks."""


class SchemaContractError(CorpusError):
    """A source's schema does not match what the pipeline expects."""


class ArtifactSchemaError(CorpusError):
    """A persisted corpus artifact is malformed or of an unsupported schema."""


class CorpusConfigError(CorpusError):
    """Corpus paths are misconfigured.

    Raised rather than tolerated because a guard pointed at the wrong directory
    finds nothing, reports success, and protects nothing.
    """
