# M1 — Name Generation Engine

**Status:** Approved v1.0 · **Date:** 2026-08-04
**Depends on:** [ADR-0003](../adr/0003-deterministic-generation.md), [ADR-0006](../adr/0006-pure-engine-boundary.md), [ADR-0008](../adr/0008-provenance-retrieval.md)
**Decisions from this design:** [ADR-0011](../adr/0011-two-tier-phoneme-orthography.md) · [ADR-0012](../adr/0012-index-addressable-generation.md) · [ADR-0013](../adr/0013-typicality-distinctiveness-objective.md) · [ADR-0014](../adr/0014-append-only-rulesets.md) · [ADR-0015](../adr/0015-sound-symbolic-semantics.md) · [ADR-0016](../adr/0016-uspto-brand-corpus.md)
**Companion:** [Evaluation Strategy](04-generation-evaluation.md)

---

## 0. Assumptions challenged

Before the design, the assumptions worth breaking — including two of my own from the system design.

### 0.1 "Pronounceable" is not the target

Pronounceability is necessary and nowhere near sufficient. *Tanamalo* is perfectly pronounceable and worthless. The target is **brandable**, which decomposes into four things pronounceability does not cover: prosodic shape, distinctiveness from existing names, spellability from hearing, and connotative fit.

Optimising for pronounceability alone produces the failure mode every naive generator has: fluent, forgettable mush.

### 0.2 English phonotactics is the wrong grammar

The instinct is to encode English phonotactics from a linguistics textbook. That grammar is far too permissive — it admits *strengths*, *sixths*, *blurbed*. Real brand names occupy a **much narrower region** of the legal space, and a textbook grammar wanders straight out of it. Hand-written grammars produce Tolkien elvish, not companies.

**Correction: induce the grammar's weights from a corpus of real brand names.** We hand-design the grammar's *structure* (for coverage of the space) and *learn its weights* (for plausibility within it).

### 0.3 The central objective is a tension, not a maximum

This is the core intellectual claim of the engine.

A good brand name must be **simultaneously typical and distinctive**:

- **Typical in form** — it must pattern like a company name (prosody, syllable shape, phoneme distribution). Fail this and it reads as a random string.
- **Distinctive in token** — it must not be close to any existing name. Fail this and it is unusable, legally and practically.

These pull against each other. Maximising typicality alone regenerates the corpus (*Lumina*, *Nexus*, *Zenith*) — this is precisely the LLM mode-collapse failure from [ADR-0003](../adr/0003-deterministic-generation.md), reproduced by a different mechanism. Maximising distinctiveness alone produces *Xqthorp*.

**The engine's job is to occupy the high-typicality / high-distinctiveness quadrant, and to be able to *measure* that it does.** Everything downstream — grammar, saturation tracking, gates, evaluation — exists to serve this frontier. We call it the **Typicality–Distinctiveness (T–D) frontier**, and it is the organising principle of the whole engine.

```
         high typicality
              │
   REGENERATES│  ★ TARGET
   THE CORPUS │    REGION
   (Lumina)   │  (Vanta, Figma, Okta)
  ────────────┼────────────────  distinctiveness →
   GENERIC    │  RANDOM STRINGS
   MUSH       │  (Xqthorp)
              │
```

### 0.4 Syllables are not the right unit — *positions* are

A uniform syllable grammar misses that brand names are **positionally structured**. Initial syllables carry rich onsets (`str-`, `kr-`, `fl-`). Final syllables do enormous perceptual work and are strongly constrained (`-a`, `-o`, `-io`, `-ex`, `-ly`). Medial syllables are simple connective tissue.

**The grammar must be positionally conditioned.** One distribution per position class, not one distribution for all syllables.

### 0.5 Generate in sound, not in spelling

The largest structural correction to my earlier thinking.

`/kɔːrveɪn/` can be written *Corvane*, *Korvane*, *Corvain*, *Korvayne*. These are the **same name** phonologically and **different assets** commercially. Generating directly in orthography conflates two decisions that should be separate, and throws away the most valuable move available to us:

> When *Corvane.com* is taken, *Korvane.com* may be free — identical pronunciation, different asset.

**Decision: two-tier generation. A phonological skeleton is generated first; orthographic variants are realised from it.** Pronounceability is scored once in phoneme space. Spellability is scored on the realisation mapping. Availability is checked per variant.

### 0.6 My earlier claim about phonotactic candidates was wrong

In [ADR-0008](../adr/0008-provenance-retrieval.md) I wrote that purely phonotactic candidates "have weak provenance by nature" and can only be retrieved on structural filters. That was a real gap and it would have left the largest supply source semantically unreachable.

**It is fixable.** Sound-symbolic structure attaches meaning at the *phoneme* level, independent of morphemes — front vowels pattern with smallness and speed, voiced stops with weight, sibilants with velocity. Effect sizes in the literature are modest and partly language-specific, so this must be a **weak, learned prior rather than a hard rule** — but it is enough to give every candidate a connotative vector and therefore a semantic handle. See §6.3. ADR-0008 should be amended when this design is approved.

### 0.7 The algorithm is not the moat

The user framed M1 as "core IP," so this needs saying plainly: **the generation algorithm is not defensible.** It is describable in a paper and reimplementable in a quarter. Anything we can write down, a competitor can write down.

What is actually defensible, in increasing order of strength:

| Asset | Why it defends |
|---|---|
| Curated morpheme inventory with semantic tags | Years of hand-curation; irreducibly manual |
| Induced typicality model + assembled brand corpus | Corpus assembly and cleaning is the real work |
| Human-labelled evaluation set | Expensive, slow, and the thing that lets us improve safely |
| **Morpheme saturation data** (§5.3) | Compounds — grows with every corpus refresh |
| **Accumulated inventory + availability history** | Compounds fastest; a competitor starts at zero |

**Strategic recommendation: trade secret and data moat, not patent.** Patenting requires public disclosure of the mechanism, costs real money, and is close to unenforceable for a startup against a competitor who implements it slightly differently. We would be paying to teach competitors the algorithm. Keep the ruleset bundles and corpora private; publish nothing about the induction pipeline.

---

## 1. Architecture

Five layers. Each is a pure function ([ADR-0006](../adr/0006-pure-engine-boundary.md)); each is independently testable.

```
  ┌─────────────────────────────────────────────────────────────┐
 0│  ADDRESS SPACE      index i ─(seed-keyed permutation)→ digits │
  ├─────────────────────────────────────────────────────────────┤
 1│  DERIVATION         digits → template + morphemes + rules     │
  ├─────────────────────────────────────────────────────────────┤
 2│  PHONOLOGY          derivation → phoneme seq + syllables +    │
  │                     stress                                    │
  ├─────────────────────────────────────────────────────────────┤
 3│  ORTHOGRAPHY        phonemes → ranked spelling variants        │
  ├─────────────────────────────────────────────────────────────┤
 4│  SEMANTICS          morphemes + sound symbolism → concept      │
  │                     tags + connotation vector                  │
  ├─────────────────────────────────────────────────────────────┤
 5│  GATES & LIFECYCLE  cheapest-first funnel → admitted inventory │
  └─────────────────────────────────────────────────────────────┘
```

Everything is parameterised by a **Ruleset** (§9) and a **Language Pack** (§10). The engine core contains **zero English-specific logic** — a constraint enforced by a test that runs the whole pipeline against a synthetic toy language (§10.4).

---

## 2. The Address Space — deterministic generation

### 2.1 Why seeded RNG is the wrong mechanism

The obvious approach — seed a PRNG, draw candidates in a loop — is fragile in ways that matter for a system whose entire value proposition is reproducibility:

- **Order-fragile.** Adding one `random()` call anywhere shifts every subsequent draw. A refactor silently changes all output.
- **Not parallelisable** without careful stream-splitting.
- **Not resumable.** A crash at candidate 4,000,000 means replaying from zero.
- **Produces duplicates.** Sampling with replacement from a large space hits birthday-paradox collisions constantly.

### 2.2 The mechanism: index-addressable enumeration

Model the candidate space as a **mixed-radix number**. Every choice point in a derivation — template, onset, nucleus, coda, morpheme, orthographic variant — is a digit with a finite radix.

```
space  = [r₀, r₁, r₂, …, r_{n-1}]        radices per choice point
|S|    = Π rᵢ                             total addressable candidates
decode(i) → (d₀, d₁, …, d_{n-1})          mixed-radix digits
build(digits, ruleset) → candidate        pure, total function
```

Sequential indices produce highly correlated candidates (all sharing a prefix), so we interpose a **seed-keyed format-preserving permutation** π over `[0, |S|)` — a small Feistel network with cycle-walking to handle non-power-of-two domain sizes:

```
candidate(seed, i) = build(decode(π_seed(i)), ruleset)
```

### 2.3 What this buys

| Property | Consequence |
|---|---|
| **Stateless** | No RNG state to thread, checkpoint, or corrupt |
| **Embarrassingly parallel** | Shard by index range; workers need zero coordination |
| **Resumable** | Crash at *i* → restart at *i* |
| **Reproducible** | `(seed, ruleset_version, i)` → exactly one candidate, forever |
| **Zero duplicates** | A permutation is a bijection — it visits each point exactly **once**. Not "few duplicates" — *none*, by construction |
| **Auditable** | Any candidate a user ever sees can be traced to its address and replayed |

The zero-duplicate property alone justifies the design. Sampling-based generators spend increasing effort on deduplication as they scale; this one cannot produce a duplicate derivation at all.

### 2.4 Weighted choices without breaking the bijection

We need non-uniform choices (common onsets should appear more often than rare ones) but must preserve the permutation property. **Quantised weight expansion:** each choice point's digit domain is expanded to `W` slots, where choice *c* occupies `round(w_c · W)` contiguous slots. Decoding maps slot → choice.

The distribution is approximated to resolution `1/W` (with `W = 1024`, well within the precision of our induced weights), the space stays a clean mixed-radix product, and the bijection is preserved. Alternatives — rejection sampling, alias tables — either break the bijection or reintroduce state.

### 2.5 Consequence: the index *is* the provenance

This falls out of the design and it is worth stating separately, because it collapses a storage problem that would otherwise be significant.

If `(seed, ruleset_version, space_id, index)` deterministically reproduces a candidate **and its entire derivation**, then that tuple *is* the complete provenance. Roughly **16 bytes**, not the ~1 KB a serialised derivation tree would cost.

At 10⁷ enumerated candidates that is the difference between ~160 MB and ~10 GB. See §7 for how this is exploited and where the expanded form is still required.

---

## 3. Phonological Layer

### 3.1 Representation

Phonemes are feature bundles, not opaque symbols — features are what make constraints expressible and language packs portable.

```yaml
- id: /r/
  ipa: "ɹ"
  arpabet: "R"
  class: consonant
  manner: approximant
  place: alveolar
  voice: true
  sonority: 3
```

Sonority ranking (obstruent 1 < nasal 2 < liquid 3 < glide 4 < vowel 5) drives the **Sonority Sequencing Principle**: sonority rises monotonically to the nucleus and falls after it. This single constraint eliminates most illegal clusters without enumerating them.

### 3.2 Positional syllable grammar

Three position classes, each with its own inventories and weights (per §0.4):

| Position | Onset | Nucleus | Coda |
|---|---|---|---|
| `σ_initial` | rich — clusters permitted | full inventory | simple |
| `σ_medial` | simple — usually single C | reduced inventory | rare |
| `σ_final` | simple | full | strongly prefers **∅** (open syllable) |

### 3.3 Prosodic templates

Templates are first-class ruleset objects specifying syllable count, position classes, and stress:

```yaml
- id: T_trochee_open
  syllables: [σ_initial, σ_final]
  stress: "10"
  shape: [CVC, CV]
  weight: <induced>
  exemplars: [Vanta, Figma, Okta, Miro]
```

> ⚠️ **These templates and their exemplars are seed hypotheses, not findings.** I have not measured the prosodic distribution of real brand names, and I am not going to assert one from intuition. The `weight` field is deliberately `<induced>`: M1.0 assembles the corpus and M1.3 measures the actual distribution. If the data says brand names are not predominantly trochaic, the templates change. **The method is the design; the numbers are an empirical question.**

### 3.4 Constraint set

Beyond grammar-guaranteed legality:

| Constraint | Purpose |
|---|---|
| Sonority sequencing | Cluster legality |
| **OCP** (Obligatory Contour Principle) | Blocks adjacent near-identical segments — the *"Sassasa"* problem |
| Max cluster complexity | Positional caps on onset/coda size |
| Hiatus resolution | Governs vowel-vowel sequences across morpheme joins |
| Degemination | Collapses doubled consonants at joins |
| Stress well-formedness | One primary stress; no stress clash |

---

## 4. Orthographic Realisation Layer

### 4.1 Realisation rules

Each rule maps a phoneme (in context) to a grapheme, carrying three annotations:

```yaml
- id: G_k_k
  phoneme: /k/
  grapheme: "k"
  contexts: [onset_initial, onset_medial]
  fidelity: 0.97        # P(naive reader recovers the phoneme)
  frequency: <induced>  # rate in the brand corpus
  register: [modern, tech, playful]
```

`/k/` alone realises as `c`, `k`, `q`, `ck`, `ch` — and the choice is a genuine branding decision, not noise. `k` reads modern and tech; `c` reads classical. The `register` tag makes that choice steerable by posture.

### 4.2 Variant generation

Each phonological form yields the top-*K* orthographic variants (proposed *K* = 8), ranked by a combination of fidelity, corpus frequency, and register fit — subject to hard constraints: orthographic well-formedness, no unintended real-word collision, no collision with a known brand.

### 4.3 The round-trip test

Spellability gets a concrete, mechanical definition rather than a vibe:

```
phonemes → realise → graphemes → g2p → phonemes'
round_trip_fidelity = alignment_score(phonemes, phonemes')
```

A name whose spelling does not recover its own pronunciation fails the "say it over the phone" test. This is directly measurable, cheap, and needs no human judgement.

### 4.4 The product capability this unlocks

Because variants are grouped under a shared phonological form, the inventory natively supports:

> *"**Corvane.com** is taken. **Korvane.com** is available — same pronunciation, slightly more modern spelling."*

No competitor does this well, because it is only possible if you generated in phoneme space to begin with. It is a direct consequence of §0.5 and, in my judgement, the single most commercially valuable feature in M1.

---

## 5. Morpheme Inventory

### 5.1 Schema

```yaml
- id: mor.lat.corv
  type: root                      # root | prefix | suffix | combining_form
  origin: latin
  gloss: "raven, crow"
  phonemic: [k, ɔː, r, v]
  allomorphs: [corv, corb]
  slots: [initial, medial]        # where it may appear
  linking_vowels: [i, o]
  register: literary
  productivity: 0.4               # how freely it combines
  saturation:
    brand_count: 12               # occurrences in the brand corpus
    percentile: 0.31
  semantics:
    denotative: [wn:raven.n.01, concept:bird, concept:intelligence]
    connotative: {valence: 0.1, arousal: 0.4, competence: 0.6,
                  sophistication: 0.5, ruggedness: 0.3, sincerity: 0.2}
    domains: {security: 0.4, aerospace: 0.3}
  attested: [Corvus, Corvid]
  status: active                  # active | deprecated | retired
  added_in: 1.0.0                 # append-only discipline (§9.3)
```

### 5.2 Composition

Morphemes combine under explicit, versioned rules: slot compatibility, linking-vowel insertion (Latin *-i-*, Greek *-o-*), hiatus resolution, degemination, stress reassignment. Every rule application is a recorded derivation step.

### 5.3 Saturation — the anti-mode-collapse mechanism

`saturation.brand_count` records how heavily a morpheme is already used in real brands. `lum-` (Lumina, Lumen, Luminary, Illumina…) is saturated. `corv-` is not.

**Saturation feeds a generation-time penalty**, so the engine actively avoids exhausted morphemes rather than rediscovering them. This is the structural answer to the mode-collapse problem that defeats LLM-based generators — and unlike a prompt instruction, it is measured, versioned, and improves automatically with every corpus refresh.

It is also, per §0.7, one of the genuinely compounding assets in the product.

---

## 6. Semantic Tagging System

Three axes plus a phoneme-level signal. Free-text tags are explicitly rejected — they degrade into inconsistent mush within months and cannot be composed.

### 6.1 Denotative — controlled vocabulary

Literal meaning, bound to a concept ontology (WordNet synset IDs where available, curated concept nodes elsewhere). Hierarchical, so `corv-` → raven → bird → animal supports retrieval at multiple levels of abstraction.

### 6.2 Connotative — a fixed vector space

A fixed-dimension vector, grounded in two established frameworks rather than invented axes:

- **Valence / Arousal / Dominance** — the standard affective-norm dimensions, with published lexicon norms available to seed them.
- **Aaker's brand-personality dimensions** — Sincerity, Excitement, Competence, Sophistication, Ruggedness.

Fixed dimensionality means connotation is composable (vectors add), comparable (cosine similarity), and directly matchable to a **posture** ([ADR-0007](../adr/0007-posture-relative-scoring.md)) — each posture is a target vector in the same space. Posture fit becomes a cosine, not a heuristic.

### 6.3 Sound symbolism — semantics without morphemes

This closes the gap from §0.6. Phoneme-level priors contribute to the connotation vector:

| Signal | Prior direction |
|---|---|
| Front vowels /i, ɪ, e/ | small, fast, precise, sharp |
| Low/back vowels /ɑ, ɔ, o/ | large, stable, weighty |
| Voiceless stops /p, t, k/ | sharp, fast, crisp |
| Voiced stops /b, d, g/ | heavy, solid, grounded |
| Sibilants /s, z, ʃ/ | speed, technology, slickness |
| Sonorants /l, m, n, r/ | smooth, warm, organic |

⚠️ **Honesty about the evidence:** phonosemantic effects are real and replicated, but effect sizes are modest and partly language-specific. These are **weak priors with learned weights, validated empirically in evaluation** — never hard rules. If M1.7 shows they carry no signal for our raters, the weights go to zero and we lose nothing structural.

Their structural value stands regardless: **every candidate gets a connotation vector, including the morpheme-free phonotactic ones.** Without this, the largest supply source is semantically unreachable.

### 6.4 Composition

| Axis | Rule |
|---|---|
| Denotative | Head-weighted union — the final morpheme dominates, modifiers contribute at reduced weight |
| Connotative | Salience-weighted mean of morpheme vectors, **then** additive sound-symbolic adjustment from the phonological form |
| Domain | Weighted max across contributing morphemes |

Composition is deterministic and recorded in the derivation, so a name's semantics are as replayable as its form.

---

## 7. Provenance Model

### 7.1 Two representations

Per §2.5, provenance has a compact form and an expanded form, and the split is a deliberate storage decision:

**Compact (~16 bytes) — for every enumerated candidate**
```
(space_id, ruleset_version, seed_id, index)
```
Sufficient to replay the entire derivation.

**Expanded — only for admitted inventory** (the ~1% surviving the gates)
```yaml
candidate_id: <blake3 of canonical derivation>   # content address
ruleset: {version: 1.4.2, hash: b3:9f2c…}
address: {space_id: S3, seed_id: s1, index: 8812440371}
strategy: morphemic_composition
derivation:
  - {op: select_template,   value: T_trochee_open}
  - {op: select_morpheme,   slot: initial, value: mor.lat.corv}
  - {op: select_suffix,     slot: final,   value: mor.aff.ane}
  - {op: apply_linking,     rule: R_hiatus_none}
  - {op: realize,           rules: [G_k_c, G_ɔː_or, G_v_v, G_eɪ_a_e], variant_rank: 0}
phonological: {phonemes: [k,ɔː,r,v,eɪ,n], syllables: [[k,ɔː,r,v],[eɪ,n]], stress: "10"}
surface: "Corvane"
normalized: "corvane"
semantics: {...composed per §6.4...}
```

### 7.2 The replay contract

```
replay(provenance, ruleset) == surface
```

Enforced in CI against frozen golden fixtures. A ruleset change that breaks replay is a **build failure**, not a surprise discovered later.

### 7.3 Content addressing and convergent derivation

`candidate_id = blake3(canonical_derivation)` gives stable cross-run identity and free deduplication.

But the *name* is keyed by `normalized`, not by derivation — because **the same surface form can arise from different derivations.** These are not collisions to discard; a name reached independently by both morphemic composition and phonotactic construction is **convergently derived**, which is weak evidence of quality (it sits in a dense, natural region of the space). We record all derivations for a name and treat convergence as a signal.

### 7.4 Why expanded provenance must be retained

For admitted inventory we store the expanded form even though the compact form is theoretically sufficient. The reason is §9.2: a **MAJOR ruleset bump invalidates the address space**, and compact rows become unreplayable. Expanded provenance survives ruleset generations. Keeping it for the ~1% that reaches users is cheap insurance against permanently orphaning the inventory.

---

## 8. Candidate Lifecycle

### 8.1 The funnel

Gates ordered **cheapest-first**, so expensive checks only ever see survivors:

```
  ENUMERATED     index i
       ↓         decode + build            [pure, ~µs]
  CONSTRUCTED    phonological form
       ↓
  G1  structural legality                  [free — grammar guarantees it]
  G2  length / syllable bounds             [trivial]
  G3  typicality floor                     [n-gram lookup]
  G4  novelty floor — distance from corpus [indexed phonetic lookup]
  G5  OCP / prosodic well-formedness       [cheap]
       ↓
  REALISED       orthographic variants
       ↓
  G6  real-word collision                  [lexicon lookup]
  G7  known-brand collision (exact+phonetic)[indexed]
  G8  safety — ALL language packs          [lexicon, union]
       ↓
  DEDUPED        by `normalized`
       ↓
  ADMITTED       → inventory row + linguistic scores
       ↓
  [M3] ENRICHED  → availability facts
       ↓
  ARCHIVED       permanently unavailable + low score
```

### 8.2 Design notes

**G8 runs across every language pack, always** — not just the target market. A name that is obscene in a language we are not currently selling into is still a brand catastrophe waiting for the founder's first international customer. This is a hard gate; no posture or weight can override it.

**Archived, never deleted.** We must remember what we have already seen and rejected — both to avoid re-surfacing it and to preserve the audit trail.

**Expected survival rates are targets to measure, not claims.** The funnel's shape is an empirical output of M1.6, and the gate thresholds are the primary tuning surface for the T–D frontier (§0.3).

---

## 9. Ruleset Versioning

### 9.1 What a ruleset is

A content-addressed bundle of everything that determines output: phoneme inventory, syllable templates and weights, constraint set, morpheme inventory, orthography rules, sound-symbolic priors, gate thresholds. Distributed as a directory of YAML plus a lockfile of hashes, loaded **immutably** at worker boot.

### 9.2 Version semantics tied to address-space stability

The versioning scheme is defined by its effect on the address space — which is the only definition that actually protects reproducibility:

| Bump | Address space | Guarantee |
|---|---|---|
| **PATCH** | Unchanged | Same index → same candidate. Gates/thresholds/scoring only. |
| **MINOR** | **Extended by appending** | Old indices decode **identically**; new indices reach new candidates. |
| **MAJOR** | Restructured | Old indices invalid. Requires re-anchoring — see §7.4. |

### 9.3 Append-only discipline

**The single operational rule that makes all of the above hold: inventory entries are never removed or reordered.** Deprecation is a status flag (`deprecated`, `retired`) plus a gate exclusion — never a deletion.

Removing one morpheme from the middle of an inventory shifts every subsequent radix digit and silently re-points every index in the system. Every stored provenance would then replay to the wrong name, with no error raised. This is the most dangerous single failure mode in the engine, and it is prevented by a CI check that diffs inventory files and fails on any non-append change without a MAJOR bump.

---

## 10. Multilingual Extensibility

### 10.1 Language Pack

```
packs/en-US/
  phonemes.yaml          # inventory + features
  phonotactics.yaml      # clusters, constraints, position classes
  orthography.yaml       # g2p + p2g realisation rules
  prosody.yaml           # templates, stress rules
  corpus/brands.txt      # for weight induction
  safety/lexicon.yaml    # profanity + unfortunate meanings, incl. phonetic near-misses
  sound_symbolism.yaml   # phoneme-level connotation priors
```

The engine core is pack-parameterised with **no English hardcoded anywhere**.

### 10.2 Two distinct requirements

These are usually conflated, and conflating them produces a system that can only ever serve one market:

1. **Generation *in* a language** — a Japanese brand for a Japanese market: generate from the `ja-JP` pack.
2. **Evaluation *across* languages** — a global brand must be pronounceable everywhere it will be spoken.

### 10.3 Market basket

A brief carries a weighted basket: `[(en-US, 0.5), (es-ES, 0.2), (ja-JP, 0.2), (de-DE, 0.1)]`.

Cross-linguistic pronounceability is the **weighted mean, subject to a hard minimum floor** — a name must not be unpronounceable in *any* basket market, however small its weight. A weighted mean alone would let a large market average away a catastrophic failure in a small one.

Two further checks in the basket:
- **Transliteration robustness** — does the name survive being written in Katakana, Cyrillic, or Arabic script and back?
- **Global-safe phoneme mode** — an optional restriction to phonemes with high cross-linguistic coverage. Segments like /θ/, /ɹ/, and complex consonant clusters are absent or difficult in many of the world's languages; excluding them yields names that travel. Proposed as a brief-level toggle.

### 10.4 Proving the abstraction

A language pack abstraction that has only ever run one language is not an abstraction — it is English with extra YAML files.

**A synthetic toy language pack ships in M1**, with a small artificial phoneme inventory and orthography, and a CI test runs the full pipeline against it. This forces the English assumptions out *before* they are load-bearing, at a fraction of the cost of discovering them during a real second-language build.

---

## 11. Scope boundaries for M1

**In:** the five layers, the address space, ruleset versioning, en-US pack, toy pack, gates, lifecycle, CLI, evaluation harness.

**Out:** LLM concept expansion (M5), availability (M3), trademark (M7), API/UI (M4/M6), learned ranking (M10).

**Designed now, built later:** the interface for **brief-conditioned construction** — restricting the address space to a subspace derived from brief-specific morphemes. M5 plugs into it. Designing the seam now costs little; retrofitting it later means reworking the address space, which is exactly the change §9.2 makes expensive.

---

## 12. Sub-milestones

| # | Deliverable | Proof |
|---|---|---|
| **M1.0** | Brand corpus assembled + cleaned; induction tooling | ≥50k real brand names, deduped, licence-clear |
| **M1.1** | Phonological core — features, syllabifier, grammar, templates | Property test: 10⁶ generated forms, zero constraint violations |
| **M1.2** | Address space — mixed-radix, Feistel permutation | Determinism: `(seed,i)` → identical candidate across processes; **zero duplicates in 10⁷** |
| **M1.3** | Weight induction from corpus; typicality model | Held-out real brands score in the top decile of typicality |
| **M1.4** | Orthographic realisation + round-trip scoring | ≥K variants/form; round-trip fidelity distribution reported |
| **M1.5** | Morpheme inventory + semantic tagging + saturation | ~800 morphemes, **LLM-drafted and human-reviewed entry by entry**; inter-annotator agreement checked on a sample; saturation computed against corpus |
| **M1.6** | Gates, lifecycle, dedupe, CLI | 10⁷ enumerated → funnel measured end-to-end |
| **M1.7** | Evaluation harness + human study | See [Evaluation Strategy](04-generation-evaluation.md) |

M1.0 is first because **everything downstream depends on the corpus** — templates, weights, typicality, saturation, and novelty distance are all induced from it. It is also the item with a legal dependency (§13), which makes it the critical path within the critical path.

---

## 13. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | ~~Brand corpus licensing~~ — **resolved**: USPTO bulk trademark data, public domain | ✅ Closed | [ADR-0016](../adr/0016-uspto-brand-corpus.md). Residual risk moves to row 7. |
| 2 | Hand-built grammar produces legal-but-lifeless output | 🔴 High | Corpus induction (§0.2); the M1.7 indistinguishability proof is the gate |
| 3 | Non-append ruleset edit silently re-points every index | 🔴 High | CI diff check on inventory files (§9.3) |
| 4 | Morpheme tagging is slow, manual, and inconsistent | 🟠 Medium | Controlled vocabulary (§6.1); inter-annotator agreement checks; LLM-assisted *drafting* with human review |
| 5 | Sound-symbolic priors carry no real signal | 🟡 Low | Weak learned weights; falsifiable in M1.7; zero structural cost if they fail |
| 6 | Address space too large to enumerate usefully | 🟡 Low | Subspace restriction by template/length; enumeration is sharded and resumable anyway |
| 7 | **Registered marks ≠ successful brands** — the USPTO register is mostly unremarkable, biasing typicality toward the merely legal | 🟠 Medium | Hand-curated quality overlay; evaluation ceiling drawn from *funded startups*, not the register; substantial normalisation in M1.0 |

**Risk 2 is now the live one.** With the corpus source settled ([ADR-0016](../adr/0016-uspto-brand-corpus.md)), the open question is whether a hand-designed grammar with induced weights actually produces output that reads as real. That is precisely what the M1.7 indistinguishability study exists to answer, and it is allowed to fail — which is the point of running it.

**Risk 7 is the subtle one.** Anyone can register a trademark, and most registrations are forgettable. Inducing typicality from the register teaches the engine what is *legally filed*, not what is *good*. The curated overlay and the funded-startup evaluation ceiling are what keep this honest; without them we would optimise confidently toward mediocrity and the metrics would look fine throughout.
