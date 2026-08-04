# ADR-0003: Deterministic generation; LLM as steering layer only

**Status:** Accepted
**Date:** 2026-08-04

## Context

The obvious way to build an AI naming product in 2026 is to ask a frontier model for names. It works immediately and demos well.

At production scale it fails in four specific ways:

1. **Mode collapse.** Models converge hard on a narrow brandable vocabulary — `-ly`, `-ify`, `Nexus`, `Lumina`, `Zeni-`. Output across users looks the same.
2. **Cross-user duplication.** Two founders in the same industry get overlapping lists, and only one can own the name.
3. **Non-determinism.** A score that can't be reproduced can't be explained or regression-tested.
4. **Unbounded cost.** Thousands of names per run × every run, forever.

## Decision

Bulk candidate generation is **deterministic and combinatorial** — phonotactic syllable grammars, morphemic composition, lexical mutation. Given `(params, ruleset_version, seed)` the output is exactly reproducible.

The LLM is confined to roles where it is genuinely irreplaceable:
- interpreting the brief into structured parameters,
- expanding concepts into seed vocabulary (metaphors, adjacent domains, tone words) that *feeds* the combinatorial engine,
- judging semantic fit on the top slice,
- writing human-readable rationale.

**The LLM never emits final names in bulk.**

## Alternatives considered

- **LLM as bulk generator.** Fastest to build, best first impression. Rejected on all four grounds above.
- **Fine-tuned small model for generation.** Cheaper per token than a frontier model, more controllable. Rejected *for now*: still non-deterministic, still needs a training corpus we don't have, and combinatorial generation already produces more legal candidates than we can score. Revisit at M10 if inventory diversity plateaus.

## Consequences

- **Accepted:** more upfront engineering — syllable grammars, root inventories, and phonotactic rules must be built and tuned by hand. This is the bulk of M1.
- **Gained:** generation is free, infinitely scalable, and reproducible from a seed.
- **Gained:** genuinely novel output, because the space is combinatorial rather than drawn from a model's learned brandable-name distribution.
- **Gained:** LLM cost is bounded by construction — it scales with the *top slice* (tens of names), not the candidate pool (millions).
- **Risk:** hand-built grammars can produce output that is legal but lifeless. Mitigated by M1's proof requirement — an ≥80% human spot-check on "sounds like a real company." If we can't hit that, this ADR is wrong and we revisit.
