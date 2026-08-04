# ADR-0013: Corpus-induced weights and the Typicality–Distinctiveness objective

**Status:** Accepted
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §0.2, §0.3](../design/03-generation-engine.md)

## Context

Two related mistakes are available here, and most name generators make at least one.

**The first is writing the grammar from a linguistics textbook.** English phonotactics is far too permissive for our purpose — it legitimately admits *strengths*, *sixths*, *blurbed*. Real brand names occupy a much narrower region of that legal space. A textbook grammar wanders out of it immediately and produces fluent, plausible, non-brand-like output.

**The second is optimising for a single quality maximum.** A good brand name must be *typical in form* (it patterns like a company name) and *distinctive in token* (it is not close to any existing name). These objectives pull against each other. Maximising typicality alone regenerates the corpus — arriving at *Lumina* by combinatorial means rather than by LLM means, but arriving all the same. Maximising distinctiveness alone produces *Xqthorp*.

## Decision

1. **Hand-design the grammar's structure; induce its weights from a corpus** of real brand names. Structure gives coverage of the space; induced weights give plausibility within it. Every weight in the ruleset is marked `<induced>` until measured.
2. **Adopt the Typicality–Distinctiveness (T–D) frontier as the engine's explicit objective.** The target is the high-typicality / high-distinctiveness quadrant.
3. **Make frontier occupancy a measured, falsifiable metric**, plotted against three references: real brands, random legal strings, and competitor-generator output. Our mass must sit in the target quadrant *and* be visibly separated from the real-brand cluster along the distinctiveness axis.
4. **Track morpheme saturation** — how heavily each morpheme is already used in real brands — and penalise saturated morphemes at generation time.

## Alternatives considered

- **Hand-written grammar, hand-tuned weights.** No corpus dependency, no licensing question. Rejected: nobody can hand-tune a phoneme distribution to match an empirical one they have not measured, and the failure is invisible from the inside.
- **Pure corpus induction, sampling directly from the learned distribution.** Maximum typicality. Rejected: this *is* mode collapse. It regenerates the corpus's densest region, which is exactly the clichéd names.
- **Single composite quality score.** Simpler to optimise and explain. Rejected: it cannot express a tension between two competing objectives, so it would silently collapse to whichever term dominates.

## Consequences

- **Required:** a brand corpus becomes a hard dependency of the engine, not a nice-to-have. Templates, weights, typicality, saturation and novelty distance are all induced from it. Source decided in [ADR-0016](0016-uspto-brand-corpus.md).
- **Required:** we must not assert prosodic or phonotactic distributions from intuition. The design specifies the *method*; the numbers are an empirical question answered in M1.3. If the data contradicts our seed hypotheses, the hypotheses change.
- **Gained:** mode collapse becomes a *measured* quantity (morpheme usage Gini, template distribution, distinct-*n*) rather than something noticed after the fact by an annoyed user.
- **Gained:** saturation data compounds — it improves automatically with every corpus refresh, and unlike a prompt instruction it is versioned and testable.
- **Accepted:** held-out discipline is now mandatory. Real brand names used as an evaluation ceiling must be excluded from weight induction, or the evaluation is contaminated and proves nothing.
