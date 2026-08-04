# ADR-0009: Trademark signals, never verdicts

**Status:** Accepted
**Date:** 2026-08-04

## Context

Trademark collision is the risk founders most need help with and are least equipped to assess. Surfacing it is high product value.

It is also the fastest way to acquire serious legal liability. If BrandForge says a name is "clear" and a founder builds a company on it and is then sued, we have a problem that no disclaimer buried in a settings page will fix. Trademark clearance is a legal judgment requiring a qualified attorney, and it depends on facts we do not have — actual use in commerce, common-law rights, intent, market channels.

The engineering here is easy. The framing is the part that matters, and it must be decided at design time, because retrofitting caution into a product that has already promised certainty is not possible.

## Decision

BrandForge surfaces **signals — evidence a human can act on — and never conclusions.**

1. **The data model stores evidence, not verdicts.** `trademark_signal` holds matched marks, jurisdictions, Nice classes, status, match type, and similarity. There is deliberately **no `is_clear`, `risk_level`, or `verdict` column.** The constraint is structural, not a UI convention that a future feature can quietly violate.
2. **UI language is calibrated and specific:** *"3 live marks with similar phonetics in class 42 — review with counsel."* Never "clear to use," never a green checkmark, never a single risk score.
3. **Terms of Service state explicitly** that BrandForge does not provide legal advice and that a trademark search is not a clearance opinion.
4. **Route to counsel.** Referral to trademark attorneys is a product feature, not an afterthought — it is the correct next action and plausibly a revenue line.

## Alternatives considered

- **Risk score (green/amber/red).** Far better UX; it's what users want. Rejected: a green light *is* a verdict, whatever the accompanying disclaimer says. The liability follows what the user reasonably understood, not what the footnote said.
- **Omit trademark screening entirely.** Zero liability. Rejected: it abandons one of the highest-value signals in the product, and founders will make the mistake anyway — with less information.

## Consequences

- **Accepted:** worse UX than a single traffic-light indicator. The output requires the user to read and think.
- **Accepted:** support burden from users asking "so can I use it or not?" — answered with routing to counsel, not a better indicator.
- **Gained:** local ingestion of USPTO bulk data (freely available) means screening is fast and cheap, with no per-query cost.
- **Required:** engineering discipline. Any future PR adding a computed verdict column or a green checkmark contradicts this ADR and must supersede it explicitly rather than slip through.
- **Required:** legal review of ToS wording before launch. This is a real dependency on M9, not a nicety.
