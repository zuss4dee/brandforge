# ADR-0019: Corpus provider abstraction with mechanical licence gating

**Status:** Accepted
**Date:** 2026-08-04
**Implements:** [Corpus Provider Architecture](../design/07-corpus-provider-architecture.md)
**Relates to:** [ADR-0016](0016-uspto-brand-corpus.md) · [ADR-0018](0018-case-files-over-raw-xml.md)

## Context

BrandForge's objective is a **Brand Intelligence Engine**, not a USPTO naming engine. Adding a corpus — Companies House, EUIPO, YC, Product Hunt, GitHub organisations, app-store publishers, our own inventory — should mean implementing a provider, never modifying the engine.

A plain `CorpusProvider` returning names, with the pipeline unioning the results, would satisfy that requirement literally and fail it in three specific ways:

1. **The sources are not the same kind of thing.** Registries are exhaustive and mostly unremarkable; curated sources are tiny and survivorship-biased; usage sources are noisy and informal. A union weights them by row count, so ~8M USPTO marks outvote ~5k YC names roughly 1600:1 — **adding our best source would dilute rather than improve**, and every intrinsic metric would look healthy while it happened.

2. **Our own inventory is a model-collapse hazard.** Inducing weights from names we generated amplifies our own priors, which then feed the next induction. This presents as rising typicality and falling diversity — easy to misread as improvement.

3. **Licence heterogeneity is the sharpest edge.** ADR-0016 chose USPTO *specifically* for public-domain licensing. Crunchbase is commercially licensed with terms that commonly restrict derived-model use; GitHub, Product Hunt and the app stores are ToS-governed. A uniform interface makes these look interchangeable, and someone under deadline will wire a licensed source into induction. The constraint then surfaces at diligence — after the engine has been induced from it. That is the exact exposure ADR-0016 exists to prevent, reintroduced by the abstraction meant to improve things.

## Decision

**Three concepts, not one.**

1. **`ProviderDescriptor`** — what a source *is*: `kind` (registry / curated / usage / internal), `licence`, jurisdiction, cadence, expected scale, `trust_tier`, attribution.
2. **`CorpusProvider`** — how to *get* it: `acquire → extract → map`. Providers own acquisition and source-specific filtering. They know nothing about phonotactics, tiers, or induction.
3. **`CorpusBlend`** — how sources *combine*: a versioned, content-addressed artifact of per-provider roles and weights, so weighting is a reviewable diff rather than a constant in a script.

**Licence gates use mechanically.** `Use` ∈ {`INDUCTION`, `SATURATION`, `NOVELTY_REFERENCE`, `EVALUATION`, `DISPLAY`}. Permitted uses are **derived from the licence class in code**, never declared per provider — a provider author cannot grant themselves induction rights by editing YAML.

| Licence class | Permitted |
|---|---|
| `public_domain` | all |
| `open_attribution` | all, attribution enforced on artifacts |
| `commercial_licensed` | saturation, novelty, display — **not induction** |
| `tos_restricted` | novelty, display |
| `internal_generated` | saturation, novelty — **never induction** |
| `unknown` | **nothing — fail closed** |

**Two CI guards**, following the pattern of [ADR-0006](0006-pure-engine-boundary.md) and [ADR-0014](0014-append-only-rulesets.md):

- **Licence gate** — every record in an induction artifact comes from a provider permitted to feed induction.
- **Autophagy gate** — no `internal_generated` record reaches any induction artifact, under any blend.

Both operate on the emitted artifact, not on intent, so they hold regardless of how a record arrived.

**Build three things only:** the interface, the USPTO provider, and a `fake` provider of a different kind and licence class used to prove the abstraction in CI without network access.

## Alternatives considered

- **Single `CorpusProvider` returning names; pipeline unions them.** Simplest, and satisfies the stated requirement. Rejected on all three grounds above — particularly that it makes the licence problem invisible at exactly the moment it becomes expensive.
- **Licence as documentation, enforced in review.** Much less machinery. Rejected: this is a silent, high-consequence failure discovered late, which is the same class as the append-only failure and warrants the same treatment. Review does not catch what it cannot see in a diff.
- **Per-provider free declaration of permitted uses.** More flexible, allows genuine exceptions. Rejected: it makes the safety property editable by the person with an incentive to edit it. A genuine exception should require changing the licence-class table, which is a visible, reviewable, deliberate act.
- **Build stubs for all ten sources now.** Rejected: writing providers for sources whose terms we have not read is precisely how the §0.4 exposure arrives. Design for them; implement two.

## Consequences

- **Gained:** adding a corpus is implementing a provider. The engine, normalisation, tiering, dedup and holdout logic are untouched.
- **Gained:** curated sources can be weighted deliberately against registries, so adding good data improves rather than dilutes.
- **Gained:** the licence exposure becomes a build failure rather than a diligence finding.
- **Gained:** blend changes flow through [ADR-0017](0017-immutable-address-spaces.md)'s existing machinery — a re-weighted blend mints a new address space, no new concept required.
- **Accepted:** M1.0's scope grows by the protocol, licence machinery, guards, conformance suite, and fake provider. Cheap now; restructuring after the pipeline exists is not.
- **Accepted, and honest: the second real provider will reshape this interface.** An abstraction validated against one implementation is a guess. The conformance suite and the fake provider reduce the blast radius; they do not eliminate it. Expect a revision when Companies House or EUIPO lands, and treat that revision as expected cost rather than as a failure of this design.
- **Required:** the holdout contamination guard now runs across the **blended** induction artifact. Per-provider checks would let each source pass individually while the blend is contaminated.
