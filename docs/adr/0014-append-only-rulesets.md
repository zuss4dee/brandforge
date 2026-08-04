# ADR-0014: Append-only ruleset inventories

**Status:** Accepted — **amended by [ADR-0017](0017-immutable-address-spaces.md)**
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §9](../design/03-generation-engine.md)

> **Amendment note (2026-08-04):** the MAJOR-bump semantics below left a tension this ADR did not resolve — weights are address-relevant, but retuning them is routine work in M1.3, so a literal reading makes every retune orphan the inventory. [ADR-0017](0017-immutable-address-spaces.md) resolves it: address spaces are immutable artifacts, and an address-relevant change *mints a new space* rather than bumping this one. The append-only rule below is unchanged and continues to hold **within** a space.

## Context

[ADR-0012](0012-index-addressable-generation.md) makes a candidate's identity a function of its **index** in a mixed-radix address space. Every stored provenance, every golden fixture, and every reproducibility claim depends on that space being stable.

The radix of each digit is the size of an inventory — the number of onsets, of morphemes, of templates. **Removing or reordering a single inventory entry shifts every subsequent digit and silently re-points every index in the system.** Every stored provenance would replay to a different name than the one recorded.

The failure raises no error. Nothing crashes, nothing logs, no test fails unless one specifically checks for it. The corruption is total and invisible.

## Decision

**Inventory entries are never removed or reordered.** Deprecation is a status flag (`active` → `deprecated` → `retired`) plus a gate exclusion. The entry keeps its position forever.

Ruleset version semantics are defined by their effect on the address space:

| Bump | Address space | Guarantee |
|---|---|---|
| **PATCH** | Unchanged | Same index → same candidate. Gates, thresholds, scoring only. |
| **MINOR** | **Extended by appending** | Old indices decode *identically*; new indices reach new candidates. |
| **MAJOR** | Restructured | Old indices invalid. Requires re-anchoring from expanded provenance. |

**CI diffs inventory files and fails the build on any non-append change absent a MAJOR bump.**

## Alternatives considered

- **Stable IDs with an indirection table** (index → entry ID). Permits reordering. Rejected: it does not actually help — the *mapping* becomes the thing that must stay append-only, so the same discipline applies with an extra layer of indirection to get wrong.
- **Content-hash the ruleset and refuse to replay across any change.** Maximally safe. Rejected: every weight tweak would be a MAJOR bump, orphaning the inventory constantly and making routine tuning prohibitively expensive.
- **Convention and code review.** Rejected for the same reason as [ADR-0006](0006-pure-engine-boundary.md): silent, catastrophic failures cannot be defended by attentiveness.

## Consequences

- **Accepted:** inventories accumulate tombstones and grow monotonically. A cosmetic cost.
- **Accepted:** MAJOR bumps are genuinely expensive and should be rare. This is correct — they *should* be painful enough to think twice about.
- **Required:** expanded provenance is retained for admitted inventory even though the compact form is theoretically sufficient, because a MAJOR bump orphans compact-only rows permanently. Cheap insurance on the ~1% of candidates that reach users.
- **Required:** the CI diff check is not optional. Without it this ADR is a note in a document that a future deadline will overrule.
