# ADR-0004: Python engine + TypeScript web

**Status:** Accepted
**Date:** 2026-08-04

## Context

The core of BrandForge is a linguistics/ML workload: grapheme-to-phoneme conversion, syllabification, character n-gram language models, phonetic-similarity algorithms, and embeddings. The frontend is a conventional interactive web app.

A single-language (all-TypeScript) stack would be simpler to operate and hire for. The counterweight is that the linguistic tooling ecosystem is overwhelmingly Python.

## Decision

- **Engine + API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic
- **Web:** Next.js (App Router), TypeScript
- **Boundary:** OpenAPI schema generated from FastAPI, TypeScript client generated from it in CI

## Alternatives considered

- **All-TypeScript** (Next.js + Hono/tRPC). One toolchain, native end-to-end type safety, one hiring profile, simplest local dev. Rejected: we would hand-roll or port g2p, syllabification, phonotactic validation, and n-gram modelling — code that already exists, is battle-tested, and is *the actual product*. Reimplementing the differentiator to save on toolchain complexity is the wrong trade.
- **All-Python** (server-rendered, HTMX or similar). One language, no client generation. Rejected: the explore/compare/shortlist experience is genuinely interactive, and we would be fighting the frontend ecosystem for the surface users actually touch.
- **Start TS, extract a Python engine later.** Rejected: the extraction would land exactly when we're busiest, and the engine is needed in M1 — first.

## Consequences

- **Accepted:** two languages, two package managers, two lint/test toolchains, two CI paths.
- **Accepted:** the type boundary is generated rather than native, so a stale generated client is a possible failure mode. Mitigated by regenerating in CI and failing the build on drift.
- **Gained:** direct access to the mature Python phonetics/ML ecosystem for the component that determines whether the product is good.
- **Gained:** the engine is importable from notebooks and scripts, which matters enormously for M2's eval work.
