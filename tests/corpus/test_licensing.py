"""Licence gating tests (ADR-0019 §2).

The two properties that matter most are the fail-closed default and the
autophagy prohibition. Both are asserted directly rather than inferred from
the table, so a well-meaning edit to ``PERMITTED_USES`` fails here loudly.
"""

from __future__ import annotations

import pytest

from services.corpus.errors import LicenceViolationError
from services.corpus.licensing import (
    PERMITTED_USES,
    induction_eligible,
    permits,
    permitted_uses,
    require,
)
from services.corpus.providers.fake import FakeProvider
from services.corpus.providers.uspto import DESCRIPTOR as USPTO
from services.corpus.types import LicenceClass, ProviderDescriptor, ProviderKind, Use


def descriptor(licence: LicenceClass, pid: str = "p") -> ProviderDescriptor:
    return ProviderDescriptor(id=pid, name=pid, kind=ProviderKind.REGISTRY, licence=licence)


# ── the two load-bearing properties ──────────────────────────────────────────


def test_unknown_licence_permits_nothing() -> None:
    """Fail closed. A provider with an unestablished licence contributes to nothing."""
    assert permitted_uses(LicenceClass.UNKNOWN) == frozenset()
    for use in Use:
        assert not permits(descriptor(LicenceClass.UNKNOWN), use)


def test_internal_generated_never_permits_induction() -> None:
    """The autophagy guard. Inducing from our own output is model collapse."""
    assert Use.INDUCTION not in permitted_uses(LicenceClass.INTERNAL_GENERATED)
    with pytest.raises(LicenceViolationError):
        require(descriptor(LicenceClass.INTERNAL_GENERATED), Use.INDUCTION)


def test_no_licence_class_is_unmapped() -> None:
    """An unmapped class silently permits nothing; better to notice at test time."""
    assert set(PERMITTED_USES) == set(LicenceClass)


# ── per-class behaviour ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("licence", "use", "allowed"),
    [
        (LicenceClass.PUBLIC_DOMAIN, Use.INDUCTION, True),
        (LicenceClass.OPEN_ATTRIBUTION, Use.INDUCTION, True),
        (LicenceClass.COMMERCIAL_LICENSED, Use.INDUCTION, False),
        (LicenceClass.COMMERCIAL_LICENSED, Use.SATURATION, True),
        (LicenceClass.TOS_RESTRICTED, Use.INDUCTION, False),
        (LicenceClass.TOS_RESTRICTED, Use.SATURATION, False),
        (LicenceClass.TOS_RESTRICTED, Use.NOVELTY_REFERENCE, True),
        (LicenceClass.INTERNAL_GENERATED, Use.SATURATION, True),
    ],
)
def test_permission_matrix(licence: LicenceClass, use: Use, allowed: bool) -> None:
    assert permits(descriptor(licence), use) is allowed


def test_require_passes_silently_when_permitted() -> None:
    require(descriptor(LicenceClass.PUBLIC_DOMAIN), Use.INDUCTION)


def test_violation_message_names_the_provider_and_the_alternatives() -> None:
    with pytest.raises(LicenceViolationError) as excinfo:
        require(descriptor(LicenceClass.COMMERCIAL_LICENSED, "crunchbase"), Use.INDUCTION)

    message = str(excinfo.value)
    assert "crunchbase" in message
    assert "induction" in message
    assert "saturation" in message  # tells you what you CAN do
    assert "0019" in message  # points at the ADR


# ── the gate applied to a set of providers ───────────────────────────────────


def test_induction_eligible_filters_correctly() -> None:
    providers = {
        "uspto": USPTO,
        "crunchbase": descriptor(LicenceClass.COMMERCIAL_LICENSED, "crunchbase"),
        "internal": descriptor(LicenceClass.INTERNAL_GENERATED, "internal"),
        "github": descriptor(LicenceClass.TOS_RESTRICTED, "github"),
        "yc": descriptor(LicenceClass.OPEN_ATTRIBUTION, "yc"),
    }
    assert induction_eligible(providers) == frozenset({"uspto", "yc"})


def test_the_permission_table_is_read_only() -> None:
    """It must not be monkey-patchable into permissiveness at runtime."""
    with pytest.raises(TypeError):
        PERMITTED_USES[LicenceClass.UNKNOWN] = frozenset(Use)  # type: ignore[index]


# ── real providers ───────────────────────────────────────────────────────────


def test_uspto_may_feed_induction() -> None:
    """Verified 2026-08-04: Public Domain Mark 1.0 — the basis of ADR-0016."""
    assert USPTO.licence is LicenceClass.PUBLIC_DOMAIN
    assert permits(USPTO, Use.INDUCTION)


def test_uspto_requires_attribution() -> None:
    assert USPTO.attribution_required
    assert USPTO.attribution and "Graham" in USPTO.attribution


def test_a_restricted_fake_provider_is_gated() -> None:
    restricted = FakeProvider(provider_id="fake.restricted", licence=LicenceClass.TOS_RESTRICTED)
    assert not permits(restricted.descriptor, Use.INDUCTION)
