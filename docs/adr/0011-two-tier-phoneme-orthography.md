# ADR-0011: Two-tier generation — phonological skeleton, then orthographic realisation

**Status:** Accepted
**Date:** 2026-08-04
**Implements:** [M1 Generation Engine §0.5, §4](../design/03-generation-engine.md)

## Context

The obvious way to generate names is to emit strings directly. This conflates two decisions that are genuinely separate:

`/kɔːrveɪn/` can be written *Corvane*, *Korvane*, *Corvain*, *Korvayne*. These are **the same name phonologically** and **different assets commercially** — different domains, different trademarks, different registers (`k` reads modern/tech, `c` reads classical).

Generating in orthography also makes pronounceability scoring incoherent: we would be scoring a spelling as a proxy for a sound.

## Decision

Generate a **phonological skeleton first** — phonemes, syllables, stress. Then **realise** the top *K* orthographic variants (proposed K = 8) from it via weighted phoneme→grapheme rules, each variant carrying fidelity, corpus frequency, and register annotations.

Pronounceability is scored once, in phoneme space. Spellability is scored on the realisation mapping via a **g2p round-trip test**: realise to graphemes, run g2p back, measure recovery of the original phoneme sequence.

Variants are grouped under a shared phonological form in the inventory.

## Alternatives considered

- **Orthography-only.** Simplest possible engine. Rejected: abandons the same-sound-different-spelling capability entirely, and makes pronounceability scoring a proxy measurement rather than a direct one.
- **Phoneme tier in M1, orthography later.** Smaller M1. Rejected: the orthographic variant is a choice point in the address space. Adding it later restructures that space, which [ADR-0014](0014-append-only-rulesets.md) correctly makes an expensive MAJOR bump. Cheap now, costly in six months.

## Consequences

- **Accepted:** an additional engine layer, a full p2g rule set, and roughly 8× more surface forms to gate, dedupe, and store.
- **Accepted:** we need a reliable g2p implementation for every language pack, which is a real constraint on how cheaply a new language can be added.
- **Gained:** the highest-value product capability in M1 — *"Corvane.com is taken; Korvane.com is available, same pronunciation."* This is only possible if generation happened in phoneme space, which is why competitors don't do it.
- **Gained:** spellability becomes a mechanical, cheap, human-free measurement instead of a judgement call.
- **Gained:** availability checks fan out across variants of one phonological form, so a single good-sounding name gets eight chances at an available domain rather than one.
