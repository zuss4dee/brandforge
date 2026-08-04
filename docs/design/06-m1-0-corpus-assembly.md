# M1.0 — Corpus Assembly

**Status:** Approved v1.0 · **Date:** 2026-08-04
**Blocks:** M1.1–M1.7 (templates, weights, typicality, saturation, novelty distance all induce from this)
**Related:** [ADR-0013](../adr/0013-typicality-distinctiveness-objective.md) · [ADR-0016](../adr/0016-uspto-brand-corpus.md) · [Generation Engine](03-generation-engine.md)

---

## 1. Verification results

Everything below was checked against primary sources on 2026-08-04. **Three of ADR-0016's assumptions were wrong.**

### 1.1 Confirmed

| Assumption | Status | Evidence |
|---|---|---|
| Public domain, no licence constraint on derived models | ✅ **Confirmed** | data.gov records the licence for the ODP Bulk Datasets API as `https://creativecommons.org/publicdomain/mark/1.0` (Public Domain Mark 1.0) |
| Large enough for phoneme-level induction | ✅ **Confirmed** | 12.7M applications/registrations, Oct 1870 – Mar 2024 |
| Substantial cleaning required | ✅ **Confirmed**, and now quantified | Only 64.2% are standard-character drawings; 84.3% contain any text at all |

USPTO requests a citation (Graham, Marco & Miller, 2018). Public Domain Mark imposes no legal obligation, but we will honour it in documentation regardless.

### 1.2 Falsified — and these change the plan

**❌ "Freely downloadable" is no longer true without registration.**

The USPTO Open Data Portal has required a USPTO.gov account **since 18 June 2026** — seven weeks ago. I confirmed the API surface directly:

```
https://api.uspto.gov/api/v1/datasets/products/search   →  401 {"message":"Unauthorized"}
   with header  X-API-KEY: <invalid>                    →  403 {"message":"Forbidden"}
   with header  api-key / Authorization: Bearer         →  401 (header not recognised)
```

The 401→403 transition under `X-API-KEY` and not under the others identifies the auth scheme conclusively. **An API key is mandatory and is a prerequisite for M1.0**, not an implementation detail.

Note also that `data.uspto.gov` serves the single-page app for *every* path including `/api/...`; the real API host is **`api.uspto.gov`**. Anything written against `data.uspto.gov/api/...` will silently receive HTML instead of JSON.

**❌ The legacy bulk host is gone, not redirected.**

```
bulkdata.uspto.gov                    →  DNS does not resolve
developer.uspto.gov/product/<deep>    →  302 to https://data.uspto.gov/  (portal root)
```

`bulkdata.uspto.gov` — the host cited by essentially every third-party tutorial, GitHub scraper, and older USPTO page — **no longer exists.** The Developer Hub was decommissioned on 5 June 2026 and its deep links resolve to the portal homepage rather than to the equivalent resource, so a broken path fails as a *wrong page*, not as a 404. Any implementation guide predating mid-2026 is unreliable on access mechanics.

**❌ "One pipeline serves M1 and M7" overstates the synergy.**

There are **two distinct trademark products**, not one:

| | Trademark Case Files Dataset | Trademark Full Text XML (`TRTDXFAP`) |
|---|---|---|
| Publisher | Office of the Chief Economist | Bulk data / ODP |
| Coverage | Oct 1870 – **Mar 2024** | Current, to present |
| Cadence | **Annual** (2023 data released 3 Sep 2025) | **Daily** |
| Format | CSV 4.33 GB · Stata 4.19 GB | XML per DTD |
| Shape | Curated relational tables | Raw filing records |

M1 needs a *historical* corpus; staleness is irrelevant to phonotactic induction. **M7 needs *current* live marks** — a screening index two years out of date would miss exactly the recent registrations most likely to collide with a founder's new name.

So M1 and M7 need **different products with different cadences.** The genuine shared asset is the normalisation logic and the mark-text semantics, not the pipeline. ADR-0016's "one ingestion pipeline, two milestones" is too strong and should be corrected.

### 1.3 Not verified — resolve by spike before implementation

I could not confirm these without an API key, and **the design must not hardcode guesses**:

| Unknown | Handling |
|---|---|
| Exact CSV column names | Documentation uses prose ("the mark identification character field"), not column names. **Validate the header at ingest; fail loudly on mismatch.** |
| Exact `mark_drawing_code` values | Docs describe the categories and reference `"4"` (pre-Nov-2003) and `"5"` in an example. **Derive the real distribution from the data and assert it matches expectations.** |
| Current download URL for the Case Files bundle | Discover via the ODP product API using a key |
| Whether the Case Files bundle needs the key too | Assume yes; verify |
| Rate limits / quotas | Unknown; back off conservatively |

---

## 2. Source decision

**Use the Trademark Case Files Dataset for the M1 corpus.** Raw daily XML is deferred to M7.

**Why:** it arrives as curated relational tables rather than raw filings — no XML/DTD parsing, and the fields we need (mark text, drawing code, status, dates, classes) are already extracted and documented. Its ~2-year staleness costs us nothing for phonotactic induction, and slightly under-counts recent morpheme saturation, which is a second-order effect on a signal we refresh anyway.

Accepted as **[ADR-0018](../adr/0018-case-files-over-raw-xml.md)**.

### The one table we need

`case_file` — one row per registration or application, keyed by serial number. Per the official documentation:

> The mark drawing code in `case_file` indicates whether the registration or application is for a standard character mark, a mark with stylized text, a design with or without text, or a mark for which no drawing is possible. If the mark includes any words, letters or numbers, the **mark identification character field** will contain that text.

That single sentence gives us both the text field and the principled structural filter.

---

## 3. Ingestion pipeline

Five stages, each producing an immutable, content-addressed artifact. **No stage mutates its input**, so any stage can be re-run from the previous one's output without re-downloading 4.3 GB.

```
  ACQUIRE ──▶ SNAPSHOT ──▶ EXTRACT ──▶ VALIDATE ──▶ LAND
    key        content-      csv        schema      raw parquet
    +URL       hashed zip    tables     contract    (typed, immutable)
```

| Stage | Behaviour | Failure mode guarded |
|---|---|---|
| **Acquire** | Resolve product → download URL via ODP product API with `X-API-KEY`; stream to disk; retry with exponential backoff | Rate limiting, transient network |
| **Snapshot** | Verify byte count and content hash; **compare size against the previous snapshot and refuse a shrink beyond tolerance**; store to object storage under `sha256:…` | **Truncated download** — the same failure class as the zone-file guard, and just as silent |
| **Extract** | Decompress; extract `case_file` only; discard the rest unread | Unbounded disk from tables we do not use |
| **Validate** | Assert the header matches a committed **schema contract**; assert row count within tolerance of the documented 12.7M; assert `mark_drawing_code` distribution ≈ documented (~64% standard character) | **Silent schema drift between annual releases** |
| **Land** | Write typed Parquet, one file, immutable, tagged with source hash and vintage | Re-parsing 4.3 GB of CSV on every downstream run |

**The schema contract is a committed artifact**, not an assumption in code. When USPTO changes a column name in the 2024 release, validation fails with a readable diff — rather than the pipeline quietly emitting an empty corpus because a `.get()` returned `None` eight million times.

### Credentials

The API key is a secret: environment variable only, never committed, never logged, redacted from error output. Obtaining it requires a USPTO.gov account — **a human action that blocks M1.0** and should be started now (§8).

---

## 4. Normalisation pipeline

### 4.1 The governing principle

> **Normalisation tags; it does not silently discard.**

Only *structural* rejects remove a row — cases where the record cannot contribute to phonotactic induction at all. Every judgement call (dictionary word, acronym, foreign origin, profanity) becomes a **tag**, so downstream induction can weight or exclude it and we can change our minds without re-ingesting.

Discarding at normalisation time destroys information irreversibly and hides the decision from everyone downstream.

### 4.2 Structural rejects

Applied in order, cheapest first. Each records a rejection reason so the funnel is measurable.

| # | Rule | Rejects | Rationale |
|---|---|---|---|
| **S1** | `mark_drawing_code` ∈ standard-character codes | Design marks, stylized text, non-visual marks | The registration must be for the *word*, not a logo. ~64% survive |
| **S2** | Mark text present and non-empty | Design-only marks | Nothing to learn from |
| **S3** | Single token after whitespace normalisation | `SOFT DRINKS`, slogans | Multi-word marks teach English syntax, not brand phonotactics. Retained separately as Tier C (§4.5) |
| **S4** | Characters ∈ `[A-Za-z]` only | `3M`, `E*TRADE`, non-Latin scripts | Digits and punctuation pollute the character n-gram model |
| **S5** | Length 3–16 characters | Single letters, slogan fragments | Below 3 is an initialism; above 16 is not a brand name |
| **S6** | Not a legal-entity artifact (`INC`, `LLC`, `CORP` as the whole mark) | Filing noise | Not brand names |

Expected survival: **~8M standard-character marks → an estimated 2–4M after S3–S6.** The real number is an output of M1.0, not a claim — and it comfortably exceeds the ≥50k proof bar.

### 4.3 Tags (retained, never rejected)

| Tag | Source | Why it matters downstream |
|---|---|---|
| `is_dictionary_word` | Lexicon lookup | *Apple*, *Oracle* are real brands but teach **English** phonotactics, not **invented-brand** phonotactics. M1.3 will likely down-weight them; that is an induction decision, not a normalisation one |
| `is_probable_acronym` | No vowel, or ≤4 chars all-consonant | Acronyms are a different naming strategy with different phonotactics |
| `is_live_registration` | Status fields | Live registrations are a better quality signal than abandoned applications |
| `is_abandoned` | Status fields | ~31% of the register |
| `is_international_registration` | Madrid Protocol flag | **Foreign-origin marks follow non-English phonotactics.** Leaving them unflagged would silently blur the distribution we are trying to learn |
| `has_profanity_signal` | Safety lexicon | Needed *by* the safety subsystem — deleting these would destroy the data M1.7's red team requires |
| `nice_classes`, `filing_year`, `registration_year` | Direct | Domain affinity and era weighting |

### 4.4 Deduplication — which is also saturation measurement

**Dedupe aggregates; it does not discard.** Collapsing to a distinct set would throw away the single most valuable derived signal in the corpus.

Group by normalised lowercase form, and for each distinct mark text emit:

```
normalized, display, registration_count, live_count, dead_count,
earliest_filing_year, latest_filing_year, nice_class_histogram, tags
```

`registration_count` **is the morpheme saturation input** ([ADR-0013](../adr/0013-typicality-distinctiveness-objective.md) §4). A mark text registered 300 times across classes is exhausted; one registered once is not. Deduplicating naively would delete exactly this.

### 4.5 Quality tiers

Induction consumes tiers by explicit choice, never by accident:

| Tier | Contents | Used for |
|---|---|---|
| **A** | Live registration · standard character · single token · 4–14 chars · not dictionary · not acronym | **Primary induction** — templates, weights, typicality |
| **B** | Standard character single tokens failing a Tier-A predicate (dead, dictionary, acronym) | Novelty-distance reference; saturation |
| **C** | Multi-token and design-with-text marks | **Saturation counting only.** Never phonotactic induction |

### 4.6 Two limitations to state plainly

**The register stores mark text in uppercase.** `CORVANE`, not `Corvane`. We therefore **cannot learn capitalisation conventions from this corpus at all** — no camel-case, no lowercase-brand convention. Orthographic realisation ([ADR-0011](../adr/0011-two-tier-phoneme-orthography.md)) must source casing conventions elsewhere. Discovering this after building the realisation layer would have been expensive.

**Registered marks are not successful brands** — [risk 7](03-generation-engine.md#13-risks), unchanged and unmitigated by anything here. Anyone can register a trademark and most registrations are unremarkable. The hand-curated overlay and the funded-startup evaluation ceiling remain the only defences.

---

## 5. Held-out dataset strategy

[ADR-0013](../adr/0013-typicality-distinctiveness-objective.md) makes evaluation contamination fatal, and contamination is invisible from the outside: a contaminated study still produces a number, and the number looks fine.

### 5.1 The specific hazard

The M1.7 ceiling is **real funded-startup names**. The USPTO register contains close to every commercially used mark in the US — so **most held-out names are also in the induction corpus.** Without active exclusion, we would induce weights from the very names we later use to prove the engine, and the discrimination study would be measuring memorisation.

### 5.2 Design

**Seal the holdout before induction tooling exists.** Ordering is the control; a holdout defined after the fact is one that can be shaped, however unintentionally, to the result.

1. **Assemble** the holdout from funded-startup names — a source independent of the register.
2. **Seal** it: `evals/holdout/holdout.txt` plus `holdout.sealed.json` containing a content hash and the seal date, both committed.
3. **Exclude** from the induction corpus by three keys, not one:

   | Key | Catches |
   |---|---|
   | Exact normalised form | `figma` = `Figma` |
   | Double Metaphone | `Korvane` leaking a held-out `Corvane` |
   | Edit distance ≤ 1 | `Figmaa`, `Figm` |

   Excluding edit-distance-1 neighbours of a few hundred holdout names removes perhaps a few thousand rows from millions. **Negligible cost, and the only version of this check that is actually safe** — exact-match exclusion alone would let a near-duplicate carry the signal straight through.

4. **Emit** `corpus.induction` as a distinct artifact from `corpus.full`. Induction reads only the former, and that is enforced, not documented.

### 5.3 The CI guard

`tools/check_holdout.py`, wired into `make check` and CI alongside the existing two guards:

| Assertion | Guards against |
|---|---|
| Holdout content hash matches `holdout.sealed.json` | **Someone editing the holdout to make a failing check pass.** The seal is the point — without it the guard checks a file the guard's own failure would tempt you to edit |
| `corpus.induction ∩ holdout = ∅` under all three keys | Direct and near-duplicate contamination |
| Every induction artifact declares its source corpus id | An induction run silently reading `corpus.full` |
| Holdout is non-empty and above a minimum size | A holdout emptied to trivially satisfy the check |

The last two matter as much as the first. A guard that can be satisfied by degenerating its own inputs is not a guard.

---

## 6. Edge cases and failure modes

| # | Failure | Severity | Handling |
|---|---|---|---|
| 1 | **Truncated download** → corpus silently missing millions of rows | 🔴 | Size + hash check against previous snapshot; refuse unexplained shrink |
| 2 | **Schema drift** in a new annual release | 🔴 | Committed schema contract; fail with a readable diff |
| 3 | **Guessed column name wrong** → all-null column, empty corpus, no error | 🔴 | Header validation before any parsing; assert non-null rate |
| 4 | **Holdout contamination via near-duplicates** | 🔴 | Three-key exclusion (§5.2) |
| 5 | **Holdout edited to pass CI** | 🔴 | Sealed content hash |
| 6 | API key expiry / rotation mid-run | 🟠 | Fail fast with a clear message; never retry silently into a rate limit |
| 7 | Rate limiting (limits unknown) | 🟠 | Conservative backoff; resumable download |
| 8 | **USPTO moves or renames the product again** — precedent exists, twice this year | 🟠 | Product resolved via API, not a hardcoded URL; snapshot retained so we can rebuild without re-downloading |
| 9 | Mojibake / non-UTF8 in mark text | 🟠 | Strict decode; quarantine failures to a reject log rather than dropping them |
| 10 | Uppercase-only text | 🟠 | Documented limitation (§4.6); casing sourced elsewhere |
| 11 | Foreign-origin marks skewing phonotactics | 🟠 | `is_international_registration` tag; induction decides |
| 12 | Duplicate serial numbers | 🟡 | Assert uniqueness; quarantine duplicates |
| 13 | Dataset staleness (Mar 2024) | 🟡 | Acceptable for induction; **not** acceptable for M7 screening |
| 14 | Register ≠ successful brands | 🟠 | Unmitigated here. Curated overlay + funded-startup ceiling |
| 15 | Disk: 4.3 GB compressed, materially more extracted | 🟡 | Stream; extract only `case_file`; Parquet for the landed artifact |

Failures 1–5 share a property worth naming: **none of them raises an exception.** Each produces a plausible-looking corpus that is quietly wrong, which is precisely why each gets an explicit assertion rather than a try/except.

---

## 7. Deliverables and proof

| Artifact | Description |
|---|---|
| `services/corpus/` | Acquire, snapshot, extract, validate, land |
| `tools/check_holdout.py` | Contamination guard, wired into `make check` |
| `schema/case_file.contract.json` | Committed schema contract |
| `evals/holdout/` | Sealed holdout + seal manifest |
| `corpus.full`, `corpus.induction` | Content-addressed Parquet artifacts |
| Funnel report | Row counts and rejection reasons at every stage |

**M1.0 is done when:** ≥50k Tier-A single-token marks are landed and deduplicated with saturation counts; the schema contract validates; the holdout is sealed; the contamination guard is green in CI; and the funnel report is published.

Note that the pipeline lives in `services/`, not `engine/` — it performs network and filesystem I/O, and [ADR-0006](../adr/0006-pure-engine-boundary.md)'s import-linter contract will reject it anywhere else.

---

## 8. Blocking action

**A USPTO.gov account and API key are required before any of this runs**, and obtaining them is a human action I cannot perform.

| Step | Owner |
|---|---|
| Create a USPTO.gov account | **Founder** |
| Register for Open Data Portal access | **Founder** |
| Obtain an API key; confirm the header is `X-API-KEY` | **Founder** |
| Provide the key via environment variable (never committed) | **Founder** |
| Spike: confirm column names, drawing codes, download URL, rate limits | CTO, once the key exists |

This joins the [zone-file applications](../ops/zone-file-access.md) as a founder-blocking dependency. Neither is large; both stop work entirely if left.
