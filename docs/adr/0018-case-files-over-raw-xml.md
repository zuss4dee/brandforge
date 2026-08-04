# ADR-0018: Trademark Case Files Dataset for the M1 corpus; raw XML deferred to M7

**Status:** Accepted
**Date:** 2026-08-04
**Amends:** [ADR-0016](0016-uspto-brand-corpus.md)
**Implements:** [M1.0 Corpus Assembly §2](../design/06-m1-0-corpus-assembly.md)

## Context

[ADR-0016](0016-uspto-brand-corpus.md) chose "USPTO bulk trademark data" as the brand corpus and claimed the ingestion pipeline would serve both M1 (corpus) and M7 (trademark screening) — "one pipeline, two milestones."

Verification against primary sources on 2026-08-04 showed that **"USPTO bulk trademark data" is not one product but two**, with different publishers, shapes, and update cadences:

| | Trademark Case Files Dataset | Trademark Full Text XML (`TRTDXFAP`) |
|---|---|---|
| Publisher | Office of the Chief Economist | Bulk data / ODP |
| Coverage | Oct 1870 – **Mar 2024** | Current |
| Cadence | **Annual** | **Daily** |
| Format | CSV 4.33 GB · Stata 4.19 GB | XML per DTD |
| Shape | Curated relational tables | Raw filing records |

The two milestones have genuinely different requirements. M1 needs a large *historical* corpus, where staleness is irrelevant to phonotactic induction. M7 needs *current live marks* — a screening index two years stale would miss precisely the recent registrations most likely to collide with a founder's new name, which is the failure mode the feature exists to prevent.

## Decision

1. **The M1 corpus is the Trademark Case Files Dataset**, specifically its `case_file` table.
2. **M7 screening will use the daily XML product**, ingested separately when M7 begins.
3. **ADR-0016's "one pipeline, two milestones" claim is withdrawn.** The genuine shared asset is the normalisation logic and mark-text semantics — not the pipeline.

## Alternatives considered

- **Raw daily XML for both.** One product, always current, no staleness. Rejected for M1: it requires XML/DTD parsing and reassembling a historical backfile from daily increments, to obtain a corpus whose currency does not matter. Substantial work for no benefit at this milestone.
- **Case Files for both.** One pipeline, genuinely. Rejected for M7: shipping a trademark screening feature against a two-year-stale index would systematically miss recent collisions. That is worse than not shipping the feature, because it would be trusted.
- **Third-party mirrors** (Reed Tech and similar). Historically convenient. Rejected: unknown provenance and licensing, and no guarantee of continuity — the legacy USPTO hosts themselves vanished this year.

## Consequences

- **Gained:** no XML parsing in M1. `case_file` arrives as a curated relational table with mark text, drawing code, status and dates already extracted and documented.
- **Gained:** the official documentation gives us a principled structural filter — `mark_drawing_code` distinguishes standard-character marks (the word marks we want) from design and stylized marks, and standard-character marks are ~64% of observations.
- **Accepted:** the M1 corpus is stale to March 2024. Irrelevant for phonotactic induction; it slightly under-counts recent morpheme saturation, a second-order effect on a signal that is refreshed anyway.
- **Accepted: two ingestion pipelines, not one.** ADR-0016 was too optimistic. The cost is real but smaller than the alternative of serving one milestone badly.
- **Required:** the annual cadence means the corpus is refreshed roughly yearly. Saturation counts age between refreshes, and the refresh must not silently change induced weights — under [ADR-0017](0017-immutable-address-spaces.md) a corpus refresh that changes weights mints a **new address space** rather than mutating the current one.
