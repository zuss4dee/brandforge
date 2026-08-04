"""Conformance suite — every corpus provider must pass this (ADR-0019 §4).

An interface validated against one implementation is a guess. This suite is
what a new provider is held to, and it is deliberately behavioural rather than
structural: satisfying the Protocol's type signature says nothing about
whether a provider streams, declares its licence honestly, or maps
deterministically.

To add a provider: add it to ``PROVIDERS`` and make this pass.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from services.corpus.errors import AcquisitionError
from services.corpus.licensing import permitted_uses
from services.corpus.protocol import CorpusProvider, Snapshot
from services.corpus.providers.fake import FakeProvider
from services.corpus.providers.uspto import UsptoCaseFilesProvider
from services.corpus.types import LicenceClass, ProviderKind, Use

#: Providers under conformance. Network-dependent acquisition is exercised
#: separately — see ``test_acquire_*`` below.
PROVIDERS: list[CorpusProvider] = [FakeProvider(), UsptoCaseFilesProvider()]
OFFLINE_PROVIDERS: list[CorpusProvider] = [FakeProvider()]


@pytest.fixture(params=PROVIDERS, ids=lambda p: p.descriptor.id)
def provider(request: pytest.FixtureRequest) -> CorpusProvider:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=OFFLINE_PROVIDERS, ids=lambda p: p.descriptor.id)
def offline_provider(request: pytest.FixtureRequest) -> CorpusProvider:
    return request.param  # type: ignore[no-any-return]


# ── descriptor contract ──────────────────────────────────────────────────────


def test_satisfies_the_protocol(provider: CorpusProvider) -> None:
    assert isinstance(provider, CorpusProvider)


def test_descriptor_is_constant(provider: CorpusProvider) -> None:
    """Blending and licence gating both key off the descriptor; it must not drift."""
    assert provider.descriptor == provider.descriptor


def test_descriptor_declares_a_known_licence_and_kind(provider: CorpusProvider) -> None:
    assert isinstance(provider.descriptor.licence, LicenceClass)
    assert isinstance(provider.descriptor.kind, ProviderKind)


def test_licence_is_established(provider: CorpusProvider) -> None:
    """UNKNOWN permits nothing, so a shipped provider must have a real licence."""
    assert provider.descriptor.licence is not LicenceClass.UNKNOWN, (
        f"{provider.descriptor.id} has not established its licence and would contribute to nothing"
    )


def test_attribution_present_when_required(provider: CorpusProvider) -> None:
    d = provider.descriptor
    if d.attribution_required:
        assert d.attribution


def test_internal_providers_can_never_feed_induction(provider: CorpusProvider) -> None:
    """The autophagy guard, asserted at the provider level (ADR-0019 §0.3)."""
    if provider.descriptor.kind is ProviderKind.INTERNAL:
        assert Use.INDUCTION not in permitted_uses(provider.descriptor.licence)


# ── acquisition contract ─────────────────────────────────────────────────────


def test_acquire_returns_a_content_addressed_snapshot(
    offline_provider: CorpusProvider, tmp_path: Path
) -> None:
    snap = offline_provider.acquire(tmp_path / "raw.dat")
    assert snap.provider_id == offline_provider.descriptor.id
    assert snap.content_hash.startswith("sha256:")
    assert snap.byte_size > 0
    assert snap.location.exists()


def test_acquire_is_reproducible(offline_provider: CorpusProvider, tmp_path: Path) -> None:
    """Same source, same bytes, same hash — the basis of rebuilding a corpus later."""
    a = offline_provider.acquire(tmp_path / "a.dat")
    b = offline_provider.acquire(tmp_path / "b.dat")
    assert a.content_hash == b.content_hash


def test_blocked_acquisition_explains_itself(tmp_path: Path) -> None:
    """A provider that cannot acquire must say why and what to do about it."""
    with pytest.raises(AcquisitionError) as excinfo:
        UsptoCaseFilesProvider().acquire(tmp_path / "unused")

    message = str(excinfo.value)
    assert "X-API-KEY" in message
    assert "BRANDFORGE_USPTO_API_KEY" in message
    assert "api.uspto.gov" in message


# ── extraction contract ──────────────────────────────────────────────────────


def test_extract_streams(offline_provider: CorpusProvider, tmp_path: Path) -> None:
    """Registry sources run to millions of rows; extraction must not materialise."""
    snap = offline_provider.acquire(tmp_path / "raw.dat")
    assert isinstance(offline_provider.extract(snap), Iterator)


def test_extracted_records_are_well_formed(
    offline_provider: CorpusProvider, tmp_path: Path
) -> None:
    snap = offline_provider.acquire(tmp_path / "raw.dat")
    records = list(offline_provider.extract(snap))
    assert records
    for r in records:
        assert r.provider_id == offline_provider.descriptor.id
        assert r.text
        assert r.source_ref


def test_extraction_is_deterministic(offline_provider: CorpusProvider, tmp_path: Path) -> None:
    snap = offline_provider.acquire(tmp_path / "raw.dat")
    first = [r.text for r in offline_provider.extract(snap)]
    second = [r.text for r in offline_provider.extract(snap)]
    assert first == second


def test_extract_handles_an_empty_source(tmp_path: Path) -> None:
    empty = FakeProvider(names=())
    snap = empty.acquire(tmp_path / "empty.dat")
    assert list(empty.extract(snap)) == []


def test_providers_have_distinct_ids() -> None:
    ids = [p.descriptor.id for p in PROVIDERS]
    assert len(ids) == len(set(ids))


def test_snapshot_is_immutable(offline_provider: CorpusProvider, tmp_path: Path) -> None:
    snap = offline_provider.acquire(tmp_path / "raw.dat")
    with pytest.raises((AttributeError, TypeError)):
        snap.content_hash = "tampered"  # type: ignore[misc]
    assert isinstance(snap, Snapshot)
