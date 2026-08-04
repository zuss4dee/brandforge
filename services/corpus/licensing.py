"""Licence gating — the mechanical half of ADR-0019.

Permitted uses are derived from the licence class **here, in code**. They are
never declared per provider. A provider author cannot grant themselves
induction rights by editing a YAML field; granting an exception means editing
this table, which is a visible, reviewable, deliberate act.

Two properties matter more than the table itself:

* ``UNKNOWN`` permits nothing. A provider whose licence has not been
  established contributes to nothing at all, loudly, rather than defaulting
  into induction quietly.
* ``INTERNAL_GENERATED`` never permits induction. Inducing phonotactic weights
  from names we generated amplifies our own priors, which then feed the next
  induction — autophagy. It presents as rising typicality and falling
  diversity, which is easy to misread as improvement.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from services.corpus.errors import LicenceViolationError
from services.corpus.types import LicenceClass, ProviderDescriptor, Use

_ALL: Final[frozenset[Use]] = frozenset(Use)

#: The gate. Read-only at runtime so it cannot be monkey-patched into permissiveness.
PERMITTED_USES: Final[MappingProxyType[LicenceClass, frozenset[Use]]] = MappingProxyType(
    {
        LicenceClass.PUBLIC_DOMAIN: _ALL,
        LicenceClass.OPEN_ATTRIBUTION: _ALL,
        # Commercial licences commonly restrict derived-model use. Until legal
        # review clears a specific source, it may inform counts but not weights.
        LicenceClass.COMMERCIAL_LICENSED: frozenset(
            {Use.SATURATION, Use.NOVELTY_REFERENCE, Use.DISPLAY}
        ),
        LicenceClass.TOS_RESTRICTED: frozenset({Use.NOVELTY_REFERENCE, Use.DISPLAY}),
        LicenceClass.INTERNAL_GENERATED: frozenset({Use.SATURATION, Use.NOVELTY_REFERENCE}),
        LicenceClass.UNKNOWN: frozenset(),
    }
)


def permitted_uses(licence: LicenceClass) -> frozenset[Use]:
    """Uses allowed under ``licence``. Unmapped classes permit nothing."""
    return PERMITTED_USES.get(licence, frozenset())


def permits(descriptor: ProviderDescriptor, use: Use) -> bool:
    return use in permitted_uses(descriptor.licence)


def require(descriptor: ProviderDescriptor, use: Use) -> None:
    """Assert a provider may be used this way, or explain precisely why not."""
    if permits(descriptor, use):
        return
    allowed = sorted(u.value for u in permitted_uses(descriptor.licence))
    msg = (
        f"{descriptor.id!r} (licence={descriptor.licence.value}) may not be used for "
        f"{use.value!r}. Permitted: {allowed or ['nothing']}. "
        f"See docs/adr/0019-corpus-provider-abstraction.md"
    )
    raise LicenceViolationError(msg)


def induction_eligible(descriptors: dict[str, ProviderDescriptor]) -> frozenset[str]:
    """Provider ids permitted to feed induction — the licence gate's positive form."""
    return frozenset(pid for pid, d in descriptors.items() if permits(d, Use.INDUCTION))
