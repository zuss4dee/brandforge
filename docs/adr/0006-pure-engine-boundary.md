# ADR-0006: Pure engine / adapter services boundary, CI-enforced

**Status:** Accepted
**Date:** 2026-08-04

## Context

[ADR-0001](0001-modular-monolith.md) chose a modular monolith. That choice is only safe if the module boundaries are real. Monoliths don't decay because someone decided to couple everything — they decay because a deadline made one import convenient, and nothing stopped it.

The generation and scoring engines are also the components most in need of fast, deterministic tests. Any hidden network or database call inside them destroys that property.

## Decision

Two zones, one rule:

- **`engine/`** — pure functions. No network, no database, no filesystem beyond bundled read-only corpora, no clock, no randomness except an explicitly passed seed.
- **`services/`** — every adapter that performs I/O: availability providers, trademark sources, the LLM gateway, storage.

**`engine/` may not import `services/`, `apps/`, or any I/O library.** This is enforced by an import-linter check in CI, not by convention or code review.

## Alternatives considered

- **Convention plus code review.** Zero tooling cost. Rejected: this is exactly the rule that erodes under deadline pressure, and the erosion is invisible until the tests are already slow and flaky.
- **Separate repositories.** Physically impossible to violate. Rejected: cross-repo change coordination is a heavy price for a small team, and it fights the monorepo's main benefit.

## Consequences

- **Accepted:** some ceremony. Corpora must be loaded by the caller and passed in, rather than read ad hoc from disk inside scoring functions.
- **Gained:** engine tests are fast, deterministic, and offline — which is what makes M2's eval harness practical to run on every commit rather than occasionally.
- **Gained:** the engine is trivially usable from notebooks, benchmarks, and CLI tools without standing up infrastructure.
- **Gained:** the extraction path stays open. Any module behind a port can become a service later without untangling hidden coupling first.
- **Required:** a CI job that fails the build on a boundary violation. Without it this ADR is decoration.
