# ADR-0010: Postgres as the single datastore

**Status:** Accepted
**Date:** 2026-08-04

## Context

BrandForge has workloads that each have a "correct" specialised store: relational data (orgs, projects, runs), a 10⁷-row inventory with heavy filtering (a search engine's job), vector similarity (a vector database's job), full-text trademark search (Elasticsearch's job), and caching/queueing (Redis's job).

Adopting the right tool for each would mean five datastores before we have a user.

## Decision

**Postgres 16 for everything durable**, with `pgvector` for embeddings, JSONB for evolving score and provenance payloads, GIN indexes for tag filtering, and native full-text search for trademark matching. **Redis** for cache, rate limiting, and the job queue only — nothing durable. **S3/R2** for blobs (corpus snapshots, zone dumps, exports).

Specialised stores are adopted only when a **measured** limit is hit, not when one is anticipated.

## Alternatives considered

- **Postgres + a dedicated vector DB.** Better ANN performance at very large scale. Rejected for now: pgvector with HNSW is comfortably sufficient at 10⁷ rows, and a second store means a second consistency problem — embeddings drifting out of sync with the rows they describe.
- **Postgres + Elasticsearch for trademark search.** Better full-text relevance. Rejected for now: our matching is primarily *phonetic* (Double Metaphone keys) and *edit-distance*, both of which are index lookups Postgres handles well. Revisit if M7's latency proof fails.
- **A search engine as the inventory store.** Rejected: the inventory needs transactional integrity with scores and availability facts, and joins we would otherwise denormalise by hand.

## Consequences

- **Accepted:** we will eventually outgrow single-node Postgres on at least one axis, most likely inventory scan performance. Mitigated by aggressive indexing, denormalised filter columns, and partitioning when measured — and read replicas before anything more exotic.
- **Gained:** one backup story, one migration story, one consistency model, one thing to operate. At our size this is worth more than any individual store's performance advantage.
- **Gained:** transactional joins across candidates, scores, and availability facts — which would otherwise become hand-maintained denormalisation and the bugs that come with it.
- **Required:** every "we should add datastore X" proposal must come with a measurement showing Postgres failing, not a benchmark from someone else's workload.
