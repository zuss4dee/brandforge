# ADR-0017: Address spaces are immutable, content-addressed artifacts

**Status:** Accepted — **amends [ADR-0014](0014-append-only-rulesets.md)**
**Date:** 2026-08-04
**Implements:** [Brand DNA §7](../design/05-brand-dna.md)

## Context

This gap was found while implementing ADR-0014's CI guard, not while writing the ADR — which is the ordinary way such gaps surface.

[ADR-0014](0014-append-only-rulesets.md) defines ruleset version semantics by their effect on the address space, and treats any **address-relevant** change as requiring a MAJOR bump that invalidates every existing index.

**Weights are address-relevant.** They feed the quantised slot expansion of [ADR-0012](0012-index-addressable-generation.md), so changing a weight changes which candidate lives at which index.

But inducing weights from the brand corpus is [M1.3's entire purpose](../design/03-generation-engine.md#12-sub-milestones), and weights will be retuned as the corpus is refreshed and the T–D frontier is tuned. Under a literal reading of ADR-0014, **every routine retune orphans the accumulated inventory.** That makes the engine's core tuning loop destructive, and effectively forbids post-launch tuning altogether.

The tension is real and ADR-0014 does not resolve it.

## Decision

**An address space is a named, immutable, content-addressed artifact.** `space_id` is part of the genotype ([Brand DNA §2](../design/05-brand-dna.md)).

- Changing *any* address-relevant parameter — a weight, an inventory's cardinality, a template set — **mints a new `space_id`**. It is never an in-place edit.
- **Old spaces are retained, never migrated.** A row carrying `space_id: en-US.s3` remains replayable under the retained `s3` definition indefinitely.
- New generation proceeds in `en-US.s4`. Nothing is orphaned; no MAJOR bump is required.

ADR-0014's append-only rule continues to hold **within** a space, unchanged.

## Alternatives considered

- **Keep ADR-0014 literal — MAJOR bump per retune.** One versioning concept instead of two. Rejected: it makes weight induction destructive, which is unacceptable given that inducing weights is the point of M1.3.
- **Make weights non-address-relevant** by using uniform slots and applying weights only as a downstream scoring signal. Rejected: generation would then sample uniformly over a space where most points are implausible, collapsing yield. Weighting *at* generation is what makes the enumeration efficient.
- **Migrate old rows into each new space.** Keeps a single live space. Rejected: there is no correct mapping. A candidate's index under new weights is not a function of its index under old ones, so "migration" would mean re-deriving every row — which is regeneration, not migration.
- **Defer to M1.3.** Rejected: `space_id` is part of the genotype, so deferring blocks the Brand DNA schema from freezing and leaves M1.2's address space built on an open question.

## Consequences

- **Gained:** weight retuning becomes routine and non-destructive. The engine's central tuning loop stops being a data-migration event.
- **Gained:** perfect historical reproducibility. Any name a user was ever shown replays exactly, under the space that produced it, regardless of subsequent tuning.
- **Accepted:** space definitions accumulate. Each is small (inventories plus weights), but they accumulate monotonically.
- **Accepted, and the important one: retained space definitions are as durable as the inventory itself.** Deleting the space that produced a row permanently destroys that row's replayability, with no error at deletion time and no way to reconstruct it afterwards. Address-space artifacts are a **backup and retention obligation**, not a config file — and must be treated as such in whatever storage they live in.
- **Required:** the CI guard from ADR-0014 already enforces this correctly — it fails on in-place mutation, which is precisely the operation that should mint a new space instead. No tooling change is needed, only the policy this ADR records.
