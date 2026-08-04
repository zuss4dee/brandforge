# Zone File Access — M0 Runbook

**Status:** Action required · **Owner:** Founder (requires a signing party) · **Blocks:** M3

> ⏱️ **This is the hidden critical path.** Zone-file access is a contractual process measured in **weeks**, not minutes, and it requires a legal entity to accept terms. Everything else in M0 is engineering we control. This is the one item that can silently slip the roadmap, which is exactly why it is scheduled first — see [ADR-0005](../adr/0005-tiered-availability.md).

---

## 1. Why we need it

The L0 tier of the availability cascade is a Bloom filter built from TLD zone files. A zone file lists every **delegated** domain in a TLD. Membership means "definitely registered," which lets us eliminate 90%+ of candidates locally, at zero marginal cost and zero network latency.

Without L0, every candidate falls through to rate-limited RDAP or paid registrar APIs — roughly **100× the cost per name**, with hard ceilings on run size. The economics of the product depend on this tier.

---

## 2. Action required from you

I can build every consumer of this data, but I cannot file the applications — they require an organisation identity and acceptance of legal terms on BrandForge's behalf. **These are yours to submit.**

### Step 1 — Establish the requesting entity
Applications ask for a legal entity, a business purpose, and a technical contact. Have ready:
- Legal entity name and address (if BrandForge isn't yet incorporated, this may be the blocker before the blocker — flag it now)
- A stated purpose. Ours is legitimate and worth stating plainly: **domain availability analysis for a brand-naming service.** Do not overstate scope.
- A technical contact email on a domain we control
- The IP address(es) that will download the zones

### Step 2 — Apply via ICANN CZDS
**https://czds.icann.org** — the Centralized Zone Data Service. Create an account, then request access per-TLD. Requests are approved by each registry operator independently, so approval is per-TLD and not simultaneous.

Priority order for our use case:

| Priority | TLDs | Why |
|---|---|---|
| 1 | `.com`, `.net` | The only TLDs most founders actually care about owning |
| 2 | `.org`, `.app`, `.dev`, `.xyz`, `.io`* | Common startup alternates |
| 3 | Everything else plausible | Cheap to request once the account exists |

> ⚠️ **Verify before assuming:** whether `.com`/`.net` are served through CZDS or through a separate Verisign zone-file agreement has changed over time, and I have not verified the current process. Check CZDS first; if `.com` isn't listed as requestable, go directly to Verisign's zone file access programme. **Please confirm the current path rather than trusting this document** — it's the kind of detail that goes stale.

### Step 3 — Track and re-apply
CZDS approvals **expire** and require periodic renewal. Put a recurring calendar reminder on this the day the first approval lands. An expired zone credential degrades L0 silently, which is the worst failure mode available to us — so it also needs a monitoring alert (see §5).

---

## 3. Important architectural caveat: ccTLDs have no zone files

**`.io`, `.ai`, `.co`, `.me`, `.sh` are country-code TLDs.** They are not covered by ICANN's gTLD zone-file regime and generally do not publish zone data at all.

This matters because founders love `.ai` and `.io`. For those TLDs the cascade **starts at L1** — no local Bloom filter, so every check is an RDAP or registrar call.

Consequences we accept:
- Per-name verification cost for ccTLDs is materially higher than for `.com`.
- Run-time budget governors must account for TLD mix; a brief that prioritises `.ai` is genuinely more expensive to serve than one prioritising `.com`.
- The inventory's pre-verified availability flags will be **`.com`-complete and ccTLD-sparse.** The UI must not imply equal confidence across TLDs.

This is a real product constraint, not just an implementation detail. It reinforces the choice of exact-match `.com` availability as our primary quality metric.

---

## 4. What I build once access lands (M3)

1. **Ingestion job** — scheduled download, integrity check, decompression, parse to normalized domain list, snapshot to S3/R2 with a content hash.
2. **Bloom filter builder** — target false-positive rate ~0.1%, sized for the `.com` zone. Versioned artifact, loaded into worker memory at boot.
3. **False-positive handling** — a Bloom filter can say "registered" for an unregistered name. Since a false positive only ever *hides* an available name, this is conservative and acceptable. High-scoring candidates rejected at L0 are spot-promoted to L1 to recover them.
4. **Freshness monitoring** — alert if the newest snapshot exceeds its expected age.

---

## 5. Failure modes to design against

| Failure | Impact | Mitigation |
|---|---|---|
| Application rejected | L0 unavailable; economics break | Apply early enough to appeal or restructure the request; keep registrar-API fallback viable |
| Approval expires unnoticed | Silent staleness — stale zone still loads, just wrong | Freshness alert on snapshot age, independent of ingestion success |
| Zone format or delivery changes | Ingestion breaks | Parser contract tests against a stored fixture |
| Snapshot arrives truncated | Bloom filter under-populated → we claim taken domains are available | **Size sanity check against the previous snapshot; refuse to build a filter that shrank unexpectedly** |

That last row is the dangerous one. A truncated zone produces a filter that reports registered domains as available — we would confidently tell a founder they can own a name that someone else already owns. **The size check is not optional.**

---

## 6. Status

| Item | Status | Date |
|---|---|---|
| Legal entity established | ☐ Not started | |
| CZDS account created | ☐ Not started | |
| `.com` / `.net` requested | ☐ Not started | |
| Priority-2 TLDs requested | ☐ Not started | |
| First approval received | ☐ Not started | |
| Renewal reminder set | ☐ Not started | |
