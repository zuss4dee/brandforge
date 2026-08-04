# BrandForge — Data Model

**Status:** Draft v0.1 · **Date:** 2026-08-04

Conceptual model. Physical schema (DDL + Alembic migrations) lands in M0/M4.

---

## 1. The central split: global vs. tenant data

The most important structural property of this model.

| Global (shared across all tenants) | Tenant-scoped |
|---|---|
| `name_candidate` — the inventory | `organization`, `user`, `membership` |
| `linguistic_score` — brief-independent scores | `project`, `brief`, `run` |
| `availability_fact` — TTL'd | `run_candidate` — semantic scores, ranking |
| `trademark_signal` | `shortlist`, `shortlist_item`, `vote`, `comment`, `decision` |

**Why it matters:** the expensive work (generation, phonetic analysis, availability lookups) is computed once and amortised across every user forever. The per-request work is a thin tenant-scoped layer on top. This is the data-model expression of the inventory-first thesis ([ADR-0002](../adr/0002-inventory-first-architecture.md)).

**Tenancy is in the schema from M0.** Every tenant-scoped table carries `organization_id`, enforced by row-level security. Retrofitting multi-tenancy is one of the reliable ways to spend a quarter on nothing.

---

## 2. Global entities

### `name_candidate`
The inventory. Expected to reach 10⁷+ rows.

| Field | Notes |
|---|---|
| `id` | |
| `text` | Canonical display form, e.g. `Corvane` |
| `normalized` | Lowercased, diacritics folded — **unique** |
| `length`, `syllable_count` | Denormalised for filtering |
| `phoneme_sequence` | IPA/ARPAbet, from g2p |
| `stress_pattern` | e.g. `10` for trochaic |
| `provenance` | JSONB — strategy, morphemes, roots, ruleset version. **The retrieval key** ([ADR-0008](../adr/0008-provenance-retrieval.md)) |
| `concept_tags` | Denormalised from provenance for fast filtering |
| `concept_embedding` | `vector` — embedding of the *provenance concepts*, never the name string |
| `first_seen_at`, `engine_version` | |

Indexes: `normalized` (unique), `(length, syllable_count)`, GIN on `concept_tags`, HNSW on `concept_embedding`. Partitioning deferred until measured need.

### `linguistic_score`
Brief-independent. Keyed `(candidate_id, ruleset_version)` — so a ruleset change adds rows rather than destroying history.

Columns per dimension: `pronounceability`, `phonotactic_legality`, `spellability`, `memorability`, `distinctiveness`, `trademark_strength_class`, plus `components` JSONB holding the sub-signals that produced each. **No composite score is stored** — the composite is computed at read time from the active posture weights ([ADR-0007](../adr/0007-posture-relative-scoring.md)).

### `safety_flag`
Separate from scores because it is a **hard gate**, not a weight. `(candidate_id, language, severity, category, source_lexicon)`. A candidate with any `severity = blocking` flag never surfaces, under any posture.

### `availability_fact`
`(candidate_id, tld, source, status, confidence, price_cents, currency, checked_at, expires_at)`

`source` ∈ `zone_file | rdap | dns | registrar | aftermarket` — mapping to the L0–L3 cascade. `confidence` is explicit because sources genuinely differ in authority (DNS is a hint; registrar is authoritative). Reads take the highest-confidence non-expired fact. TTL governs *read eligibility*, not deletion: zone-file facts refresh with the zone drop, registrar facts expire in hours.

⚠️ **Facts are retained in full, never overwritten** ([Brand DNA §10](05-brand-dna.md)). The audit trail is what makes "was it available when we chose it?" answerable with evidence rather than assertion. This makes `availability_fact` the highest-volume table in the system, growing without bound as the background sweeper runs. **Time-based partitioning and an archival tier must be designed before M3 ships** — retrofitting them once the table is large is exactly when migrations become painful.

### `trademark_signal`
`(candidate_id, mark_text, jurisdiction, nice_class, status, match_type, similarity, source_record_id, retrieved_at)`

`match_type` ∈ `exact | phonetic | edit_distance`. **Evidence only.** There is deliberately no `is_clear` or `risk_verdict` column — the schema makes the legal posture structural rather than a UI convention ([ADR-0009](../adr/0009-trademark-signals-not-verdicts.md)).

---

## 3. Tenant-scoped entities

### `organization` / `user` / `membership`
Standard. `membership.role` ∈ `owner | admin | member | viewer`.

### `project`
A naming effort. Belongs to an org, has many briefs and runs.

### `brief` — **versioned, never updated in place**
| Field | Notes |
|---|---|
| `description` | Free text — what the company does |
| `industry`, `audience`, `tone` | |
| `posture` | `deep_tech \| enterprise_b2b \| consumer_playful \| premium_luxury \| clinical_trust` — drives score weights |
| `must_include` / `must_avoid` | Substrings, phonemes, concepts |
| `length_min/max`, `syllable_min/max` | |
| `tld_preferences` | Ordered |
| `budget_cents` | Ceiling for acquirable-domain suggestions |
| `version`, `parent_brief_id` | Editing a brief creates a new version so past runs stay interpretable |

### `run`
One execution of the pipeline over one brief version.

`status` ∈ `queued | generating | scoring | verifying | ranking | complete | failed`
`manifest` JSONB — engine version, ruleset version, RNG seed, model IDs, prompt versions, corpus hashes. **Reproducibility contract.**
`cost_cents`, `token_usage`, `provider_calls` — cost attribution is first-class, not an afterthought.

### `run_candidate`
The join carrying per-run, brief-dependent results.

`(run_id, candidate_id, semantic_fit, posture_fit, composite_score, rank, rationale, llm_model, prompt_version)`

`rationale` is generated only for the top slice — LLM cost is bounded by construction, not by hope.

### `shortlist` / `shortlist_item` / `vote` / `comment` / `decision`
The collaboration layer (M8). `decision` records the chosen candidate, the deciding user, timestamp, and — critically — a **snapshot** of the availability and trademark facts as they stood at decision time. Founders will ask "was it available when we chose it?" and the answer must not depend on live data that has since moved.

---

## 4. Lifecycle notes

**Inventory growth.** Generation runs are background jobs that append to `name_candidate` and `linguistic_score`. They are not user-triggered. A user's run *retrieves* from inventory and supplements with brief-conditioned construction.

**Availability freshness.** A background sweeper refreshes `availability_fact` for high-scoring inventory, prioritised by score and staleness — so the names most likely to be shown are the ones most likely to be fresh. Cheap, and it makes the common case fast.

**Ruleset migration.** Bumping `ruleset_version` does not invalidate rows; it adds a new score generation. Old runs remain explainable under the ruleset that produced them.
