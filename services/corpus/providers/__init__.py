"""Corpus provider implementations and the descriptor registry.

``KNOWN_PROVIDERS`` is what lets ``tools/check_corpus.py`` validate a persisted
artifact: the artifact records provider ids, and the guard needs their declared
licences to decide whether the artifact was legitimately built. A provider id
present in an artifact but absent here fails the check — an artifact from an
unknown source cannot be shown to be permitted.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from services.corpus.providers.uspto import DESCRIPTOR as USPTO_CASE_FILES
from services.corpus.types import ProviderDescriptor

KNOWN_PROVIDERS: Final[MappingProxyType[str, ProviderDescriptor]] = MappingProxyType(
    {USPTO_CASE_FILES.id: USPTO_CASE_FILES}
)

__all__ = ["KNOWN_PROVIDERS", "USPTO_CASE_FILES"]
