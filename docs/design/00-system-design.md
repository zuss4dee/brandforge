# BrandForge — System Design

**Status:** Approved v0.1 · **Date:** 2026-08-04 · **Owner:** CTO

---

## 1. Thesis

> BrandForge is a **search-and-verification engine over an owned inventory of brandable, verified-available names**, with an LLM as the semantic steering layer — not an AI name vending machine.

This framing was chosen deliberately over the intuitive one ("generate thousands of names, then filter"). Four claims underpin it. Each is recorded as an ADR.

1. **Thousands of unavailable names is noise.** Founders want ~15 names they can *own*. Availability is the scarce constraint, so it becomes the first-class axis rather than the last filter. → [ADR-0002](../adr/0002-inventory-first-architecture.md)
2. **LLMs are the wrong bulk generator.** They mode-collapse (`-ly`, `-ify`, `Nexus`, `Lumina`), duplicate across users, are non-deterministic (so scores aren't reproducible), and cost scales linearly with usage forever. Combinatorial phonotactic generation is deterministic, free, and genuinely novel. → [ADR-0003](../adr/0003-deterministic-generation.md)
3. **The moat is owned data, not prompts.** Zone files, bulk trademark registers, and a labelled brand corpus compound. Prompts don't — every competitor can call the same models.
4. **There is no universal name quality.** "Vanta" is excellent for B2B security and terrible for a children's bakery. Scoring is **posture-relative**. → [ADR-0007](../adr/0007-posture-relative-scoring.md)

---

## 2. Product

**Who:** Pre-seed/seed founders; product leads naming a new line. Secondary: agencies, VC platform teams.

**Job to be done:** *"Get me to a name I love, that I can legally use and actually own the .com for, in one sitting instead of three weeks."*

| Metric | Definition |
|---|---|
| **North star** | **Time-to-Confident-Name** — median minutes from brief submitted to a name marked *decided* |
| **Primary quality** | % of a user's shortlist that is exact-match `.com` available or acquirable under budget |
| **Business** | runs → decision → domain acquisition conversion |

**Core loop:** `Brief → Run → Explore → Shortlist → Compare → Verify → Decide → Acquire`

**Explicitly out of scope for v1:** logo generation, tagline generation, full brand identity systems, domain speculation/trading, legal opinions.

---

## 3. Architecture

**Shape:** modular monolith + async workers. Not microservices — at our size the failure mode of microservices is distributed debugging of a product that hasn't found fit. Module boundaries are enforced *in code* so any module can be extracted later when a real scaling reason appears. → [ADR-0001](../adr/0001-modular-monolith.md)

```
┌──────────────────────────────────────────────────────────────┐
│  Web App (Next.js)  — brief, explore, shortlist, decide       │
└───────────────────────────┬──────────────────────────────────┘
                            │ OpenAPI-typed client · SSE run progress
┌───────────────────────────▼──────────────────────────────────┐
│  API (FastAPI)  — auth, tenancy, projects, runs, shortlists   │
└───────────┬───────────────────────────────┬──────────────────┘
            │ enqueue                       │ read
┌───────────▼───────────────┐   ┌───────────▼──────────────────┐
│  Orchestrator + Workers   │   │  Postgres 16                 │
│  (durable job pipeline)   │   │  + pgvector  + Redis cache   │
└───────────┬───────────────┘   └──────────────────────────────┘
            │
   ┌────────┴─────────┬──────────────┬─────────────┬───────────┐
   ▼                  ▼              ▼             ▼           ▼
┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────┐ ┌──────────┐
│Generation│ │Linguistic    │ │Availability│ │Risk &   │ │LLM       │
│Engine    │ │Scoring       │ │Service     │ │Trademark│ │Gateway   │
│(pure)    │ │(pure)        │ │(tiered)    │ │Screening│ │(Claude)  │
└──────────┘ └──────────────┘ └─────┬──────┘ └────┬────┘ └──────────┘
                                    │             │
                           ┌────────▼─────────────▼────────┐
                           │  Owned Data Indexes            │
                           │  zone files · RDAP cache ·     │
                           │  USPTO/EUIPO marks · brand     │
                           │  corpus · profanity lexicons   │
                           └────────────────────────────────┘
```

### 3.1 The two load-bearing decisions

**(a) Generation and linguistic scoring are pure functions.** No I/O, no network, no database. Given `(brief_params, ruleset_version, seed)` they are fully deterministic and reproducible — therefore unit-testable, benchmarkable, cacheable, and explainable. Anything touching the network lives behind an adapter in `services/`, outside `engine/`. CI enforces that `engine/` cannot import `services/`. → [ADR-0006](../adr/0006-pure-engine-boundary.md)

**(b) Scores split by brief-dependence.**

| Score class | Brief-dependent? | Cache scope |
|---|---|---|
| Pronounceability, spellability, syllables, rhythm, distinctiveness, safety | No | Global, permanent, keyed `(name, ruleset_version)` |
| Semantic fit, posture fit, LLM rationale | **Yes** | Per-run |
| Availability, trademark signals | No, but time-decaying | Global, TTL'd |

The expensive linguistic analysis of `"Corvane"` is computed **once for every user, ever**. Only the cheap semantic layer is per-request. This is the largest single efficiency win in the design.

### 3.2 Reproducibility

Every run emits a **manifest**: engine version, ruleset version, RNG seed, model IDs, prompt versions, corpus hashes. For a scoring product, *"why is this an 82?"* must be answerable in eighteen months.

---

## 4. Generation Engine

Four supply sources feed one candidate stream. Every candidate carries **provenance** — which strategy built it, from which morphemes, under which ruleset. Provenance is what makes retrieval and explanation possible downstream.

| # | Source | Role |
|---|---|---|
| 1 | **Phonotactic construction** | Syllable grammar over legal onsets/nuclei/codas; CV/CVC/CVCV templates; sonority-sequencing constraints; stress targets. The workhorse. |
| 2 | **Morphemic composition** | Curated Latin/Greek/Germanic roots (`vert`, `lum`, `cred`, `nav`) with semantic-affinity tags, plus brandable affixes (`-io`, `-ora`, `-ly`, `-va`). |
| 3 | **Lexical mutation** | Real words → vowel shift, consonant swap, truncation, compounding, portmanteau, deliberate misspelling (`Lyft`/`Flickr` class). |
| 4 | **LLM concept expansion** | Claude reads the brief, returns *seed vocabulary* — metaphors, adjacent domains, tone words — which feeds sources 2 and 3. **Never emits final names in bulk.** |

### 4.1 Retrieval: embed provenance, not the name

The obvious design — embed every inventory name in pgvector, search against the brief — **does not work.** `"Corvane"` is not a word; its embedding is noise. Semantics live in the *morphemes and concept tags attached at generation time*, not in the surface string.

**So we embed provenance.** Retrieval is `brief → concepts → tags → candidates`, combined with structured filters (length, syllables, availability flag, quality floor). Getting this wrong is the most common way these systems produce irrelevant output. → [ADR-0008](../adr/0008-provenance-retrieval.md)

A brief-conditioned construction pass supplements inventory retrieval with roots derived from the brief's own vocabulary — cheap, deterministic, and covers concepts the inventory hasn't seen.

---

## 5. Scoring Engine

Nine dimensions. **Every subscore is stored**; the composite is a *view* computed from stored parts under the active posture weights.

| Dimension | Method |
|---|---|
| **Pronounceability** | Character 5-gram model (Kneser-Ney) over English lexicon + real brand corpus. Mean log-prob per char, z-normalised. Tiny, fast, explainable. |
| **Phonotactic legality** | g2p → syllabify → validate onset/coda clusters and sonority sequencing. Catches what the n-gram misses. |
| **Spellability** | The "say it over the phone" test. g2p → p2g round-trip; count plausible alternate spellings. High ambiguity = real-world friction. |
| **Length & syllables** | Posture-dependent target curves, not a fixed penalty. |
| **Memorability** | Stress/rhythm pattern, alliteration, phoneme repetition, distinctiveness from neighbours. |
| **Trademark strength** | Classify on the real legal spectrum: fanciful > arbitrary > suggestive > descriptive > generic. Differentiating — and it's the axis that gets founders sued. |
| **Semantic fit** | Concept-tag overlap + LLM judge on the top slice only. |
| **Linguistic safety** | Profanity / unfortunate meaning across ~15 major languages, including phonetic near-misses. A **hard gate**, not a score. |
| **Ownability** | Availability + acquisition cost + handle availability, folded in as a score rather than a filter. |

### 5.1 Evaluation before implementation

Scoring without ground truth is astrology. **M2 ships the eval set before it ships the scorer:** ~500 names — successful startup names (positive), random legal strings (neutral), known-failed/unpronounceable names (negative) — plus human ratings. Rank correlation is reported on every ruleset change. If the model can't rank real unicorn names above random CVCV strings, the model is wrong and we find out immediately.

---

## 6. Availability Subsystem

An economics problem before it is an engineering problem. Naively checking 3,000 names × 5 TLDs per run at registrar-API prices is a business-ending cost curve.

### 6.1 Tiered cascade

| Tier | Source | Cost | Answers |
|---|---|---|---|
| **L0** | Bloom filter from **zone files** | ~free, no network | "Definitely registered" — kills 90%+ of candidates locally |
| **L1** | RDAP (+ DNS as weak hint) | free, rate-limited, cached | Registered/available, dates, registrar |
| **L2** | Registrar API | $ / rate-limited | Authoritative + **price + premium status** |
| **L3** | Aftermarket (Afternic/Sedo/Dan) | $ | Resale price for taken-but-purchasable |

Only names surviving L0 *and* scoring well reach L2. Roughly a **100× cost reduction** versus the naive design. → [ADR-0005](../adr/0005-tiered-availability.md)

### 6.2 Two correctness traps

⚠️ **DNS is not authoritative for registration.** Many registered domains have no nameservers. Any design treating NXDOMAIN as "available" will lie to users. DNS is a hint that promotes to L1 — never a verdict.

⚠️ **Zone-file access has weeks of contractual lead time.** Verisign `.com` TLD Zone File Access and ICANN CZDS applications must be filed during **M0**, or they land on the critical path at M3. See [zone-file-access.md](../ops/zone-file-access.md).

### 6.3 Front-running as a trust feature

Founders genuinely fear that searching a domain gets it sniped. **Commitment:** shortlisted candidates are resolved via zone data and RDAP — never leaked into third-party *search* endpoints that could be logged and acted on. Our architecture already works this way, so this costs nothing and is worth saying out loud in the product.

### 6.4 Provider isolation

Every provider sits behind one port — `AvailabilityProvider` → normalized `AvailabilityFact {status, source, confidence, checked_at, price}` — with per-provider circuit breakers, budget governors, and rate limiters. No provider's JSON shape reaches the domain model. Providers *will* churn; that's a certainty, not a risk.

---

## 7. Risk & Trademark Screening

Ingest **USPTO bulk trademark data locally** (freely downloadable) rather than paying per query. Index by exact mark, normalized mark, phonetic key (Double Metaphone), and Nice class. Screening = exact + phonetic + edit-distance match against *live* marks in briefs-relevant classes.

⛔ **Legal posture, decided at design time:** we surface **signals, never conclusions.** No "clear to use." UI language is calibrated — *"3 live marks with similar phonetics in class 42 — review with counsel."* The data model stores **evidence, not verdicts**, so the constraint is structural rather than a UI convention someone can later violate. ToS states explicitly that this is not legal advice. → [ADR-0009](../adr/0009-trademark-signals-not-verdicts.md)

---

## 8. Technology

| Layer | Choice | Rationale |
|---|---|---|
| Engine + API | **Python 3.12**, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | The engine is a linguistics/ML workload — g2p, phonemizer, n-gram models, numpy, embeddings |
| Web | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query | Fast, boring, hireable |
| Type sharing | OpenAPI → generated TS client | Recovers most of the safety a single-language stack would give |
| Database | Postgres 16 + pgvector | One datastore until proven otherwise. JSONB for evolving score payloads, relational for integrity |
| Cache / queue | Redis + Arq | Avoids Celery's operational weight at this size |
| Object store | S3 / Cloudflare R2 | Corpus snapshots, zone dumps, exports |
| LLM | **Claude** behind a model-agnostic gateway — Opus 5 for brief interpretation + rationale, Haiku 4.5 for bulk rerank/judge | Structured output via tool schemas; prompt versioning, eval harness, per-run cost ceiling from day one |
| Observability | OpenTelemetry, structured logs, Sentry | Per-run cost and latency attribution is a first-class metric |
| Deploy | Docker → Fly.io/Railway → AWS when it hurts | No platform team for a product with no users |

**Accepted trade-off:** Python + TypeScript means two languages and two toolchains. An all-TS stack would be simpler for a small team. We chose Python because the name engine *is* the product, and in TypeScript we'd be hand-rolling phonetics libraries that are already battle-tested in Python. → [ADR-0004](../adr/0004-python-engine-typescript-web.md)

---

## 9. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Availability data cost / rate limits | 🔴 Critical | Tiered cascade; zone files as foundation |
| 2 | Zone-file agreements have weeks of legal lead time | 🔴 Critical | **File during M0**, before dependent code exists |
| 3 | Trademark screening → legal liability | 🔴 High | Signals-not-verdicts, structural in the data model + ToS |
| 4 | Quality is subjective; no ground truth | 🟠 High | Eval set ships *before* the scorer (M2) |
| 5 | LLM cost blowup at scale | 🟠 High | LLM on top-N only; hard per-run budget ceiling; aggressive caching |
| 6 | Offensive meaning in another language | 🟠 High | Multi-language safety screen as a hard gate |
| 7 | Provider churn / API deprecation | 🟡 Medium | Ports & adapters from day one |
| 8 | Mode collapse — every user gets similar names | 🟡 Medium | Combinatorial generation + per-tenant novelty tracking |
| 9 | Multi-tenant data leakage | 🟡 Medium | Tenancy in the schema from M0, never retrofitted |

---

## 10. Related documents

- [Data model](01-data-model.md)
- [Milestones](02-milestones.md)
- [Zone-file access runbook](../ops/zone-file-access.md)
- [Architecture Decision Records](../adr/)
