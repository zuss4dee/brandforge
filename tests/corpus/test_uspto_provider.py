"""USPTO provider tests, focused on the schema contract.

The CSV column names were never verified against the real file — USPTO's
documentation describes fields in prose ("the mark identification character
field"), not by column name. A guessed name would yield an all-null column, an
empty corpus, and **no error at all**. These tests exist because that failure
is silent.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from services.corpus.errors import SchemaContractError
from services.corpus.protocol import Snapshot
from services.corpus.providers.uspto import (
    DESCRIPTOR,
    STANDARD_CHARACTER_CODES,
    UsptoCaseFilesProvider,
    resolve_columns,
)
from services.corpus.types import NameStatus

HEADER = ["serial_no", "mark_id_char", "mark_draw_cd", "filing_dt", "status_cd", "live_dead_ind"]

ROWS = [
    # standard character, live
    ["78000001", "CORVANE", "4", "20110402", "700", "L"],
    ["78000002", "LUMERIS", "5", "20190115", "700", "L"],
    # design mark — rejected by the source-specific filter
    ["78000003", "SWOOSH LOGO", "2", "20050101", "700", "L"],
    # standard character, dead
    ["78000004", "ZEPRIX", "5", "20200601", "606", "D"],
    # standard character but no text
    ["78000005", "", "4", "20200601", "700", "L"],
]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Snapshot:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return Snapshot(
        provider_id=DESCRIPTOR.id,
        content_hash="sha256:test",
        location=path,
        byte_size=path.stat().st_size,
        vintage="2023",
    )


# ── schema contract ──────────────────────────────────────────────────────────


def test_resolves_the_documented_header() -> None:
    resolved = resolve_columns(HEADER)
    assert resolved["mark_text"] == "mark_id_char"
    assert resolved["drawing_code"] == "mark_draw_cd"


def test_resolution_is_case_insensitive() -> None:
    resolved = resolve_columns([c.upper() for c in HEADER])
    assert resolved["mark_text"] == "MARK_ID_CHAR"


def test_alternate_candidate_names_resolve() -> None:
    """USPTO may rename between annual releases; candidates cover known variants."""
    header = [
        "serial_number",
        "mark_identification",
        "mark_drawing_code",
        "filing_date",
        "status_code",
        "live_dead_indicator",
    ]
    assert resolve_columns(header)["mark_text"] == "mark_identification"


def test_missing_column_fails_loudly_and_shows_the_real_header() -> None:
    """The whole point: never a silent fallback to None."""
    broken = [c for c in HEADER if c != "mark_id_char"]
    with pytest.raises(SchemaContractError) as excinfo:
        resolve_columns(broken)

    message = str(excinfo.value)
    assert "mark_text" in message
    assert "mark_id_char" in message  # what we tried
    assert "status_cd" in message  # the actual header, for diagnosis
    assert "06-m1-0-corpus-assembly" in message  # where the caveat is documented


def test_ambiguous_columns_fail_rather_than_guess() -> None:
    """Two matches means the source changed shape in a way we have not understood."""
    ambiguous = [*HEADER, "mark_identification"]
    with pytest.raises(SchemaContractError, match="ambiguous"):
        resolve_columns(ambiguous)


def test_empty_file_fails_with_a_schema_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    snap = Snapshot(DESCRIPTOR.id, "sha256:0", path, 0, "2023")
    with pytest.raises(SchemaContractError, match="no CSV header"):
        list(UsptoCaseFilesProvider().extract(snap))


# ── extraction behaviour ─────────────────────────────────────────────────────


def test_only_standard_character_marks_are_extracted(tmp_path: Path) -> None:
    """S1 — the registration must be for the word, not a logo."""
    snap = write_csv(tmp_path / "case_file.csv", HEADER, ROWS)
    texts = [r.text for r in UsptoCaseFilesProvider().extract(snap)]
    assert texts == ["CORVANE", "LUMERIS", "ZEPRIX"]
    assert "SWOOSH LOGO" not in texts


def test_standard_character_codes_match_the_documentation() -> None:
    """Docs reference '4' (pre 2 Nov 2003) and '5'. Treated as a hypothesis."""
    assert set(STANDARD_CHARACTER_CODES) == {"4", "5"}


def test_status_and_year_are_mapped(tmp_path: Path) -> None:
    snap = write_csv(tmp_path / "case_file.csv", HEADER, ROWS)
    by_text = {r.text: r for r in UsptoCaseFilesProvider().extract(snap)}
    assert by_text["CORVANE"].status is NameStatus.LIVE
    assert by_text["CORVANE"].first_seen_year == 2011
    assert by_text["ZEPRIX"].status is NameStatus.DEAD


def test_malformed_date_yields_none_not_a_crash(tmp_path: Path) -> None:
    rows = [["78000001", "CORVANE", "4", "not-a-date", "700", "L"]]
    snap = write_csv(tmp_path / "case_file.csv", HEADER, rows)
    assert next(iter(UsptoCaseFilesProvider().extract(snap))).first_seen_year is None


def test_unrecognised_live_flag_becomes_unknown_not_live(tmp_path: Path) -> None:
    """Defaulting an unknown status to LIVE would silently inflate quality signals."""
    rows = [["78000001", "CORVANE", "4", "20110402", "700", "?"]]
    snap = write_csv(tmp_path / "case_file.csv", HEADER, rows)
    assert next(iter(UsptoCaseFilesProvider().extract(snap))).status is NameStatus.UNKNOWN


def test_descriptor_records_the_verified_facts() -> None:
    assert DESCRIPTOR.expected_scale == 12_700_000
    assert DESCRIPTOR.cadence == "annual"
    assert DESCRIPTOR.jurisdiction == "US"
