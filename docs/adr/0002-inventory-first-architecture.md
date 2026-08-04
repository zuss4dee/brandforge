# ADR-0002: Inventory-first, not generate-on-demand

**Status:** Accepted
**Date:** 2026-08-04

## Context

The intuitive pipeline is: user submits a brief → generate thousands of names → filter by availability → rank → show. This matches the user's mental model and is how most name generators work.

It has two fatal properties at scale. First, availability is the scarce constraint: if 95%+ of generated names are already registered, then 95% of the pipeline's work is wasted, and the user sees a slot machine. Second, cost and latency scale linearly with usage forever — every run re-does work that a previous run already did.

## Decision

Invert it. Maintain a **pre-built, pre-scored, pre-verified inventory** of brandable available names as a durable asset. Per-request work is **retrieval + rerank + narrow live verification** on the top candidates only.

Generation and availability sweeping run as background jobs, not user-triggered ones.

## Alternatives considered

- **Generate fresh per request.** Simpler; faster to a first demo; no inventory infrastructure. Rejected: runs are slow, most output is unavailable noise, and unit costs never improve with scale — the economics get worse as the product succeeds.
- **Hybrid, decide later.** Keep both paths open until M3 gives us real cost data. Rejected as the *default*, because the inventory shapes the data model and the generation engine's output contract; deferring means building both and rewriting one.

## Consequences

- **Accepted:** materially more infrastructure before the first end-to-end demo. M1–M3 produce no UI.
- **Gained:** the inventory compounds. Every generation and availability sweep makes the product permanently better for every future user — a real moat, unlike prompt engineering.
- **Gained:** sub-10s results become achievable, because the expensive work already happened.
- **Required:** a freshness strategy. Inventory availability data goes stale; a background sweeper must prioritise refresh by score and staleness, and the UI must re-verify at shortlist time before a founder acts on it.
- **Required:** brief-conditioned construction alongside retrieval, so concepts the inventory has never seen are still covered.
