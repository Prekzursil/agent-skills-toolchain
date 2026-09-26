---
name: bc-batch-content-ships-in-en-apk
description: iter-18 tbcml recon — the bucket-(d) "needs-real-MapStageData" batch
  events already have real content in the EN APK; the blocker is the server schedule,
  not missing content
metadata:
  node_type: memory
  type: project
  originSessionId: 6e6b50ba-b8c8-4bf8-89ac-f379e04fc0bd
permalink: main/claude-memory/d-reverse-tools-android-battlecats-toolkit/bc-batch-content-ships-in-en-apk
---

iter-18 tbcml recon (dat-cache-decode/tbcml_recon.py on the merged 15.3.0 EN APK)
directly inspected the game packs and **falsified the wave_plan/iter-17 premise** that the
celebration + behemoth batch events are bucket-(d) "needs-real-MapStageData". Their content
already ships in the EN APK:

- Memories of 2024 → REGULAR_EVENT (S) map_index **392** — `MapStageDataS_392.csv` real
  (energy 50, stages "Memories of Spring/Summer/Fall/Winter"); Map_option id1392 = "2024年思い出アルバム".
- Memories of 2025 → S **418** (StageName_RS row418, same Memories stages). EXISTS.
- Fireworks Spectacular! → S **410** (StageName_RS row410 "Fireworks! (Deadly)/(Merciless)"). EXISTS.
- Empress' Report/Excavation 1 → S **344** (StageName_RS row344 "8/29 Journal|...|8/31 Escape"). EXISTS.
- Behemoth Forest/Desert/Volcano → BEHEMOTH (Q) **0/1/2** only (3 maps total: ガープラ密林/
  アシビニ砂漠/ジャンフォレ火山 = Map_option 31000/31001/31002). The "II/III" difficulty tiers
  have NO separate MapStageData in EN.

**Why:** This explains iter-16 — feeding MapID 1392 a live ACTIVE schedule row STILL didn't
render, because content (MapStageDataS_392) was never the gap. The binding blocker is the
SERVER schedule (event_0.dat → sub_81AE20 → sub_817020 gate), not missing content. A
content-only tbcml APK therefore cannot surface these; they need the schedule path (forbidden
this wave) or a baked sub_817020 gate-bypass (HGT-safe per master plan, never tried).

**How to apply:** When a future wave claims an event "needs content baked", verify against the
actual packs first (tbcml_recon.py pattern: extract APK → enumerate MapStageData*/StageName_*/
Map_option). EN ships ~433 regular-event (S) maps + 3 behemoth (Q). Genuinely content-absent
families are collaboration / region-exclusive, not celebration/behemoth-base. See
[[ralph-runtime-memory-broken]] for the file-memory workaround used by this loop.