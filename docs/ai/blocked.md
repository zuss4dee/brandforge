# Blocked — awaiting human action

A pointer list, not a source of truth. Detail lives in the linked documents; this file exists so a session can see in ten seconds what is waiting on a human, rather than reading eight design docs to find out.

**Keep it short. Delete rows when they clear.**

| # | Blocked on | Blocks | Detail |
|---|---|---|---|
| 1 | **USPTO Open Data Portal API key.** Create a USPTO.gov account, register for ODP, obtain a key, export as `BRANDFORGE_USPTO_API_KEY` | M1.0 acquisition, snapshot validation, the funnel report, and the spike that resolves the five unverified items in the ledger | [M1.0 §8](../design/06-m1-0-corpus-assembly.md) · [verified-facts §3](verified-facts.md) |
| 2 | **Zone-file access agreements.** ICANN CZDS and/or Verisign — weeks of contractual lead time, and the current path is itself unverified | M3 availability. Without the L0 bloom filter, per-name verification cost rises roughly 100× | [zone-file runbook](../ops/zone-file-access.md) |

**Both clocks run whether or not engineering is happening.** Item 2 has been open since M0 and carries the longest lead time in the project.

---

## Not blocked, but worth knowing

| Item | Status |
|---|---|
| Legal review of trademark ToS wording (signals, never verdicts) | Needed before M9 launch — [ADR-0009](../adr/0009-trademark-signals-not-verdicts.md) |
| Funded-startup name list for the M1.7 evaluation ceiling | Needed before M1.7; must be sealed *before* induction tooling exists — [M1.0 §5](../design/06-m1-0-corpus-assembly.md) |
| Rater panel recruitment for the M1.7 indistinguishability study | ~2 weeks lead time — [evaluation strategy §5](../design/04-generation-evaluation.md) |
