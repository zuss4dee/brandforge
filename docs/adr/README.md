# Architecture Decision Records

An ADR captures **one** architectural decision: the context, the choice, the alternatives rejected, and the consequences we accept. ADRs are immutable once accepted — a decision that changes gets a *new* ADR that supersedes the old one. The old one stays, so the reasoning trail survives.

## Format

```markdown
# ADR-NNNN: Title

**Status:** Proposed | Accepted | Superseded by ADR-XXXX
**Date:** YYYY-MM-DD

## Context
## Decision
## Alternatives considered
## Consequences
```

## When to write one

Write an ADR when a decision is **expensive to reverse** or when a future engineer would reasonably ask *"why on earth is it done this way?"* Framework choices, data-model shapes, boundaries, external dependencies, and legal posture all qualify. Library picks and file layout usually don't.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith.md) | Modular monolith over microservices | Accepted |
| [0002](0002-inventory-first-architecture.md) | Inventory-first, not generate-on-demand | Accepted |
| [0003](0003-deterministic-generation.md) | Deterministic generation; LLM as steering layer only | Accepted |
| [0004](0004-python-engine-typescript-web.md) | Python engine + TypeScript web | Accepted |
| [0005](0005-tiered-availability.md) | Tiered availability cascade with zone-file L0 | Accepted |
| [0006](0006-pure-engine-boundary.md) | Pure engine / adapter services boundary, CI-enforced | Accepted |
| [0007](0007-posture-relative-scoring.md) | Posture-relative scoring with stored subscores | Accepted |
| [0008](0008-provenance-retrieval.md) | Retrieve on provenance embeddings, not name embeddings | Accepted (amended by 0015) |
| [0009](0009-trademark-signals-not-verdicts.md) | Trademark signals, never verdicts | Accepted |
| [0010](0010-postgres-single-datastore.md) | Postgres as the single datastore | Accepted |

### M1 — Generation Engine

| ADR | Title | Status |
|---|---|---|
| [0011](0011-two-tier-phoneme-orthography.md) | Two-tier generation — phonology then orthography | Accepted |
| [0012](0012-index-addressable-generation.md) | Index-addressable deterministic enumeration | Accepted |
| [0013](0013-typicality-distinctiveness-objective.md) | Corpus-induced weights and the T–D objective | Accepted |
| [0014](0014-append-only-rulesets.md) | Append-only ruleset inventories | Accepted (amended by 0017) |
| [0015](0015-sound-symbolic-semantics.md) | Sound-symbolic semantics for morpheme-free candidates | Accepted — amends 0008 |
| [0016](0016-uspto-brand-corpus.md) | USPTO bulk trademark data as the brand corpus | Accepted (amended by 0018) |
| [0017](0017-immutable-address-spaces.md) | Address spaces are immutable, content-addressed artifacts | Accepted — amends 0014 |
| [0018](0018-case-files-over-raw-xml.md) | Case Files Dataset for M1; raw XML deferred to M7 | Accepted — amends 0016 |
| [0019](0019-corpus-provider-abstraction.md) | Corpus provider abstraction with mechanical licence gating | Accepted |
