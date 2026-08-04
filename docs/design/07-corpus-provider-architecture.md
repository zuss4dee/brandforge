# Corpus Provider Architecture

**Status:** Approved v1.0 · **Date:** 2026-08-04
**Related:** [M1.0 Corpus Assembly](06-m1-0-corpus-assembly.md) · [ADR-0013](../adr/0013-typicality-distinctiveness-objective.md) · [ADR-0016](../adr/0016-uspto-brand-corpus.md) · [ADR-0018](../adr/0018-case-files-over-raw-xml.md)

---

## 0. The objective, and the trap

BrandForge should be a **Brand Intelligence Engine**, not a USPTO naming engine. Adding a corpus must mean implementing a provider, never modifying the engine.

Agreed. But the naive version of this — one `CorpusProvider` interface returning names, with the pipeline unioning them — is worse than not building it, for three reasons.

### 0.1 The listed sources are not the same kind of thing

They differ along an axis that determines how they may be *used*, not merely how they are fetched:

| Kind | Sources | Character |
|---|---|---|
| **Registry** | USPTO, EUIPO, Companies House | Exhaustive, legally filed, mostly unremarkable. Millions of rows |
| **Curated** | YC, Crunchbase | Small, high signal, **survivorship-biased**. Thousands of rows |
| **Usage** | Product Hunt, GitHub orgs, App Store, Play Store | Self-selected, noisy, current, informal |
| **Internal** | BrandForge's own inventory | **Our own output** |

### 0.2 Naive union destroys the curated sources

USPTO contributes ~8M marks. YC contributes ~5k names. Union them unweighted and **USPTO outvotes YC roughly 1600:1** — the highest-signal corpus we have becomes statistical noise, and every induced weight reflects the register's mediocrity.

This is the [risk-7 problem](03-generation-engine.md#13-risks) made worse by success: adding good sources would *dilute* rather than improve, and every intrinsic metric would look fine throughout.

> **Therefore the abstraction must carry role and weight, not just records.** A provider that only yields names is not enough information to use it correctly.

### 0.3 The internal corpus is a model-collapse hazard

"Internal BrandForge corpus" is the most dangerous item on the list, and it deserves naming plainly.

If we induce phonotactic weights from names **we generated**, we amplify our own priors, then induce from the amplified output, and so on. This is autophagy — the generative equivalent of a photocopy of a photocopy. It would show up as *rising* typicality scores and *falling* diversity, which is easy to misread as improvement.

Our own output may inform saturation and novelty distance. **It must never inform induction.** Not as a policy someone remembers — as a gate that fails the build.

### 0.4 Licence heterogeneity is the sharpest edge

[ADR-0016](../adr/0016-uspto-brand-corpus.md) chose USPTO *specifically* because public-domain licensing places no constraint on derived models. The listed sources are wildly heterogeneous:

- USPTO, EUIPO, Companies House — public / open data
- Crunchbase — **commercially licensed**, frequently restricting derived-model use
- GitHub, Product Hunt, App Store, Play Store — **terms-of-service governed**; scraping exposure

A uniform provider interface makes these look interchangeable. Somebody — plausibly a future engineer under deadline, plausibly me — will implement a Crunchbase provider and plug it into induction, and the constraint will be discovered at diligence, after the engine has been induced from it. That is precisely the exposure ADR-0016 exists to prevent, reintroduced through the abstraction meant to be an improvement.

> **Therefore licence is a first-class field of the interface, and it gates permitted use mechanically.**

---

## 1. The design

Three concepts, not one.

```
   ProviderDescriptor        what this source IS
        │                    (kind, licence, jurisdiction, trust, scale)
        ▼
   CorpusProvider            how to GET it
        │                    (acquire → extract → map)
        ▼
   CorpusRecord              a canonical row
        │
        ▼
   CorpusBlend               how sources COMBINE
                             (weights + roles, versioned, content-addressed)
```

### 1.1 Separation of duties

The split that keeps providers thin and the pipeline uniform:

| Provider does | Pipeline does |
|---|---|
| Acquire (network, auth, pagination) | Universal structural rules (single token, charset, length) |
| Extract (unzip, parse, stream) | Tagging (dictionary word, acronym, profanity) |
| **Source-specific filtering** (e.g. USPTO `mark_drawing_code`) | Deduplication and saturation aggregation |
| Map to `CorpusRecord` | Tiering, blending, artifact emission |

A provider knows about *its source*. It knows nothing about phonotactics, tiers, or induction. Adding Companies House means writing acquire/extract/map — nothing else.

### 1.2 `ProviderDescriptor`

```yaml
id: uspto.case_files
name: USPTO Trademark Case Files Dataset
kind: registry                  # registry | curated | usage | internal
licence: public_domain          # drives permitted_uses — see §2
jurisdiction: US
locale: en-US
cadence: annual
expected_scale: 12_700_000
trust_tier: 3                   # 1 = highest signal … 4 = weakest
attribution_required: true
attribution: "Graham, Marco & Miller (2018)"
```

`trust_tier` and `kind` are what let a blend weight 5k YC names against 8M registry rows deliberately rather than accidentally.

### 1.3 `CorpusRecord`

```yaml
text: "CORVANE"              # as published
provider_id: uspto.case_files
source_ref: "78123456"       # serial number / company number / URL
first_seen: 2011-04-02
status: live                 # live | dead | unknown
categories: ["042"]          # Nice class / SIC / app category
source_fields: {…}           # provider-specific, retained not discarded
```

Deliberately minimal. Anything a provider knows that the common shape cannot hold goes in `source_fields` — retained, because [normalisation tags rather than discards](06-m1-0-corpus-assembly.md#41-the-governing-principle).

### 1.4 `CorpusBlend` — the artifact that makes weighting explicit

```yaml
blend_id: bf.blend.v1
providers:
  - {id: uspto.case_files, roles: [induction, saturation, novelty], weight: 1.0}
  - {id: yc.companies,     roles: [induction, evaluation],          weight: 400.0}
  - {id: bf.internal,      roles: [saturation, novelty],            weight: 1.0}
```

Content-addressed and versioned. Weighting is now a **reviewable artifact in a diff**, not a constant buried in an induction script.

Under [ADR-0017](../adr/0017-immutable-address-spaces.md), changing the blend changes induced weights, which **mints a new address space** — the existing machinery covers this with no new concept.

---

## 2. Licence gating — the mechanical part

`Use` is an enum: `INDUCTION`, `SATURATION`, `NOVELTY_REFERENCE`, `EVALUATION`, `DISPLAY`.

Permitted uses are **derived from the licence class in code**, never declared freely per provider. A provider author cannot grant themselves induction rights by editing a YAML field:

| Licence class | Permitted uses |
|---|---|
| `public_domain` | all |
| `open_attribution` | all (attribution enforced at artifact level) |
| `commercial_licensed` | saturation, novelty, display — **not induction** |
| `tos_restricted` | novelty, display |
| `internal_generated` | saturation, novelty — **never induction** (§0.3) |
| `unknown` | **nothing** — fail closed |

`unknown` failing closed is the important row. A new provider with an unset licence contributes to nothing at all, loudly, rather than defaulting into induction quietly.

### 2.1 Guards

Two new CI checks, following the pattern already established by the [engine purity](../adr/0006-pure-engine-boundary.md) and [append-only](../adr/0014-append-only-rulesets.md) guards — enforce what documentation cannot:

| Guard | Assertion |
|---|---|
| **Licence gate** | Every record in an induction artifact comes from a provider whose licence class permits `INDUCTION` |
| **Autophagy gate** | No `internal_generated` record appears in any induction artifact, under any blend |

Both operate on the artifact, not on intent — so they hold regardless of how the record arrived.

### 2.2 Holdout, extended

The [contamination guard](06-m1-0-corpus-assembly.md#53-the-ci-guard) currently checks one corpus. With curated providers this gets sharper, not looser: **YC and Crunchbase are plausible holdout sources *and* plausible induction sources.** The guard must run across the blended induction artifact, not per-provider — otherwise each provider passes individually while the blend is contaminated.

---

## 3. Cross-provider identity

The same name will appear in several sources. `CORVANE` may be a USPTO mark, a GitHub org, and an App Store publisher.

**Merge, don't duplicate.** Deduplication is by normalised form across the blend, aggregating per-provider counts rather than collapsing them:

```yaml
normalized: corvane
providers:
  uspto.case_files: {count: 3, live: 1, earliest: 2011}
  github.orgs:      {count: 1, live: 1, earliest: 2019}
convergent_provider_count: 2
```

Saturation is then computable **per provider and in aggregate** — because "registered 300 times at USPTO" and "300 GitHub orgs" are not the same fact and must not be summed into one number.

`convergent_provider_count` is a quality signal in its own right: a name independently present across registry, usage, and curated sources is a genuinely used brand, not a defensive filing. This mirrors [convergent derivation](05-brand-dna.md#51-three-identifiers-three-jobs) in Brand DNA — the same principle applied to evidence rather than construction.

---

## 4. Validating the abstraction without building ten providers

**An interface validated against one implementation is a guess.** The second provider always reshapes it — that is not a risk to mitigate, it is a near-certainty to plan around.

Two cheap defences, both patterns already proven in this repo:

1. **A conformance test suite** every provider must pass — descriptor validity, streaming behaviour, licence declaration, deterministic mapping, empty-source handling, malformed-record quarantine.
2. **A `fake` provider** shipped in M1.0: a tiny in-memory source of a different `kind` and licence class from USPTO. It exercises the whole pipeline in CI with no network and no API key, and it forces the USPTO-specific assumptions out **before** they become load-bearing.

This is exactly the [toy language pack](03-generation-engine.md#104-proving-the-abstraction) trick from the engine design. It worked there for the same reason: an abstraction with one instance is English with extra YAML files.

**We build the interface, the USPTO provider, and the fake provider. Nothing else.** The other nine are designed for, not built — writing stubs for sources we have not read the terms of is how the licence problem in §0.4 arrives.

---

## 5. Impact on M1.0

Scope grows, honestly stated:

| Added | Cost |
|---|---|
| Provider protocol, descriptor, record, blend types | Small |
| Licence classes + permitted-use derivation | Small |
| Licence gate + autophagy CI guards | Small |
| Conformance suite + fake provider | Moderate |
| Restructure ingestion as provider-shaped | Moderate — cheap now, expensive after the pipeline exists |

**Unchanged:** the normalisation rules, tiering, dedup, holdout strategy, and every verified USPTO fact from [M1.0](06-m1-0-corpus-assembly.md). Those move from "the pipeline" to "the shared pipeline" without altering their content.

**M1.0's proof gains one clause:** the fake provider must traverse the full pipeline in CI with zero network access, and both licence guards must be demonstrated failing on a deliberate violation — the same standard applied to the M0 guards.

Accepted as **[ADR-0019](../adr/0019-corpus-provider-abstraction.md)**.
