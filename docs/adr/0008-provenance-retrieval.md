# ADR-0008: Retrieve on provenance embeddings, not name embeddings

**Status:** Accepted — **amended by [ADR-0015](0015-sound-symbolic-semantics.md)**
**Date:** 2026-08-04

> **Amendment note (2026-08-04):** the final consequence below — that phonotactic candidates have weak provenance and are retrievable only on structural filters — understated a real gap. Phonotactic construction is the engine's *largest* supply source, so leaving it semantically unreachable would sterilise most of the inventory. [ADR-0015](0015-sound-symbolic-semantics.md) closes this by attaching connotative semantics at the phoneme level. The core decision below — retrieve on provenance, not on embeddings of invented strings — is unchanged.

## Context

Given a brief and an inventory of 10⁷ names, we must retrieve the semantically relevant ones. The reflexive 2026 answer is: embed every name into pgvector and run vector similarity against the brief.

**This does not work, and it fails quietly.** Our inventory names are invented strings — `Corvane`, `Lumeris`, `Zeprix`. They are out-of-vocabulary by construction. An embedding model given a novel string produces a vector driven by orthographic accident and subword fragments, not meaning. The nearest neighbours of `Corvane` will be strings that *look* like it, not names that *mean* what the founder needs.

The failure is quiet because the system still returns results, and they still look like names. It just returns irrelevant ones — and this is, in our assessment, the single most common reason systems in this category produce output that feels random.

## Decision

**Embed provenance, not the surface string.**

Every generated candidate records, at generation time, the morphemes, roots, and concept tags it was built from. `Corvane` might carry `{roots: [corv- "raven", -ane], concepts: [vigilance, flight, watchfulness], strategy: morphemic}`.

Retrieval is therefore:

```
brief → LLM concept expansion → concept tags → candidates
      + structured filters (length, syllables, availability, quality floor)
      + brief-conditioned construction for concepts absent from inventory
```

The `concept_embedding` column holds an embedding of the candidate's **concept set**, which is real language and embeds meaningfully.

## Alternatives considered

- **Embed the name string.** Standard, trivial to implement. Rejected for the reason above — it is semantically vacuous on invented words.
- **Pure tag matching, no embeddings.** Precise and cheap. Rejected as insufficient alone: it misses near-synonymous concepts (a brief about "trust" should reach roots tagged *reliability*, *fidelity*, *assurance*). Retained as a fast structured pre-filter *combined* with vector search.
- **LLM reranks a random inventory sample.** Rejected: at inventory scale, a random sample almost never contains the good matches, and the LLM cannot rescue a bad candidate set.

## Consequences

- **Required:** the generation engine must emit rich provenance. This constrains M1's output contract, and provenance cannot be reconstructed after the fact — a candidate generated without it is permanently unretrievable by meaning.
- **Required:** root and morpheme inventories must carry curated semantic tags. This is real hand-work in M1 and the main reason M1 is not trivial.
- **Gained:** retrieval is explainable — we can show *why* a name matched ("built from *corv-*, raven → vigilance").
- **Gained:** structured filters and vector search compose, so we get precision and recall rather than choosing one.
- **Accepted:** candidates from pure phonotactic construction have weak provenance by nature (they're built from sound, not meaning). They are retrieved primarily on phonetic/structural filters and posture fit — which is appropriate, since that is exactly what they offer.
