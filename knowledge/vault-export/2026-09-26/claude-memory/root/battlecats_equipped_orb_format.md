---
name: battlecats-equipped-orb-format
description: BC per-cat equipped talent orbs live in BCSFE's unnamed uidiid2/90700
  block (candidate, needs empirical diff); BCSFE is GPL-3
metadata:
  node_type: memory
  type: project
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/battlecats-equipped-orb-format
---

Per-cat **equipped** talent orbs in the BC save are NOT modeled by any upstream tool (BCSFE's `TalentOrbs` is only the GLOBAL inventory bag `dict[orb_id→count]`; ruinzstorm/BattleCatsHacker have zero orb code). They live in BCSFE's opaque **`uidiid2` block**: `save.py:730-748` (read), `1826-1837` (write), `2468/2849` (serde), inside the `game_version>=90700` gate. Layout BCSFE already consumes = `short outer_count`, per entry `short cat_id?` + `byte slot_count?` + per slot `byte slot_index?` + `short orb_id?`, then `bool ub10` (once, after loop, line 746), `assert int==90700`. Adding `EquippedTalentOrbs` as a pure byte-reinterpretation → byte-identical round-trip BY CONSTRUCTION (same primitive op sequence). `orb_id` shares the global-bag id space → resolve via BCSFE `OrbInfoList.get_orb_info` (composes 4 files: DataLocal/equipmentlist.json[="equipment"==orbs] + equipmentgrade.csv + resLocal/attribute_explonation.tsv + equipment_explonation.tsv). Orb-id name fmt `<effect>-<grade>-<trait>` e.g. `massive-s-alien`.

**STATUS = STRONG CANDIDATE, NOT confirmed.** cat_id/slot/orb_id mapping is structural inference (no editor names these fields). **Confirm before shipping write code:** bracketed empirical diff — pull baseline → equip exactly ONE orb on a known empty-slot cat (note cat + orb), save → pull → diff; the only `90700`-block change pins cat_id/slot/orb_id + the empty sentinel. Full plan: `D:\WSA\_analysis\gamedata\equipped_orb_save_format.md` §5.

**BCSFE is GPL-3.0-or-later** (pyproject + LICENSE + README copyleft) → add `EquippedTalentOrbs` INTO the BCSFE fork (GPL-native), don't vendor a copy into a maybe-closed toolkit. Personal use = no obligation.

**STATUS 2026-06-01: SHIPPED + PUSHED.** IDA-sealed the format (reader sub_8079D0/writer sub_80C890, empty=sparse-by-omission); BCSFE fork branch `feat/equipped-talent-orbs` has `core.EquippedTalentOrbs` (byte-identical round-trip, JSON-safe edit API, 21 tests); trainer-gui has a keystone-safe Orbs panel (`feat/trainer-gui-p2c`); unified toolkit consolidated at `D:\ReverseTools\Android\bc-toolkit-unified-wt` (branch `consolidate-unified`, off ralph-hardening tip). **Live save pushed & verified**: 29 S-grade orbs (orb-capable owned cats) + 17 reworked decks (slots 2-10/12-19; decks 1&11 locked) via `D:\WSA\_analysis\apply_bc_edits.py`, dual-write SAVE_DATA+.OLD, md5 74f2ec2f, pre-push backup `bc-save-recovery\SAVE_PREPUSH_20260601_103241.bin`. **adb GOTCHA:** git-bash mangles `/sdcard` path args to adb.exe (→`C:/Program Files/Git/sdcard/...`) — prefix adb pull/push/shell with `MSYS_NO_PATHCONV=1` (and use Windows-style local paths). Grade ladder gradeID 0=D..4=S; ~38 trait-generic orbs (e.g. "common threat") deferred (need matchup choice → finish via GUI).

**Corn/Maize Cat (718) = VERSION SKEW, RESOLVED (not an error):** 15.3.0 game data has 718 `total_forms=2, tf_id=0` → no True form in 15.3.0; the wiki's "Corn True form" shipped AFTER 15.3.0. The local matrix is CORRECT for our 15.3.0 save — NO rebuild needed. Both Boulder(581) and Maize(718) are valid no-True-form exemplars for 15.3.0. Authoritative roster: `D:\WSA\_analysis\gamedata\orb_capable_roster_15.3.0.{md,csv}` = **180 orb-capable cats (146×1-slot + 34×2-slot Ubers) = exactly 180 talented (biconditional EXACT in 15.3.0); 438 no-True-form**. Relates to [[bcsfe-save-roundtrip]], [[battlecats-trainer-gui]].