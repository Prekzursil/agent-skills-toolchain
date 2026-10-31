---
name: seed-golden-journey
description: Use when an app needs a keystone acceptance test that proves the real product actually works end to end, not just that units pass or coverage is high. Scaffolds a HELD-OUT golden-journey test that launches the REAL app, drives the ONE primary user journey, and asserts a REAL artifact on disk (a valid media file via ffprobe, a downloaded file, a screenshot) rather than element-present. Parameterized for Electron (playwright electron launch), web (Playwright page goto), and CLI (spawn plus assert output file), with an annotated fill-in-the-blanks template derived from the Reframe exemplar. Makes the journey the merge gate and forbids citing coverage as done. NOT for broad unit/integration coverage (see two-tier-verify); NOT for mocked component tests.
---

# seed-golden-journey

Coverage and "unit-green" are a **proxy the implementer controls**, so a capable agent optimizes
that proxy and stops — while the real A→B→C user journey stays broken. Live proof: Reframe shipped
v1.4 with **100% coverage and green units**, and "Make Shorts" never produced a file on Windows.
Three real Windows-only bugs sat exactly at the seams the unit tests mock and Linux CI can't reach.
The one signal that caught them was a **held-out golden-journey that drove the real app and
asserted a real vertical short on disk**.

This skill scaffolds that keystone: the single external **done-signal** the implementer can't
author or fake. It is the highest-leverage thing a user provides — no hook substitutes for it.

## The five rules of a golden journey

1. **Pick the ONE money journey.** The single flow that is the product's reason to exist — the
   thing that, if it silently broke, the product is worthless regardless of coverage. Reframe:
   *"Make Shorts produces a real vertical short file on disk."* One journey, not a matrix.
2. **Drive the REAL app — nothing stubbed.** Launch the actual built binary/app; drive the real
   UI; let it hit the real backend/sidecar, real ffmpeg, real filesystem. The bugs live precisely
   at the seams unit tests mock; a mocked journey re-hides them.
3. **Assert a REAL produced artifact, not element-present.** "Button rendered" / "toast appeared"
   is theater. The pass condition is the *thing the user came for* existing and being valid on

### The assertion ladder (climb every rung — stopping early is theater)
### Wiring the async completion (background jobs)
### Stack recipes — the LAUNCH is the only part that changes
### Make it the gate + forbid the reward-hack surface
### Anti-patterns
