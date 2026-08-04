"""USPTO Trademark Case Files provider (ADR-0016, ADR-0018).

Verified 2026-08-04 (docs/design/06-m1-0-corpus-assembly.md §1):

* Licence is Public Domain Mark 1.0 — no constraint reaches derived models.
* 12.7M applications/registrations, Oct 1870 to Mar 2024, annual cadence.
* ``bulkdata.uspto.gov`` no longer resolves; the Developer Hub is decommissioned.
* The API host is ``api.uspto.gov`` (``data.uspto.gov`` serves the SPA for every
  path, so requests there return HTML rather than a 404).
* Authentication is the ``X-API-KEY`` header — verified by the 401→403
  transition under that header and not under ``api-key`` or ``Authorization``.

**Deliberately unverified and therefore not hardcoded:** the exact CSV column
names (USPTO's documentation uses prose — "the mark identification character
field" — not column names) and the exact ``mark_drawing_code`` values. Both are
resolved against the real header at ingest and fail loudly on mismatch. A
guessed column name yields an all-null column, an empty corpus, and no error —
which is why resolution is explicit rather than a ``dict.get``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

from services.corpus.errors import AcquisitionError, SchemaContractError
from services.corpus.protocol import Snapshot
from services.corpus.types import (
    CorpusRecord,
    LicenceClass,
    NameStatus,
    ProviderDescriptor,
    ProviderKind,
)

DESCRIPTOR: Final[ProviderDescriptor] = ProviderDescriptor(
    id="uspto.case_files",
    name="USPTO Trademark Case Files Dataset",
    kind=ProviderKind.REGISTRY,
    licence=LicenceClass.PUBLIC_DOMAIN,
    jurisdiction="US",
    locale="en-US",
    cadence="annual",
    expected_scale=12_700_000,
    # Tier 3: exhaustive but mostly unremarkable. Anyone can register a mark,
    # so the register teaches what is legally filed, not what is good.
    trust_tier=3,
    attribution_required=True,
    attribution="Graham, Stuart J.H., Marco, Alan C., Miller, Richard (2018). "
    "The USPTO Trademark Case Files Dataset.",
)

API_HOST: Final[str] = "https://api.uspto.gov"
API_KEY_HEADER: Final[str] = "X-API-KEY"
API_KEY_ENV: Final[str] = "BRANDFORGE_USPTO_API_KEY"

#: Standard-character marks — the registration is for the *word*, not a logo.
#: Documentation references "4" (filing date before 2 Nov 2003) and "5".
#: Treated as a hypothesis: the observed distribution is asserted at validation
#: time against the documented ~64% share.
STANDARD_CHARACTER_CODES: Final[frozenset[str]] = frozenset({"4", "5"})
EXPECTED_STANDARD_CHARACTER_SHARE: Final[float] = 0.642

#: Candidate column names, most likely first. Resolution requires exactly one
#: match in the real header — never a silent fallback.
COLUMN_CANDIDATES: Final[dict[str, tuple[str, ...]]] = {
    "mark_text": ("mark_id_char", "mark_identification", "mark_id_characters"),
    "drawing_code": ("mark_draw_cd", "mark_drawing_code", "draw_cd"),
    "serial": ("serial_no", "serial_number"),
    "filing_year": ("filing_dt", "filing_date"),
    "status": ("status_cd", "status_code"),
    "live_flag": ("live_dead_ind", "live_dead_indicator"),
}


def resolve_columns(header: Sequence[str]) -> dict[str, str]:
    """Bind logical fields to real column names, or fail with the actual header.

    Ambiguity is an error too: two candidates matching means the source changed
    shape in a way we have not understood, and guessing between them would be
    the same silent-wrongness failure the explicit resolution exists to prevent.
    """
    available = {h.strip().casefold(): h for h in header}
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for logical, candidates in COLUMN_CANDIDATES.items():
        matches = [available[c] for c in candidates if c in available]
        if len(matches) == 1:
            resolved[logical] = matches[0]
        elif not matches:
            missing.append(f"{logical} (tried: {', '.join(candidates)})")
        else:
            msg = (
                f"ambiguous columns for {logical!r}: {matches}. "
                f"The source schema changed; update COLUMN_CANDIDATES deliberately."
            )
            raise SchemaContractError(msg)

    if missing:
        msg = (
            f"USPTO case_file header does not contain: {'; '.join(missing)}.\n"
            f"Actual header: {list(header)}\n"
            f"Column names were never verified against the real file (see "
            f"docs/design/06-m1-0-corpus-assembly.md §1.3). Update COLUMN_CANDIDATES."
        )
        raise SchemaContractError(msg)

    return resolved


def _year(value: str) -> int | None:
    digits = value.strip()[:4]
    return int(digits) if digits.isdigit() else None


def _status(row: dict[str, str], columns: dict[str, str]) -> NameStatus:
    flag = row.get(columns["live_flag"], "").strip().upper()
    if flag in {"L", "LIVE", "1", "Y"}:
        return NameStatus.LIVE
    if flag in {"D", "DEAD", "0", "N"}:
        return NameStatus.DEAD
    return NameStatus.UNKNOWN


class UsptoCaseFilesProvider:
    """Reads the ``case_file`` table of the Trademark Case Files Dataset."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        return DESCRIPTOR

    def acquire(self, destination: Path) -> Snapshot:
        """Not yet implemented — blocked on a USPTO API key.

        Deliberately raises rather than stubbing a download. The Open Data
        Portal has required a USPTO.gov account since 18 June 2026, and the
        product's real download URL cannot be resolved without a key, so any
        implementation written now would be guesswork dressed as code.
        """
        msg = (
            f"USPTO acquisition requires an Open Data Portal API key.\n"
            f"  1. Create a USPTO.gov account and register for the Open Data Portal\n"
            f"  2. Obtain an API key (header: {API_KEY_HEADER}, host: {API_HOST})\n"
            f"  3. Export it as {API_KEY_ENV}\n"
            f"Then the download URL must be resolved via the ODP product API — it is "
            f"not hardcoded because the legacy bulkdata.uspto.gov host no longer exists.\n"
            f"See docs/design/06-m1-0-corpus-assembly.md §8."
        )
        raise AcquisitionError(msg)

    def extract(self, snapshot: Snapshot) -> Iterator[CorpusRecord]:
        """Stream standard-character marks from an extracted ``case_file`` CSV.

        Streaming rather than materialising: the table runs to millions of rows.
        The standard-character filter is source-specific and therefore lives
        here rather than in shared normalisation.
        """
        with snapshot.location.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                msg = f"{snapshot.location}: empty file, no CSV header"
                raise SchemaContractError(msg)
            columns = resolve_columns(reader.fieldnames)

            for row in reader:
                # S1 — standard-character marks only. The registration must be
                # for the word, not a logo.
                if row.get(columns["drawing_code"], "").strip() not in STANDARD_CHARACTER_CODES:
                    continue

                text = row.get(columns["mark_text"], "").strip()
                if not text:
                    continue

                yield CorpusRecord(
                    text=text,
                    provider_id=DESCRIPTOR.id,
                    source_ref=row.get(columns["serial"], "").strip(),
                    status=_status(row, columns),
                    first_seen_year=_year(row.get(columns["filing_year"], "")),
                    source_fields={"drawing_code": row.get(columns["drawing_code"], "").strip()},
                )
