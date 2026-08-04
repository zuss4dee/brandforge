# Verified Facts Ledger

External facts checked against primary sources, with the date and method. This exists so nobody re-verifies what is already known, and — more importantly — so **assumptions never harden into facts through repetition**.

**Rules.** A row belongs here only if it was checked against a *primary* source: the vendor's own documentation, an actual API response, a licence field. Third-party guides are leads, not evidence. Anything unverified goes in §3, never §1.

**Facts expire.** USPTO's access model changed twice in 2026. Re-verify before relying on anything with a stale date.

---

## 1. Verified

### USPTO — checked 2026-08-04

| Fact | Method | Confidence |
|---|---|---|
| Licence is **Public Domain Mark 1.0** (`creativecommons.org/publicdomain/mark/1.0`) — no constraint on derived models | data.gov catalog licence field for the ODP Bulk Datasets API | High |
| Trademark Case Files Dataset: **12.7M** records, **Oct 1870 – Mar 2024** | USPTO OCE dataset page | High |
| Formats: CSV **4.33 GB**, Stata **4.19 GB**; **annual** cadence; 2023 edition released 2025-09-03 | USPTO OCE dataset page | High |
| `case_file` = one row per registration/application, keyed by serial number | Official documentation PDF, §5.2.1 | High |
| Mark text lives in the **"mark identification character" field**; `mark_drawing_code` distinguishes standard-character / stylized / design / no-drawing | Official documentation PDF, §5.2.1.3 | High |
| **64.2%** of observations are standard-character drawings; **84.3%** contain any text | Documentation PDF, Table 2 | High |
| Citation requested: Graham, Marco & Miller (2018) | USPTO OCE dataset page | High |
| **ODP requires a USPTO.gov account since 2026-06-18** | USPTO news announcement | High |
| **API host is `api.uspto.gov`.** `data.uspto.gov` serves the SPA for *every* path, including `/api/...` — requests there return HTML, not a 404 | Direct request; observed `content_type: text/html` on all `data.uspto.gov` API paths | High |
| **Auth header is `X-API-KEY`** | Direct request: 401 with no header, **403** with an invalid `X-API-KEY`, 401 with `api-key` or `Authorization: Bearer`. The 401→403 transition under one header and not the others identifies the scheme | High |
| **`bulkdata.uspto.gov` no longer resolves** (DNS failure, not a redirect) | `curl` — `Could not resolve host` | High |
| Developer Hub decommissioned 2026-06-05; deep links **302 to the portal root**, not to the equivalent resource | Direct request to a `developer.uspto.gov/product/...` deep link | High |

> ⚠️ **Consequence worth repeating:** almost every third-party guide, tutorial, and GitHub scraper for USPTO bulk data points at `bulkdata.uspto.gov`. Following the consensus answer would have produced code that could never have worked. **Any USPTO implementation guide predating mid-2026 is unreliable on access mechanics.**

---

## 2. Falsified

Assumptions that were checked and found wrong. Kept so they are not quietly re-adopted.

| Assumption | Reality | Where corrected |
|---|---|---|
| USPTO bulk data is freely downloadable without registration | Requires a USPTO.gov account and an API key since 2026-06-18 | [ADR-0016 note](../adr/0016-uspto-brand-corpus.md) |
| One USPTO ingestion pipeline serves both M1 and M7 | Two distinct products with different cadences — annual Case Files vs daily XML | [ADR-0018](../adr/0018-case-files-over-raw-xml.md) |
| `bulkdata.uspto.gov` is the bulk download host | Host does not exist | [M1.0 §1.2](../design/06-m1-0-corpus-assembly.md) |

---

## 3. Unverified — treat as assumptions

**None of these may be hardcoded.** Each is resolved against reality at runtime and fails loudly on mismatch.

| Assumption | Current handling | Resolves when |
|---|---|---|
| CSV column names (`mark_id_char`, `mark_draw_cd`, …) — docs use prose, not column names | `resolve_columns()` matches candidates against the real header; raises `SchemaContractError` on missing *or ambiguous* match, printing the actual header | API key obtained |
| `mark_drawing_code` standard-character values are `{"4", "5"}` | Constant, cross-checked at validation against the documented ~64% share | API key obtained |
| Case Files download URL under the new ODP | Resolved via the ODP product API, never hardcoded | API key obtained |
| Whether the Case Files bundle needs the API key too | Assumed yes | API key obtained |
| ODP rate limits and quotas | Unknown; back off conservatively | API key obtained |

---

## 4. Not yet investigated

| Question | Blocks |
|---|---|
| Whether `.com`/`.net` zone access runs through ICANN CZDS or a separate Verisign agreement | M3 — [runbook](../ops/zone-file-access.md) flags this as unverified |
| ccTLD availability data sources (`.io`, `.ai`, `.co` publish no zone files) | M3 |
| EUIPO and Companies House bulk access and licensing | Future corpus providers |
