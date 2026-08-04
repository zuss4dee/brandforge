# Contributing to BrandForge

Repository standards. Short, and every rule earns its place.

---

## Setup

```bash
make install    # uv sync + install git hooks
make check      # everything CI runs
```

`make help` lists all targets. Python 3.12 is pinned in `.python-version`; uv installs it.

---

## The two rules that matter most

Most standards here are conventions — breaking one produces a review comment. **These two guard failure modes that produce no symptom at all**, so they are enforced mechanically and are not negotiable in a code review.

### 1. `engine/` is pure — no I/O, no clock, no ambient randomness

`engine/` may not import `services/`, `apps/`, `tools/`, any network or filesystem module, or `random` / `time` / `datetime` / `uuid`.

Enforced by import-linter (`make boundaries`), configured in `pyproject.toml`.

**Why the ban on `random` and `time`:** determinism ([ADR-0012](docs/adr/0012-index-addressable-generation.md)) means a seed must be passed in explicitly. One `random.random()` call in a scoring function makes every score irreproducible and every golden fixture flaky — and it will not fail a test, it will just quietly make the product unexplainable. The import ban makes the guarantee structural rather than a habit.

**If the boundary blocks you, that is a design conversation, not a config edit.** Load data in `services/` and pass it in.

### 2. Ruleset inventories are append-only

Entries in `engine/rulesets/**` are **never removed or reordered**. Deprecate with `status: deprecated`; the entry keeps its position forever.

Enforced by `make inventory`, backed by committed `*.lock.json` files.

**Why:** a candidate's identity is its index in a mixed-radix address space. Inventory size is the radix of a digit. Remove one entry and every subsequent digit shifts — **every stored provenance in the system now replays to a different name.** Nothing crashes. Nothing logs. No test fails. The corruption is total and invisible.

To change an inventory legitimately: append. If you genuinely need to restructure, that mints a **new address space** — it is not an in-place edit. See [ADR-0014](docs/adr/0014-append-only-rulesets.md).

Regenerate locks with `make inventory-lock` and **commit the diff** — that diff is the reviewable artifact, exactly like a golden fixture.

---

## Architecture Decision Records

Any decision that is **expensive to reverse**, or that a future engineer would reasonably question, gets an ADR before the code lands. Format and process: [docs/adr/README.md](docs/adr/README.md).

ADRs are immutable once accepted. A changed decision gets a **new** ADR that supersedes or amends the old one — the old one stays, so the reasoning trail survives. See [ADR-0008](docs/adr/0008-provenance-retrieval.md) for an example of an amendment done properly.

Library picks and file layout do not need an ADR. Boundaries, data-model shapes, external dependencies, and legal posture do.

---

## Code standards

| | |
|---|---|
| **Formatting** | Ruff format. Not negotiable, not discussed in review. |
| **Linting** | Ruff, config in `pyproject.toml`. Suppressions carry a reason: `# noqa: RULE — why`. |
| **Types** | MyPy `strict`, no per-module opt-outs. New code is fully annotated. |
| **Imports** | Absolute only; relative imports are banned (`TID252`). |
| **Docstrings** | Modules and public functions. Explain **why**, not what — the code says what. |

### Determinism

Anything in `engine/` must be reproducible from its inputs. No hidden state, no clock reads, no unseeded randomness, no dict-ordering assumptions across processes. If a function cannot be re-run to the same answer next year, it does not belong in `engine/`.

### Comments

Comment the surprising, not the obvious. A comment explaining *why a boundary exists* or *why the naive approach fails* is worth ten explaining what a loop does.

---

## Testing

- Tests live in `tests/`, mirroring the source tree.
- Prefer **property-based tests** (Hypothesis) for engine invariants. Determinism, bijectivity, and constraint soundness are universally quantified claims; example-based tests sample them thinly.
- Mark anything slow `@pytest.mark.slow` so pre-commit stays fast.
- **A bug fix ships with the test that would have caught it.** Red-team findings become permanent regression tests.

Coverage is reported, not gated. A coverage threshold measures diligence in writing tests, not their quality, and gaming it is easier than satisfying it.

---

## Commits and branches

- Branch from `main`: `m1/phonotactic-grammar`, `fix/lockfile-ordering`.
- Direct commits to `main` are blocked by a pre-commit hook.
- Conventional-commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `adr:`.
- Reference the ADR when implementing one: `feat(engine): mixed-radix address space (ADR-0012)`.

Write commit messages for someone bisecting a regression eighteen months from now.

---

## Review checklist

- [ ] Does this need an ADR? Has it got one?
- [ ] Does anything new in `engine/` reach for I/O, a clock, or randomness?
- [ ] If an inventory changed — is it an append, and is the lockfile diff in the PR?
- [ ] Do new engine invariants have property tests, not just examples?
- [ ] Are user-visible claims traceable to stored data? (No number in the UI without provenance.)
- [ ] Does a trademark or availability change respect [ADR-0009](docs/adr/0009-trademark-signals-not-verdicts.md) — evidence, never verdicts?

---

## Dependencies

Adding one is a decision with a maintenance cost. Prefer the standard library; prefer a small well-maintained package over a framework; justify anything that touches the engine's determinism. `engine/` dependencies must be pure-compute (numpy is fine; an HTTP client is not, and import-linter will say so).
