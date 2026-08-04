# ADR-0015: Sound-symbolic semantics for morpheme-free candidates

**Status:** Accepted — **amends [ADR-0008](0008-provenance-retrieval.md)**
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §0.6, §6.3](../design/03-generation-engine.md)

## Context

[ADR-0008](0008-provenance-retrieval.md) established that retrieval works on **provenance** — the morphemes and concept tags a candidate was built from — rather than on embeddings of the invented surface string. That reasoning stands.

But its final consequence conceded a gap:

> *"Candidates from pure phonotactic construction have weak provenance by nature (they're built from sound, not meaning). They are retrieved primarily on phonetic/structural filters and posture fit."*

This is a bigger problem than it appeared. **Phonotactic construction is the engine's largest supply source.** Leaving it semantically unreachable means the bulk of the inventory can never be matched to a brief by meaning — it would surface only when a founder's constraints happened to be structural.

## Decision

Attach connotative semantics at the **phoneme** level, independent of morphemes.

Sound-symbolic priors — front vowels patterning with smallness/speed/precision, back vowels with size/stability, voiceless stops with sharpness, voiced stops with weight, sibilants with velocity, sonorants with warmth — contribute to the same fixed connotation vector space used for morphemes (VAD + Aaker brand-personality dimensions, per [§6.2](../design/03-generation-engine.md#62-connotative--a-fixed-vector-space)).

**Every candidate therefore carries a connotation vector**, whether or not it contains a morpheme. Posture fit becomes a cosine similarity in that space for all candidates uniformly.

These are **weak priors with learned weights, validated empirically**, never hard rules.

## Alternatives considered

- **Leave the gap.** Rejected: it sterilises the largest supply source.
- **Post-hoc LLM tagging of phonotactic candidates.** Assign meaning by asking a model what each invented name evokes. Rejected: costs scale with inventory size (millions of candidates), is non-deterministic, and contradicts [ADR-0003](0003-deterministic-generation.md)'s confinement of the LLM to the top slice.
- **Treat sound symbolism as a hard rule set.** Rejected — see the honesty note below.

## Consequences

- **Gained:** uniform semantic retrieval across every supply source; the inventory is fully reachable by meaning.
- **Gained:** it is *free* at generation time. The phonological form is already computed; the vector is a lookup and a sum.
- **Honesty about the evidence:** phonosemantic effects are real and replicated, but **effect sizes are modest and partly language-specific.** Treating them as strong rules would be overclaiming. They are seeded as weak priors, their weights are learned, and their contribution is falsifiable in the M1.7 study.
- **Accepted:** if the study shows they carry no signal for our raters, the weights go to zero. We lose nothing structural — the vector space and the retrieval path remain, populated by morphemes alone. This is a cheap bet with a bounded downside.
- **Required:** sound-symbolic priors are per-language-pack, not universal. Cross-linguistic phonosemantics does not transfer reliably, and assuming it does would export an English intuition to markets where it is simply wrong.
