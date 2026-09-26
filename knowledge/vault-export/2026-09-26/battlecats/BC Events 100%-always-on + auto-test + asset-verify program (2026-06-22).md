---
title: BC Events 100%-always-on + auto-test + asset-verify program (2026-06-22)
type: note
permalink: main/battlecats/bc-events-100-always-on-auto-test-asset-verify-program-2026-06-22
tags:
- battlecats
- events
- frida
- reverse-engineering
- compaction-checkpoint
---

# BC Events Comprehensive Program (EN 15.4.1, rooted BlueStacks)

User goal: **100% of events always-on WITHOUT reset**, **auto-tested visibility at 100% confidence (NOT OCR/guessing)**, and **100% asset-completeness** (every cat/unit/event has its art in-game, no blurs/blanks). Decision log: `D:\ReverseTools\Android\battlecats-toolkit\docs\EVENTS-GRILL-DECISIONS.md`. Design wf `wfw4x1rvb`; offline build wf `w1ni1076b`.

## Observations
- [verdict] W1 no-reset-all-events is NOT pure data-only — the reset is `Map_option.csv` reward-reset-type (col8 = 0 none / 2 reset-on-reclear "Golden Tower bug" / 3 reset-gate), a CONTENT field independent of event_0. So injecting an always-on window for an OFF-ROTATION col8=2 event re-creates the reset.
- [mechanism] DATA-ONLY HGT-safe no-reset = window-EXTEND: edit ONLY event_0 field2 end_date->20300101, byte-preserve field0 start_date (the window-instance key) — works ONLY for col8 in {2,3} events LIVE in their real window now + col8==0 re-admits.
- [mechanism] Off-rotation col8=2 needs HYBRID: a Frida reset-suppression hook on the reset-WRITER and/or a BCSFE save re-grant; foreign-container gauntlet 24xxx + colosseum 36xxx need scoped Frida sub_819E20->1 (or static .so patch); dojo 6xxx/11xxx/30000 must NEVER route via event_0.
- [open-question] The reset-WRITER (the fn that zeroes clear_progress on new-occurrence display) is NOT yet located. sub_4DF750/4DF8B0/4DFA10 are admission READS inside sub_819E20, NOT the writer. A device experiment (data write-watchpoint on clear_progress) must locate it + confirm whether start_date or an interval-derived epoch is the instance key.
- [feasible] W2 auto-test daemon: a read-only Frida daemon calling the game's OWN decision fns sub_5F8AC0(admit) && sub_81BAF0(active) as NativeFunctions — ZERO Interceptor.attach (crash-safe; render-thread hooks crash). RB-tree node: left@0x00 right@0x08 parent@0x10 key-int32@0x1C enable@0x20; root@treeAddr+0x20 count@+0x28. Calendar tree at gs+0x2DD8. SHA self-verify gate (so_sha256 9605648b...) so it reads the RIGHT bytes. 5-way classifier vs BC-EVENT-ROSTER (647 rows). Honest limit: proves the engine's DECISION to render, not literal GPU pixels.
- [feasible] W3 asset-completeness is OFFLINE via tbcml: imgcut<->sheet OOB rect bounds = the strongest collab-GC detector (+ transparency/size/hash heuristics). all-866 verdict needs the FULL current server-pack set (APK ~31-56 units, on-disk packs ~440/866 — both partial); the checker separates "GC/broken" from "not-downloaded".
- [device] /data is write-blocked (BlueStacks sdb1 ext4 I/O-error -> aborted journal -> ro remount; host NOT full). READ-only Frida + memory reads do NOT write /data, so the W2 daemon, the 15.4.1 IDA offset re-derive, and the reset-writer locator CAN run on the current faulted device NOW. Only WRITES (event_0 push, save re-grant, .so sideload, full server-pack pull) wait on a disk repair OR a fresh BlueStacks Pie64 instance. Save backed up: `D:\ReverseTools\Android\apk-15.4.1\out\SAVE_DATA_real` (583925B).
- [real-state] Live save confirmed: Golden Tower 7010 + Sengoku/Road-to-Unification 1385-1389 RESET to 0; Infernal Tower 7006 + Heavenly Tower 7000 retained at floor 50. Verified BCSFE accessors: tower = `save.tower.chapters.chapters[mapid-7000].chapters[star].stages[i].clear_times`; event = `save.event_stages.chapters[1].chapters[mapid-1000].chapters[star].clear_progress`.
- [naming] User-reported "missing" Behemoth/Gapra/Ashvini/Jinfore = ONE event Behemoth Culling (maps 31000-31002, reset-SAFE, daily ~4h slot). "2 new Engage Commander" = 1386/1387 (Nyandam/Hannya), same 1385-1389 Sengoku cluster, benign.
- [separate] De-gacha companion (earn 567 gacha cats by playing via BCSFE save-grant) engine + trainer-gui Progressive panel committed 2ef8b72 on feat/progressive-degacha-gui; 24 engine tests; in-game validation device-blocked (same disk fault).

## Relations
- relates_to [[BC Event Summoner]]
- relates_to [[BCSFE save round-trip]]
- relates_to [[Frida hot-path interceptor crash]]
- relates_to [[Battle Cats stage-unlock hook]]
