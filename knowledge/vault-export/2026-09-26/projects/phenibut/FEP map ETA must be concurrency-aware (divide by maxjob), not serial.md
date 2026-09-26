---
title: FEP map ETA must be concurrency-aware (divide by maxjob), not serial
type: note
permalink: main/projects/phenibut/fep-map-eta-must-be-concurrency-aware-divide-by-maxjob-not-serial
tags:
- fep
- monitor
- eta
- dashboard
- phenibut
- gotcha
---

**A live FEP-map ETA computed as `pace × remaining` (serial) over-counts by ~N× when the map runs N legs concurrently (`-maxjob N`).**

The scw_fep_dashboard originally showed 22-28h when the real ETA was ~1/4 of that, because `pace = elapsed / legs_done` then `eta = pace × (total - done)` assumes one-leg-at-a-time.

**Fix:** `eta = pace × (total - done) / concurrency`, where `concurrency = max(1, min(active_legs, total - done))`. Applied in `C:\Users\Prekzursil\.biomni-mcp\scw_fep_dashboard.ps1`.

**Caveat:** even concurrency-adjusted, the ETA under-weights heterogeneous legs — if the done legs are the fast solvent ones and the slow complex legs haven't landed, it's optimistic until the first representative (complex) leg completes. See [[FEP+ per-leg wall-times (10ns 12-lambda OPLS4, H100) — solvent ~42min, complex ~2.5-3h]].

**How to apply:** any multi-worker job ETA must divide serial pace by effective concurrency, AND be flagged "firms up when the first slow/representative unit completes" — never present the serial number as the ETA.