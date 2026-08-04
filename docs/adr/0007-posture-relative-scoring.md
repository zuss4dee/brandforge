# ADR-0007: Posture-relative scoring with stored subscores

**Status:** Accepted
**Date:** 2026-08-04

## Context

It is tempting to compute one "name quality score" and rank by it. This is wrong on its face: *Vanta* is excellent for B2B security and terrible for a children's bakery. *Bumble* is excellent for consumer social and unusable for a medical device. Quality is not a property of a name alone — it is a property of a name **relative to an intended brand posture.**

A single global score would also make the product's central output unexplainable, which is fatal when users are making a decision they'll live with for a decade.

## Decision

1. Score across **nine independent dimensions**, and **store every subscore.**
2. **Never store a composite.** The composite is a *view*, computed at read time by applying the active posture's weight vector to the stored subscores.
3. The founder selects a **posture** on the brief: `deep_tech | enterprise_b2b | consumer_playful | premium_luxury | clinical_trust`. Each posture is a named, versioned weight profile.
4. **Linguistic safety is a hard gate, not a weight.** A blocking safety flag removes a candidate under every posture. No weight vector can trade away "this word is obscene in Portuguese."

## Alternatives considered

- **Single global quality score.** Simple to build, simple to explain in marketing. Rejected: it is straightforwardly wrong, and it makes the ranking unexplainable and untunable.
- **Fully user-tunable sliders on all nine dimensions.** Maximum flexibility. Rejected for v1: it hands the user a nine-dimensional optimisation problem they have no basis to solve. Postures are opinionated presets — the right default. Advanced tuning can come later, on top of the same stored subscores.
- **Learned ranker from the start.** Rejected: we have no training data until users make choices. Deferred to M10, where it reweights the same stored dimensions rather than replacing them.

## Consequences

- **Accepted:** more storage per candidate, and composites are computed rather than indexed — so ranking a large result set costs CPU at read time. Mitigated by ranking only the retrieved slice, never the full inventory.
- **Gained:** full explainability. "82 for enterprise B2B: strong pronounceability, high trademark distinctiveness, penalised for four syllables" is a sentence we can generate from stored data.
- **Gained:** re-weighting is free. Changing a posture profile re-ranks history without recomputing a single score.
- **Gained:** postures are a genuine product differentiator and map directly onto how founders already think about their brand.
- **Required:** posture profiles must be versioned, so a past run's ranking stays reproducible after we tune the weights.
