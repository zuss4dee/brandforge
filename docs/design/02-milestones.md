# BrandForge — Milestones

**Status:** Approved v0.1 · **Date:** 2026-08-04

One milestone at a time. Each has a hard Definition of Done and a **proof** — a measurable claim, not "it compiles." A milestone is not done until its proof is demonstrated.

---

| # | Milestone | Definition of Done | Proof |
|---|---|---|---|
| **M0** | **Foundations** | Monorepo, CI, lint/type/test gates, ADR process, domain model, tenancy in schema, observability skeleton. **Zone-file + CZDS applications filed.** | CI green on an empty vertical slice; agreements submitted |
| **M1** | **Generation Engine** | Pure, deterministic, CLI-driven. No API, no UI, **no LLM**. [Design](03-generation-engine.md) · [Eval](04-generation-evaluation.md) | 10⁷ enumerated / 10⁵+ admitted candidates, **zero duplicate derivations**, bit-reproducible from `(seed, ruleset_version, index)`; blind forced-choice discrimination vs. held-out real startup names **≤60%** (chance 50%); rated significantly above competitor generators; T–D frontier occupancy separated from the training corpus |
| **M2** | **Scoring Engine** | 9 dimensions + posture profiles. **Eval set built first.** | Rank correlation vs. human labels beats a length-only baseline by a stated margin |
| **M3** | **Availability Subsystem** | Tiered L0–L3, provider ports, caching, budget governors, **partitioning + archival tier for the unbounded fact history** | Verified availability for 10k names at a measured cost/name; L0 eliminates ≥90% |
| **M4** | **API + Orchestration** | Projects, briefs, runs, durable pipeline, streamed progress | End-to-end run via API in under 90s |
| **M5** | **Semantic Layer** | LLM brief expansion, concept-tag retrieval, rerank, rationale | Blind test: brief-relevant output beats a random inventory sample |
| **M6** | **Web App** | Brief → explore → shortlist → compare → decide | 5 external founders complete a run unassisted |
| **M7** | **Risk & Trust** | Local USPTO index, phonetic collision, multi-language safety | Screens a full shortlist in <2s; zero unsafe names in a red-team set |
| **M8** | **Collaboration & Decision** | Teams, voting, comments, export, acquisition handoff | A team of 3 converges on a name |
| **M9** | **Commercialization** | Auth, billing, quotas, rate limits, tenancy hardening | Paid run executes end-to-end |
| **M10** | **Quality Flywheel** | Feedback capture → learned reranker → continuous eval | Ranking measurably improves from real user choices |

---

## Sequencing rationale

**M1–M3 are the actual product.** M4–M6 make it usable; M7–M10 make it a business.

**M1 deliberately has no UI and no LLM.** If we can't produce a great name inventory offline, no amount of frontend saves us — and it is far better to learn that in week two than in month four. The temptation to build a demo-able slice first is the temptation to defer the only question that matters.

**M1's proof was strengthened on 2026-08-04.** The original "human spot-check ≥80% sounds like a real company" had no baseline (80% against *what*?), drifted with rater mood, and measured only typicality — a generator that memorised the corpus would have scored ~100% and been worthless. The replacement is a blind forced-choice study against held-out real startup names, which is self-calibrating because the baseline is embedded in the instrument. Rationale in [Evaluation Strategy §0](04-generation-evaluation.md).

**M2 builds the eval set before the scorer.** Writing the scorer first means grading our own homework. The eval set is the specification.

**M0 files the zone-file agreements** because they carry weeks of contractual lead time and M3 depends on them. This is the classic hidden critical-path item — see [zone-file-access.md](../ops/zone-file-access.md).

## Explicitly deferred

Logo/tagline generation, full brand identity, domain trading, mobile apps, and any learned ranking model before M10. Each is a plausible-sounding detour from the one question v1 must answer: *can we reliably find founders names they can own?*
