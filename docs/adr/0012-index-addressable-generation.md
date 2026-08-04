# ADR-0012: Index-addressable deterministic enumeration

**Status:** Accepted
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §2](../design/03-generation-engine.md)

## Context

[ADR-0003](0003-deterministic-generation.md) requires deterministic generation. The obvious mechanism — seed a PRNG and draw in a loop — satisfies the letter of that requirement and fails its purpose:

- **Order-fragile.** Adding one `random()` call anywhere shifts every subsequent draw. A harmless refactor silently changes all output.
- **Not parallelisable** without careful stream-splitting.
- **Not resumable.** A crash at candidate 4,000,000 replays from zero.
- **Produces duplicates.** Sampling with replacement collides constantly at scale.

## Decision

Model the candidate space as a **mixed-radix number**: every choice point (template, onset, nucleus, coda, morpheme, orthographic variant) is a digit with finite radix. Interpose a **seed-keyed format-preserving permutation** — a small Feistel network with cycle-walking for non-power-of-two domains — over the index space.

```
candidate(seed, i) = build(decode(π_seed(i)), ruleset)
```

Non-uniform choice weights are achieved by **quantised weight expansion**: each digit domain is expanded to *W* slots (proposed W = 1024) with choice *c* occupying `round(w_c · W)` contiguous slots. This preserves the bijection.

## Alternatives considered

- **Seeded PRNG stream.** Familiar, trivial. Rejected on all four grounds above.
- **Counter-based PRNG (Philox/Threefry) with rejection sampling for weights.** Stateless and parallel, which solves most of it. Rejected: rejection sampling reintroduces duplicates and makes yield per index non-constant, which breaks clean sharding.
- **Alias tables for weighted sampling.** Efficient. Rejected: not a bijection, so duplicates return.

## Consequences

- **Gained: zero duplicate derivations, by construction.** A permutation is a bijection — it visits each point exactly once. Not "few duplicates," *none*. Sampling-based generators spend ever-increasing effort on deduplication as they scale; this one cannot produce a duplicate derivation at all.
- **Gained:** embarrassingly parallel. Shard by index range with zero worker coordination.
- **Gained:** resumable after a crash; auditable back to the exact address for any name a user ever sees.
- **Gained (significant, and unforeseen):** **the index *is* the provenance.** If `(seed, ruleset_version, space_id, index)` replays the whole derivation, that tuple is complete provenance — ~16 bytes rather than ~1 KB of serialised derivation tree. At 10⁷ candidates, ~160 MB instead of ~10 GB.
- **Accepted:** weight resolution is quantised to `1/W`. Well within the precision of induced weights; not a practical constraint.
- **Accepted:** the whole scheme depends on address-space stability across ruleset versions. That dependency is load-bearing and is governed by [ADR-0014](0014-append-only-rulesets.md).
