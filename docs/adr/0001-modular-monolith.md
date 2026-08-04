# ADR-0001: Modular monolith over microservices

**Status:** Accepted
**Date:** 2026-08-04

## Context

BrandForge has several components with genuinely different resource profiles: a CPU-bound generation engine, an I/O-bound availability service, an LLM gateway with its own rate limits, and a conventional CRUD API. That difference is the standard argument for splitting them into services.

We are also a very small team building a product that has not yet found market fit.

## Decision

Build a **modular monolith with async workers**. One deployable API, one worker pool, strict module boundaries enforced in code.

## Alternatives considered

- **Microservices from day one.** Correct resource isolation, independent scaling. Rejected: at our size the dominant cost is not compute, it is the engineering time lost to distributed tracing, schema versioning across services, and local dev environments. We would be paying an operational tax on a product whose shape is still uncertain.
- **Serverless functions.** Attractive for the bursty availability workload. Rejected for the core: the generation engine needs warm in-memory corpora and n-gram models; cold starts would dominate. Remains a candidate for isolated sweeper jobs later.

## Consequences

- **Accepted:** a single scaling unit; a heavy generation job can contend with API traffic until we split the worker pool (which we can do without changing code, since workers are already a separate process).
- **Accepted:** one deploy pipeline, one place to look when something breaks.
- **Required:** module boundaries must be real, not aspirational. Enforced by [ADR-0006](0006-pure-engine-boundary.md). Without that enforcement this decision degrades into a big ball of mud and the extraction path closes.
- **Reversible:** any module behind a port can be extracted into a service when a measured scaling reason appears — and "measured" is the operative word.
