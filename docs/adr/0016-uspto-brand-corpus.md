# ADR-0016: USPTO bulk trademark data as the brand corpus

**Status:** Accepted — **amended by [ADR-0018](0018-case-files-over-raw-xml.md)**
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §13](../design/03-generation-engine.md), risk 1

> **Verification note (2026-08-04):** checked against primary sources during [M1.0 design](../design/06-m1-0-corpus-assembly.md). The **licensing basis below is confirmed** — data.gov records the licence as Public Domain Mark 1.0, so no constraint reaches derived models, and the core decision stands. Two claims did not survive:
>
> 1. **"Freely downloadable" no longer holds.** The Open Data Portal has required a USPTO.gov account since 18 June 2026, and `api.uspto.gov` requires an `X-API-KEY` header (verified: 401 without, 403 with an invalid key). Obtaining a key is now a prerequisite for M1.0. The legacy `bulkdata.uspto.gov` host no longer resolves at all.
> 2. **"One ingestion pipeline serves both M1 and M7" is withdrawn.** "USPTO bulk trademark data" is two products with different cadences; M1 needs the historical Case Files Dataset, M7 needs current daily XML. See [ADR-0018](0018-case-files-over-raw-xml.md).

## Context

[ADR-0013](0013-typicality-distinctiveness-objective.md) makes a corpus of real brand names a hard dependency: prosodic templates, phonotactic weights, the typicality model, morpheme saturation, and novelty distance are **all** induced from it. Corpus quality bounds engine quality.

It also carries a licensing dimension that is easy to get wrong quietly. A corpus ingested under restrictive terms can contaminate every derived model, and the problem surfaces at diligence rather than at ingestion.

## Decision

**USPTO bulk trademark data is the primary brand corpus.**

- It is a **US government work and therefore public domain** — no licence constrains derived models.
- It is large enough to induce reliable phoneme-level distributions.
- It is **already required for M7 trademark screening.** One ingestion and normalisation pipeline serves both the generation corpus and the screening index.

A smaller hand-curated set of successful startup names may be layered in later as a quality-weighted overlay, and a held-out slice of real startup names is reserved as the evaluation ceiling — excluded from induction per [ADR-0013](0013-typicality-distinctiveness-objective.md).

## Alternatives considered

- **Commercial startup dataset (Crunchbase or similar).** Cleaner and closer to the names we want to emulate. Rejected as the primary source: commercial licences frequently restrict derived-model use, and a term discovered after we have induced an engine from the data is a genuinely bad position — potentially requiring us to rebuild the core model. Not worth the exposure when a public-domain alternative exists.
- **Hand-curated set only.** Zero licensing risk, highest signal. Rejected as primary: realistically thousands rather than tens of thousands of names, too thin for reliable phoneme-level statistics. Retained as an overlay.
- **Web-scraped company lists.** Cheap and plentiful. Rejected: terms-of-service exposure, no provenance, and unknown quality — the worst combination of the three.

## Consequences

- **Accepted: substantial cleaning work.** Trademark registrations include many non-brandable marks — descriptive phrases, slogans, figurative marks, defunct registrations, and multi-word entries. The normalisation pipeline is real work and is scheduled as M1.0, first, because everything downstream blocks on it.
- **Accepted: registered marks are not the same population as *successful brands*.** Most registrations are unremarkable. This biases the induced typicality model toward the merely legal rather than the genuinely good. Mitigated by the hand-curated overlay and by keeping the evaluation ceiling drawn from *funded startups*, not from the register.
- **Gained:** one pipeline, two milestones (M1 and M7). Worth designing around deliberately.
- **Gained:** no licensing constraint on any derived model — which matters at diligence, not just today.
- **Required:** saturation counts (how used-up a morpheme is) come from this corpus, so its refresh cadence directly drives how current our anti-mode-collapse signal stays.
