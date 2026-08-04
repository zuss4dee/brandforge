# Backlog

Known issues, deferred deliberately. Each was found in review and consciously not fixed — this file is the difference between *accepted* debt and *forgotten* debt.

**Not a wish list.** Items enter with an ID, a reason for deferral, and where the debt is anchored in code. Items leave when fixed or when explicitly dropped.

Raised from the M1.0 pre-commit review (2026-08-04). Findings 1, 2 and 4 from that review were fixed before commit and are not listed here.

---

## Accepted technical debt

### BF-001 · Corpus artifact format will not survive real data
**Impact:** High once real data lands · **Anchored:** `TODO(BF-001)` in [`pipeline.py`](../../services/corpus/pipeline.py) `CorpusArtifact`

`CorpusArtifact.names` is a JSON array, fully materialised. At the projected 2–4M Tier-A marks that is roughly a 50MB file, held in memory in `build_artifact`, again in `from_path`, and again per artifact in `tools/check_corpus`.

**Why deferred:** the fake provider emits eight names, so nothing today exercises the limit, and the format cannot be designed honestly before the [USPTO API key](blocked.md) reveals the real row counts and distribution.

**Note that this is wider than the deferred Parquet `land` stage.** The *guard* reads artifacts too, so it needs a streaming read path regardless of how `land` is eventually implemented. Deferring `land` did not defer this.

**Trigger:** must be resolved before the first real ingest, not after.

---

## Deferred findings — M1.0 review

Ranked as reviewed. None are correctness bugs in current behaviour.

### Medium

| ID | Finding |
|---|---|
| **BF-002** | `normalise_names` silently drops non-alphabetic entries. A holdout containing `3M` or `X.AI` loses those names with no signal, and the seal then seals the shrunken set. This exact trap cost time during M1.0 when digit-padded fixtures silently fell below `MIN_HOLDOUT_SIZE`. Should report what it dropped. |
| **BF-003** | `HoldoutIndex.contamination_key` returns bare strings (`"exact"`, `"phonetic"`, `"edit_distance"`). They become `excluded_by_holdout` dict keys and test assertions; a typo is silent on both sides. Should be an enum. |
| **BF-004** | `BlendEntry.weight` is validated but never read — confirmed by grep, the only references are in its own validator. Deliberate weighting is the blend's entire stated purpose, so the field is currently decorative. Lands with M1.3 induction. |
| **BF-005** | `tools/inventory_lock.py` has the same vacuous-pass shape that was just fixed in `check_corpus`: a misconfigured `[tool.brandforge.inventory].root` yields "nothing to check" and exit 0. Lower impact today (no inventories exist until M1.5) but the same silent-guard-defeat class. **Fix before M1.5.** |

### Low

| ID | Finding |
|---|---|
| **BF-006** | `check_holdout` uses `for _ in [1] if hits` — an obscure way to build a conditional single-element list. |
| **BF-007** | `build_artifact`'s contributing filter puts a walrus inside a conditional expression inside a comprehension. Hard to read. |
| **BF-008** | `HoldoutIndex.build` calls `phonetic_key(n)` twice per name. |
| **BF-009** | `_is_probable_acronym` docstring promises "or short and vowel-free"; the code implements only the first clause. |
| **BF-010** | `pad_names` is duplicated verbatim across three test files. Belongs in `conftest.py`. |
| **BF-011** | `SnapshotLedger` has no schema version, unlike `HoldoutSeal` and `CorpusArtifact` which both do. `SnapshotRecord(**entry)` will raise an obscure `TypeError` on drift. |
| **BF-012** | Providers present in `results` but absent from the blend are silently dropped, which can yield an empty artifact with no signal. |
| **BF-013** | The funnel test never exercises `too_long` or `empty_text`; the fake provider fixture lacks those cases. |
| **BF-014** | `run_check` previously took two adjacent `Path` parameters, swappable with no type error. Largely addressed by `CorpusPaths`, but the test adapter still takes two positional paths. |
| **BF-015** | `Use.EVALUATION` is declared and never referenced. |

---

## How this list is used

Before starting a milestone, scan for items whose **trigger** has arrived — BF-001 before the first real ingest, BF-005 before M1.5, BF-004 with M1.3.

Do not treat the low items as a batch to clear. Most are cheapest to fix while already editing the file in question.
