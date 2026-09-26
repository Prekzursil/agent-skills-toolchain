---
name: battlecats_guerrilla_window_re
description: BC 15.3.0 guerrilla/Aku rotating-stage availability RE — the +1 availability
  lever + address map (resolves the 2h59m Aku-timer gap)
metadata:
  node_type: memory
  type: project
  originSessionId: 3cd9445a-ab17-4eec-ad05-c1d1bf411c40
permalink: main/claude-memory/root/battlecats-guerrilla-window-re
---

BC EN 15.3.0 `libnative-lib.so` (SHA `99bb6f36…`, IDA imagebase 0). Solved the "2h59m reroll / Aku timer" gap ([[battlecats_stage_unlock_hook]], supersedes the GAP-LEDGER Aku-unknown). The decisive constant was **10800 (3h, 0x2A30)** — `10740` has 0 hits; "2h59m" = a 3h window's countdown rounded down.

**The system = the Guerrilla / limited-time rotating-stage scheduler.** A `std::array<Record,6>` (6×24B) at **gameState+4536** (gameState = `sub_653C80()`). Strings in the readers prove it: `urguerrilla_warning00`, `assault_warning`, `labyrinth_*`, `demon_error_popup`/`demon_timelimit` (**demon = Aku**), `treasure_festival_*`, `otasuke_sale%d`.

**24B Record:** +0 active · **+1 available-now (THE read gate)** · +2 s8 pending-count(×10800s) · +8 double start · +16 double end.
**Key funcs:** `sub_4F1C40(arr,now)` advancer (the 10800 hits) · `sub_4F1E20(arr,idx)`=public getter→`arr[idx].+1` (bounds<6) · `sub_4F1E40`=countdown `fmax(end−now,0)` · `sub_4F1D40`/`sub_4F1DB0` save (de)serialize → **state is in the save file** · `sub_9B4EF0`=now=`system_clock::now()/1e6` (**device wall-clock, NOT server**). Advanced on day-change `sub_5AC690` (+ calendar builder `sub_525AB0`) and scene-mode-44 `sub_6A65B0`. Parallel server-schedule layer at gameState+7440 (`sub_6EA320`). Giant readers `sub_585EB0`(66K)/`sub_598460`(81K).

**THE LEVER (HGT-safe — no clock change):** force **`+1`=1 on all 6 records** (gameState+4536+24*k+1). Three ways: Frida hook `sub_4F1E20`→ret 1 / write the 6 bytes; static `.so` patch `sub_4F1E20`→`mov al,1;ret`; or BCSFE save-edit (it's persisted). This is the read field every consumer uses — explains why the prior live force "only painted crowns" (cosmetic field, never +1). **EMPIRICALLY CONFIRMED live 2026-06-05** (read-only Frida dump `source/reports/_guerrilla_dump.py`: gameState=0x7fec3dba2530; end−start=10800 EXACT all 6 slots; all expired ~12d ago so avail=0 → no guerrilla/Aku stage showing). **Durability nuance:** a bare +1-byte WRITE is transient (advancer sub_4F1C40 re-expires stale windows on day-change/scene-mode-44) → robust lever = hook/patch sub_4F1E20→ret1, OR set active=1 + extend end=now+10800*N. Live WRITE-test held (live-modding caution — save-copy or user go-ahead first).

RED HERRING (don't re-chase): `sub_4F2020/4F2420` (ids 817/818, `nekokan_pack`) + `sub_4F1E80` (811/819) = nekokan-SALE/event-descriptor side, NOT the +2 reroll. +2 writer still OPEN (look in +7440 subsystem or `sub_585EB0`; RNG state at gameState+302112) — but LOW priority, the +1 lever works regardless.

Full doc: `source/reports/research/ROTATING-WINDOW-AVAILABILITY-RE-2026-06-05.md`. Device Frida-confirm (dump gameState+4536 across a window flip) = PENDING. IDA MCP = direct HTTP POST `127.0.0.1:13337/mcp` (zeromcp, 61 verbs: find type=immediate, decompile, xrefs_to, py_eval…); funnel hides the verbs. Complements [[battlecats_startup_filter_rebuilt_apk]] (calendar-tree admission for off-window monthlies) — different layer.