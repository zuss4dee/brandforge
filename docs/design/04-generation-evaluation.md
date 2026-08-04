# M1 — Generation Engine Evaluation Strategy

**Status:** Approved v1.0 · **Date:** 2026-08-04
**Companion:** [Generation Engine Design](03-generation-engine.md)
**Amends:** M1's proof in [Milestones](02-milestones.md) — see §0 and §8

---

## 0. The problem with the original M1 proof

[Milestones](02-milestones.md) currently defines M1's proof as:

> *human spot-check ≥80% "sounds like a real company"*

**This is a weak proof and I want to replace it.** Three defects:

1. **Absolute ratings drift.** "Sounds like a real company" is not calibrated. Rater mood, batch composition, and time of day move it by more than the effect we are trying to measure. An 80% today and an 80% next month may not mean the same thing.
2. **No baseline.** 80% against what? Random strings would score near zero, so 80% might be trivial. Real brand names might score 75%, in which case 80% would be *superhuman* and almost certainly measurement error.
3. **It measures the wrong axis.** It measures typicality only. A generator that memorised the corpus and emitted *Lumina* would score ~100% and be worthless — it fails the distinctiveness half of the T–D frontier entirely.

### The replacement

> **M1 passes when raters cannot reliably distinguish our names from real, successful company names — while the same batch demonstrably occupies a distinct region of name-space from the corpus.**

Both halves are required. Typicality without distinctiveness is plagiarism; distinctiveness without typicality is noise. This is a direct, falsifiable test of the T–D frontier claim, and it is self-calibrating — the baseline is embedded in the instrument.

---

## 1. Five evaluation levels

Ordered by cost. The cheap ones run on every commit; the expensive one runs per milestone.

| Level | What | Cost | Cadence |
|---|---|---|---|
| **L1** | Correctness & determinism | free | every commit |
| **L2** | Intrinsic distribution metrics | cheap | every commit |
| **L3** | Golden fixtures | free | every commit |
| **L4** | Human indistinguishability study | expensive | per milestone |
| **L5** | Adversarial / red-team | moderate | per milestone + on demand |

---

## 2. L1 — Correctness & determinism

Property-based tests (Hypothesis), run in CI. These are the non-negotiable structural guarantees from [§2](03-generation-engine.md#2-the-address-space--deterministic-generation).

| Property | Assertion |
|---|---|
| **Determinism** | `candidate(seed, i)` identical across processes, machines, and Python versions |
| **Bijectivity** | Over 10⁷ indices: **zero duplicate derivations.** Not "few" — zero |
| **Totality** | Every index in `[0,\|S\|)` decodes to a valid candidate; no exceptions, no empties |
| **Replay** | `replay(provenance, ruleset) == surface` for every admitted candidate |
| **Constraint soundness** | 10⁶ generated forms, zero phonotactic violations |
| **Shard independence** | Range `[a,b)` generated on one worker ≡ generated across N workers |
| **MINOR compatibility** | After a MINOR ruleset bump, every pre-bump index decodes **identically** |
| **Append-only** | CI diff fails on any non-append inventory edit without a MAJOR bump |

The last two encode [§9](03-generation-engine.md#9-ruleset-versioning). They are the tests that prevent the silent index re-pointing failure, which produces no error and corrupts everything.

---

## 3. L2 — Intrinsic distribution metrics

No humans required, so these run continuously and catch regressions between human studies. Each metric maps to a specific failure mode.

### 3.1 Typicality — *does it sound like a brand?*

Mean log-probability of generated names under a character/phoneme n-gram model trained on the brand corpus.

**Test:** the generated distribution should overlap held-out real brand names. Reported as distributional overlap, not a threshold — we want our names to *sit inside* the real distribution, not to score higher than real names, which would indicate we are producing the corpus's most clichéd region.

### 3.2 Novelty — *is it actually new?*

Minimum edit distance and minimum phonetic distance (Double Metaphone + alignment) from every corpus entry.

**Test:** p95 of minimum distance above threshold; **zero** candidates below the collision floor.

### 3.3 Diversity — *are we collapsing?*

The mode-collapse detector, and the metric I would watch most closely:

| Metric | Detects |
|---|---|
| Distinct-*n* over phoneme n-grams | Phonological repetition |
| Entropy of onset / nucleus / coda usage | Under-use of the legal space |
| **Gini coefficient of morpheme usage** | Saturation drift — a few morphemes dominating output |
| Template usage distribution | Over-reliance on one prosodic shape |

A rising morpheme Gini is the early warning that we are becoming the thing [ADR-0003](../adr/0003-deterministic-generation.md) was written to avoid — arriving by our own mechanism rather than an LLM's.

### 3.4 T–D frontier occupancy

The headline chart. Plot the batch in (typicality × distinctiveness) space against three references: real brands, random legal strings, and competitor-generator output.

**Test:** our mass sits in the high-typicality / high-distinctiveness quadrant, and is **visibly separated** from the real-brand cluster along the distinctiveness axis. This is the falsifiable form of [§0.3](03-generation-engine.md#03-the-central-objective-is-a-tension-not-a-maximum).

### 3.5 Yield

Funnel survival at each gate, and the end-to-end admitted rate. Primarily a cost metric — it determines how much compute an inventory of a given size requires — but a sudden change is also a sensitive regression signal.

---

## 4. L3 — Golden fixtures

A frozen set of `(ruleset_version, seed, index_range)` tuples with expected output hashes, committed to the repo.

**Any ruleset change that alters output fails CI until a human explicitly blesses a new golden file.**

This is the mechanism that makes ruleset changes *visible in code review*. Without it, a one-line weight tweak silently changes millions of names and nobody notices until the T–D chart moves three weeks later. The diff in the golden file is the reviewable artifact.

---

## 5. L4 — Human indistinguishability study

The M1 proof. Everything else is instrumentation for this.

### 5.1 Protocol

**Blind mixed panel.** Raters see names in a shuffled stream with no source labels:

| Arm | Source | Role |
|---|---|---|
| **A** | Our generated candidates (post-gate) | Treatment |
| **B** | Real names of funded startups, held out from the training corpus | **Ceiling** |
| **C** | Random phonotactically-legal strings | **Floor** |
| **D** | Output from 2–3 competitor generators | Competitive baseline |
| **E** | Calibration items with known-correct answers | Rater quality control |

Arm B being **held out from the training corpus** is essential. If real names used as the ceiling were also used to induce our weights, the comparison is contaminated and the study proves nothing.

### 5.2 Task design

Two tasks per rater, because they measure different things:

1. **Forced-choice discrimination.** Given a pair (one real, one generated), pick the real one. **Chance is 50%.** The closer raters get to chance, the better we are.
2. **Rated judgement.** Independent 1–7 Likert scales for: *would fund a company with this name*, *pronounceable on first sight*, *memorable*, *sounds like a real company*. Multiple scales because a single "quality" rating conflates dimensions we need to tune independently.

### 5.3 Success criteria

| Metric | Threshold |
|---|---|
| **Discrimination accuracy vs. Arm B** | ≤ 60% (chance = 50%) |
| **Mean rating vs. Arm D (competitors)** | Ours significantly higher, *p* < 0.05 |
| **Mean rating vs. Arm C (random)** | Ours dramatically higher — sanity check |
| **Mean rating vs. Arm B (real)** | Within 1.0 Likert point |
| **Inter-rater reliability** | Krippendorff's α ≥ 0.6, else the study is uninterpretable |

If discrimination accuracy is near 50%, raters genuinely cannot tell our invented names from real funded companies. That is a far stronger and far more honest claim than "80% sounded good."

### 5.4 Rater panel

**Founders and operators, not general crowdworkers.** Brand judgement is domain-specific; a rater who has never named a company is not evaluating the thing we care about. Crowdworkers are cheaper and will produce a noisier, less relevant signal.

Recommended: 20–30 raters, ≥40 judgements each, calibration items interleaved, and pre-registered thresholds. **The success criteria are fixed before the data is collected** — otherwise we will find a threshold the results happen to clear, which is not a test.

### 5.5 Cost and honesty

This study costs real money and roughly two weeks. That is a legitimate reason to run it *once* at M1.7 rather than continuously — which is exactly why L2 exists as the continuous proxy. If we cannot afford the panel, we should say so and adjust the milestone honestly, rather than quietly substituting a self-assessment.

---

## 6. L5 — Adversarial / red-team

Deliberate attempts to make the engine produce something embarrassing. Everything found becomes a permanent regression test.

| Probe | Looking for |
|---|---|
| **Cross-linguistic offence** | Names obscene or unfortunate in any pack language, incl. phonetic near-misses |
| **Unintended real words** | Slang, medical terms, and — critically — non-English words the en-US lexicon check misses |
| **Famous-mark collision** | Near-misses on well-known brands via phonetic and visual similarity |
| **Homograph / lookalike** | Confusable character sequences (`rn` ≈ `m`, `l` ≈ `I`) — a phishing-adjacent risk once these become domains |
| **Prosodic pathology** | Unpronounceable-in-practice forms the constraint set permits on paper |
| **Seed sensitivity** | Whether output quality varies materially by seed — it should not |

The homograph probe matters more than it looks. These names become domains, and a name that renders confusably in a browser address bar is a liability we would be handing to our own customers.

---

## 7. What we deliberately do **not** measure in M1

Naming these prevents scope drift and premature optimisation:

| Not measured | Why | Where it lands |
|---|---|---|
| Semantic fit to a brief | No LLM concept expansion in M1 | M5 |
| Availability yield | No availability subsystem yet | M3 |
| Trademark collision rate | Only a crude famous-marks check in M1 | M7 |
| Commercial conversion | No product yet | M6+ |

M1 answers exactly one question: **can we generate names that are simultaneously brand-plausible and genuinely novel, reproducibly and at scale?** Every other question is deferred, on purpose.

---

## 8. Proposed amendment to the milestone

Replace M1's proof in [Milestones](02-milestones.md):

> ~~Emits 1M+ unique pronounceable candidates, reproducible from a seed; human spot-check ≥80% "sounds like a real company"~~

> **Emits 10⁷ enumerated / 10⁵+ admitted candidates with zero duplicate derivations, bit-reproducible from `(seed, ruleset_version, index)`; blind forced-choice discrimination against held-out real startup names ≤60% (chance 50%); mean rating significantly above competitor generators; T–D frontier occupancy demonstrably separated from the training corpus.**

Longer, and every clause is measurable.
