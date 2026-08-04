# BrandForge

Helping founders discover startup-quality company and product names — generated, validated, scored, availability-checked, and **actually ownable.**

> **Thesis:** BrandForge is a search-and-verification engine over an owned inventory of brandable, verified-available names, with an LLM as the semantic steering layer — not an AI name vending machine.

**Status:** M0 complete — tooling and CI guards in place. No business logic yet. Next: M1.0 (Corpus Assembly).

```bash
make install   # uv sync + git hooks
make check     # lint · types · boundaries · inventory · tests
```

---

## Start here

| Document | What it covers |
|---|---|
| [System Design](docs/design/00-system-design.md) | Architecture, thesis, components, technology, risk register |
| [Data Model](docs/design/01-data-model.md) | Entities, the global/tenant split, lifecycle |
| [Milestones](docs/design/02-milestones.md) | M0–M10 with definitions of done and proofs |
| [M1 — Generation Engine](docs/design/03-generation-engine.md) | The core engine: grammar, morphemes, semantics, provenance, determinism |
| [M1 — Evaluation Strategy](docs/design/04-generation-evaluation.md) | How we prove the engine works |
| [Brand DNA](docs/design/05-brand-dna.md) | The record every candidate carries from generation to decision |
| [M1.0 — Corpus Assembly](docs/design/06-m1-0-corpus-assembly.md) | Verified USPTO source, ingestion, normalisation, held-out strategy |
| [Corpus Providers](docs/design/07-corpus-provider-architecture.md) | Multi-source abstraction, blending, and licence gating |
| [ADRs](docs/adr/) | Every load-bearing decision, with alternatives rejected |
| [CONTRIBUTING](CONTRIBUTING.md) | Repository standards and the two non-negotiable CI guards |
| [CLAUDE.md](CLAUDE.md) | Claude Code operating manual — role, workflow, approval boundaries |
| [Verified facts](docs/ai/verified-facts.md) · [Blocked](docs/ai/blocked.md) · [Backlog](docs/ai/backlog.md) | External facts with dates; what needs a human; accepted debt |
| [Zone File Access](docs/ops/zone-file-access.md) | ⚠️ Action required — weeks of lead time, blocks M3 |

---

## Repository layout

```
brandforge/
├── docs/
│   ├── adr/          # architecture decision records
│   ├── design/       # system design, data model, milestones
│   └── ops/          # runbooks
├── engine/           # Python — PURE. no I/O, no network, no database.
│   ├── morphology/   # syllable grammar, roots, affixes
│   ├── phonetics/    # g2p, syllabification, n-gram models
│   ├── scoring/      # the nine dimensions + posture weights
│   └── corpora/      # lexicons, brand corpus, root tables
├── services/         # adapters — everything that performs I/O
│   ├── availability/ # zone, rdap, registrar, aftermarket
│   ├── trademark/
│   └── llm/          # Claude gateway, prompt registry
├── apps/
│   ├── api/          # FastAPI
│   ├── worker/       # Arq workers
│   └── web/          # Next.js
├── evals/            # golden sets, scorer benchmarks, LLM evals
└── infra/
```

**The most important line in that tree is the `engine/` ↔ `services/` split.** `engine/` may not import `services/`, and CI enforces it. That single rule is what keeps the core deterministic, fast to test, and extractable at year three. See [ADR-0006](docs/adr/0006-pure-engine-boundary.md).

---

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Postgres 16 + pgvector · Redis + Arq · Next.js + TypeScript · Claude
