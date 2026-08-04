# Brand DNA Specification

**Status:** Approved v1.0 · **Date:** 2026-08-04
**Precedes:** M1.0 (Corpus Assembly) and all engine code
**Related:** [Data Model](01-data-model.md) · [Generation Engine](03-generation-engine.md) · [ADR-0012](../adr/0012-index-addressable-generation.md) · [ADR-0017](../adr/0017-immutable-address-spaces.md)

---

## 0. What this is, and the trap it must avoid

Brand DNA is the **canonical record that travels with a candidate from generation to decision**. Every subsystem reads it; each writes exactly one part of it. It is the contract between the engine, the scorers, the availability and trademark adapters, and the product.

**The trap is the god object.** The obvious implementation — one document that every subsystem writes to as it learns things — couples everything to everything. Six months in, nobody can change a field because seven subsystems read it, nobody knows which writer is authoritative for a value, and a stale score and a fresh score sit in the same blob with no way to tell them apart.

The specification therefore leads with the constraints, not the fields:

1. **Four layers, one writer each.** No subsystem writes another's layer. Ever.
2. **Layers differ in mutability, and the difference is enforced.** Sealed, recomputable, decaying, and append-only are four different things and must not share a storage model.
3. **Identity derives from one layer only.** A candidate's id cannot change because a score was recomputed or a domain expired.
4. **Nothing is hashed that contains a float.**

---

## 1. The four layers

The organising question is *what kind of truth is this?* — because that determines mutability, ownership, cacheability, and tenancy. Four kinds of truth turn out to be present, and they behave completely differently.

| Layer | Truth kind | Writer | Mutability | Scope |
|---|---|---|---|---|
| **0 · Genotype** | What it **is** — structure | Generation engine | **Sealed at birth** | Global |
| **1 · Phenotype** | What it's **worth** — measurement | Scoring engine | **Recomputable**, versioned | Global |
| **2 · Environment** | What the **world says** | `services/` adapters | **Decaying**, TTL'd | Global |
| **3 · Reception** | What **humans decided** | API / product | **Append-only** event log | **Tenant** |

The genotype/phenotype distinction is doing real work here, not decoration: **genotype is discrete and immutable, phenotype is continuous and derived.** That single line predicts every downstream property — what can be hashed, what can be cached, what must be recomputed on a ruleset bump, what belongs in an index.

This layering is consistent with the global/tenant split already in [Data Model §1](01-data-model.md): layers 0–2 are global and amortised across all users forever; only layer 3 is tenant-scoped.

---

## 2. Layer 0 — Genotype

**Everything determined by `(space_id, seed_id, index, ruleset_version)`.** Sealed at creation, never updated, never migrated.

```yaml
genotype:
  dna_schema: 1
  genotype_id: b3:4f9a2c…            # content address, see §5
  address:
    space_id: en-US.s3               # immutable address-space artifact (§7)
    seed_id: s1
    index: 8812440371
  ruleset_version: 1.4.2
  strategy: morphemic_composition
  derivation:                        # replayable; the ops ARE the mixed-radix digits
    - {op: select_template, value: T_trochee_open}
    - {op: select_morpheme, slot: initial, value: mor.lat.corv}
    - {op: select_suffix,   slot: final,   value: mor.aff.ane}
    - {op: apply_linking,   rule: R_hiatus_none}
    - {op: realize,         rules: [G_k_c, G_ɔː_or, G_v_v, G_eɪ_a_e], variant_rank: 0}
  phonoform:
    phonoform_id: b3:7c1e88…
    phonemes: [k, ɔː, r, v, eɪ, n]
    syllables: [[k, ɔː, r, v], [eɪ, n]]
    stress: "10"
  surface: "Corvane"
  normalized: "corvane"
  morphemes: [mor.lat.corv, mor.aff.ane]
```

**Every value here is discrete** — identifiers, integers, enum members, phoneme symbols. No floats anywhere. That is not an accident; see §5.

### 2.1 Compact form

Per [ADR-0012](../adr/0012-index-addressable-generation.md), `(space_id, seed_id, index, ruleset_version)` **replays the entire genotype**. Enumerated-but-not-admitted candidates store only that — ~16 bytes rather than ~1 KB.

The expanded form is materialised for admitted inventory only, because a new address space orphans compact-only rows (§7). Cheap insurance on the ~1% that reaches users.

---

## 3. Layer 1 — Phenotype

Measurements of the form. **Never a source of truth** — always recomputable from `(genotype, ruleset_version)`, and therefore a cache with a version key rather than durable state.

### 3.1 Three scopes, and why conflating them is expensive

Phenotype fields do not all key off the same thing, and treating them uniformly means recomputing identical values eight times per phonological form:

| Scope | Key | Fields |
|---|---|---|
| **Phonoform** | `phonoform_id` | pronounceability, phonotactic legality, syllable count, stress pattern, cross-linguistic pronounceability, sound-symbolic connotation |
| **Surface** | `normalized` | spellability, round-trip fidelity, typicality, distinctiveness, memorability, trademark-strength class |
| **Derivation** | `genotype_id` | concept tags, morpheme-derived connotation, saturation penalty |

The eight orthographic variants of one phonological form ([ADR-0011](../adr/0011-two-tier-phoneme-orthography.md)) **share every phonoform-scoped score.** Pronounceability is a property of the sound; spelling cannot change it. Scoring it per variant would be eight times the work for one answer.

```yaml
phenotype:
  scoring_ruleset_version: 1.4.2
  computed_for: {phonoform_id: …, normalized: …, genotype_id: …}
  phonoform_scope:
    pronounceability: 0.82
    phonotactic_legality: 1.0
    syllable_count: 2
    cross_linguistic: {en-US: 0.94, es-ES: 0.88, ja-JP: 0.71, _min: 0.71}
  surface_scope:
    spellability: 0.74
    round_trip_fidelity: 0.91
    typicality: 0.68
    distinctiveness: 0.79
    trademark_strength: fanciful
  derivation_scope:
    concept_tags: [wn:raven.n.01, concept:vigilance, concept:flight]
    connotation: {valence: 0.1, arousal: 0.4, competence: 0.6, sophistication: 0.5, …}
  gates:                              # discrete, hard — never weights
    safety: {status: clear, checked_packs: [en-US, es-ES, ja-JP, de-DE, pt-BR]}
    real_word_collision: false
    brand_collision: false
```

### 3.2 No composite score

Per [ADR-0007](../adr/0007-posture-relative-scoring.md), **no composite is stored.** The composite is a view computed at read time from these subscores under the active posture's weight vector. Storing one would freeze a ranking that is supposed to be relative to the founder's brand posture.

### 3.3 Gates are not scores

`gates` is discrete and sits apart from the continuous fields deliberately. A blocking safety flag removes a candidate under **every** posture; no weight vector can trade away "this word is obscene in Portuguese." Modelling it as a low score would make it tradeable, which is precisely wrong.

---

## 4. Layers 2 and 3

### 4.1 Environment — what the world says

External, time-decaying, non-deterministic. Written only by `services/` adapters.

```yaml
environment:
  availability:
    - {tld: com, status: registered, source: zone_file, confidence: 0.99,
       checked_at: 2026-08-04T09:12:00Z, expires_at: 2026-08-05T09:12:00Z}
    - {tld: com, variant: "korvane", status: available, source: registrar,
       confidence: 1.0, price_cents: 1299, checked_at: …, expires_at: …}
  trademark_signals:
    - {mark: "CORVAIN", jurisdiction: US, nice_class: 42, status: live,
       match_type: phonetic, similarity: 0.87, source_record_id: …}
```

**Two invariants:**

- **Never collapse to a boolean.** There is no `available: true` field. Every fact carries `source`, `confidence`, `checked_at`, and `expires_at`, because sources genuinely differ in authority — DNS is a hint, a registrar is authoritative ([ADR-0005](../adr/0005-tiered-availability.md)). Reads take the highest-confidence unexpired fact.
- **Evidence, never verdicts.** No `is_clear`, no `risk_level`. Structural, per [ADR-0009](../adr/0009-trademark-signals-not-verdicts.md) — a schema with no verdict field cannot grow a verdict UI by accident.

### 4.2 Reception — what humans decided

The only tenant-scoped layer, and an append-only event log rather than mutable state: run membership and rank, semantic fit for a specific brief, shortlist entries, votes, comments, and the decision.

A `decision` stores a **snapshot** of the environment layer as it stood at decision time. Founders will ask "was it available when we chose it?" and that answer must not depend on live data that has since moved.

---

## 5. Identity and hashing

### 5.1 Three identifiers, three jobs

Conflating these is a predictable source of confusion, so they are named distinctly from the start:

| Identifier | Identifies | Cardinality |
|---|---|---|
| `genotype_id` | one **derivation** | one per index |
| `phonoform_id` | one **pronunciation** | one per ~8 variants |
| `normalized` | one **name** | the user-facing unit |

**A name may have several genotypes.** *Corvane* can be reached by morphemic composition and independently by phonotactic construction. These are not collisions to discard — a **convergently derived** name sits in a dense, natural region of the space, which is weak evidence of quality. All derivations are retained, their concept tags union, and convergence is recorded as a signal.

### 5.2 The hashing rule

> **Hash the genotype. Never hash the phenotype.**

Genotype is entirely discrete, so its canonical JSON is byte-identical on every platform and Python version — a stable content address.

Phenotype contains floats. Float repr differs across platforms, libraries, and compiler flags; `0.1 + 0.2` is a well-known hazard and hashing over it produces tests that pass on a laptop and fail on CI for reasons nobody can reproduce. **Phenotype is keyed by `(scope_id, scoring_ruleset_version)`, never fingerprinted.**

This also means recomputing every score cannot change a single candidate's identity — which is the property that lets us re-score the entire inventory without touching a foreign key.

---

## 6. Schema evolution

`dna_schema` is versioned **separately from `ruleset_version`**. They change at different rates, for different reasons, owned by different people: the ruleset changes when linguistics changes, the schema when engineering does. One version number for both would couple two unrelated release cadences.

**Rules:**

- **Additive within a major.** New optional fields only.
- **Unknown fields are preserved on round-trip.** A worker running an older schema that reads, modifies, and writes a record must not destroy a field it doesn't understand. During any rolling deploy, mixed versions run concurrently — without this rule, the older workers silently strip the newer ones' data.
- **Required fields need a major bump**, and a major bump needs a migration path.
- **Canonical definition is Pydantic v2**, with JSON Schema exported in CI for the TypeScript client ([ADR-0004](../adr/0004-python-engine-typescript-web.md)).

---

## 7. Address spaces are immutable artifacts

**This is a refinement to [ADR-0014](../adr/0014-append-only-rulesets.md) discovered while implementing its CI guard**, and it resolves a genuine tension the ADR left open.

ADR-0014 treats any address-relevant change — including a **weight** change, since weights feed quantised slot expansion — as requiring a MAJOR bump that invalidates old indices. But [M1.3's entire job is inducing weights from the corpus](03-generation-engine.md#12-sub-milestones), and weights will be retuned. Under a literal reading, routine tuning orphans the inventory. That is unworkable.

**Resolution: an address space is a named, immutable, content-addressed artifact, and `space_id` is part of the genotype.**

- Changing any address-relevant parameter **mints a new `space_id`**. It is never an in-place edit.
- **Old spaces are retained, not migrated.** Rows carrying `space_id: en-US.s3` stay replayable under the retained `s3` definition forever.
- New generation proceeds in `en-US.s4`. Nothing is orphaned, and no MAJOR bump is needed.

The append-only rule still holds *within* a space, and the CI guard already enforces exactly this: it fails on in-place mutation, which is precisely the operation that should mint a new space instead.

The cost is honest: retained space definitions accumulate, and a candidate's replayability depends on our never deleting the space that produced it. That makes address-space artifacts **as durable as the inventory itself** — a backup and retention concern, not merely a config one.

**Accepted as [ADR-0017](../adr/0017-immutable-address-spaces.md).**

---

## 8. The explainability contract

> **No number reaches a user without a Brand DNA field behind it.**

Every user-visible claim — a score, a badge, a ranking, an availability statement — must be traceable to a stored field, its layer, its writer, and its version. "82 for enterprise B2B" resolves to specific subscores under a named posture weight vector at a named ruleset version.

This is already a line in the [review checklist](../../CONTRIBUTING.md). It is what makes the product defensible when a founder asks why we ranked one name above another, eighteen months after we did.

---

## 9. What Brand DNA is not

Stated explicitly, because each of these is a plausible-looking mistake:

| Not | Why |
|---|---|
| A **god object** | Single-writer-per-layer. A subsystem that wants to write another's layer has a design problem, not a schema problem. |
| A **message bus** | It is a record, not a channel. Subsystems coordinate through the job pipeline. |
| The **source of truth for phenotype** | Phenotype is derived. It can be dropped and rebuilt from genotype plus ruleset. |
| A **scratchpad** | Subsystem-local state stays local. If only one subsystem reads a field, it does not belong here. |
| **Tenant data** | Layers 0–2 are global and shared across every user. Only reception is tenant-scoped. |

---

## 10. Resolved decisions

**1 · Environment facts are retained in full.** Every availability and trademark check is kept, not just the latest per `(name, tld, source)`.

The audit trail is the point: when a founder asks *"was it available when we chose it?"*, the decision snapshot alone is an assertion — the fact history is evidence. Domain pricing trends fall out as a byproduct.

⚠️ **The cost is real and lands on the highest-volume table in the system.** `availability_fact` grows without bound as the background sweeper refreshes inventory. This needs time-based partitioning and an archival tier **designed before M3 ships**, not retrofitted once the table is large enough to make migrations painful. Recorded as a constraint on M3.

**2 · Concept tags union across convergent derivations.** When *Corvane* is reached independently by morphemic composition and phonotactic construction, the tag sets merge, and convergence is recorded as a weak quality signal. The alternative — separate sets merged at query time — is more faithful to provenance but complicates every retrieval path for a distinction users never see.

**3 · `dna_schema` v1 freezes after M1.5**, once morphemes and semantics are real. Freezing now, before the morpheme inventory exists, would guarantee a major bump within a fortnight.
