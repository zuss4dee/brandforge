# ADR-0005: Tiered availability cascade with zone-file L0

**Status:** Accepted
**Date:** 2026-08-04

## Context

Domain availability is the most expensive operation in the product and the one users care most about. Checking thousands of names × several TLDs per run through a registrar API is rate-limited and financially unviable — per-run cost would exceed plausible per-run revenue.

The sources available differ enormously in cost, authority, and latency, and no single one is both cheap and authoritative.

## Decision

A **four-tier cascade**, where each tier is roughly 10–100× cheaper than the next and only survivors are promoted:

| Tier | Source | Cost | Provides |
|---|---|---|---|
| L0 | Bloom filter built from zone files | ~free, no network | "Definitely registered" — eliminates 90%+ locally |
| L1 | RDAP (DNS as weak hint only) | free, rate-limited, cached | Registered/available, dates, registrar |
| L2 | Registrar API | $ | Authoritative + price + premium status |
| L3 | Aftermarket (Afternic/Sedo/Dan) | $ | Resale price for taken-but-purchasable |

Candidates reach L2 only if they survive L0 *and* score well. All providers sit behind an `AvailabilityProvider` port returning a normalized `AvailabilityFact {status, source, confidence, checked_at, price}`, with per-provider circuit breakers, rate limiters, and budget governors.

## Alternatives considered

- **Registrar API only.** Far less setup, no legal agreements. Rejected: ~100× higher cost per name and hard rate-limit ceilings that cap run size — it constrains the product, not just the budget.
- **DNS-only checking.** Free and fast. Rejected as a *verdict*: many registered domains have no nameservers, so NXDOMAIN does not mean available. Using it that way would systematically lie to users about the single fact they most rely on. DNS is retained only as a hint that promotes to L1.

## Consequences

- **Accepted:** zone-file access requires **Verisign TLD Zone File Access and ICANN CZDS agreements with weeks of contractual lead time.** These must be filed in M0 or they land on the critical path at M3. See `docs/ops/zone-file-access.md`.
- **Accepted:** zone data is a periodic snapshot, so L0 has a freshness lag. Acceptable because L0 only ever produces the *negative* ("registered"), and a stale negative is conservative — we might hide a name that just became free, never claim a taken one is free.
- **Gained:** roughly 100× cost reduction, making large runs economically viable.
- **Gained (trust):** because we resolve via zone data and RDAP, shortlisted candidates are never leaked into third-party *search* endpoints that could be logged and front-run. This is a real founder fear, it costs us nothing, and it is worth stating in the product.
- **Required:** `confidence` must be explicit on every fact, and reads must prefer the highest-confidence non-expired fact. Sources genuinely differ in authority and flattening that away would reintroduce the DNS trap.
