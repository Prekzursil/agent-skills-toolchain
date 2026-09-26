---
name: battlecats-stage-unlock-hook
description: Battle Cats 15.3 — two-hook Frida agent that bypasses time-limited stage
  gating. Hook addresses, semantics, why HGT01 isn't triggered, and where the toolkit
  lives.
metadata:
  node_type: memory
  type: project
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/battlecats-stage-unlock-hook
---

The Battle Cats stage-unlock workflow shipped 2026-05-20. Goal: every time-limited event stage playable at any time, no save edits, no device-time changes, no HGT01.

**Hook targets (file offsets in libnative-lib.so, equal to runtime offset-from-module-base because IDA `imagebase = 0x0`):**

- `sub_8A3350` @ `0x8A3350` — `int(__int64 start, uint end)`. Event status code. Force return `0` (= open / in range). `2` = `stage_shortcut_out_of_term`, `3` = `stage_shortcut_no_interval_times`, `4` = `stage_challenge_conditions`.
- `sub_8A3520` @ `0x8A3520` — boolean "currently in window" predicate. Force return `1` to keep the success branch alive.
- `sub_8A3750` @ `0x8A3750` — `bool(event_id)` calendar-tree membership check; reads from `xmmword_31EA78`. Force return `1`. **Added 2026-05-20**, no observed effect on Special-Stages menu visibility (the menu does not call this from its rendering path).

These cover the STAGE-ENTRY path via menu dispatchers `sub_5DFF40`, `sub_5E0130`, `sub_5E39B0`, `sub_5EA950`, `sub_5EBE40`, `sub_5ED0F0`, `sub_5EE3B0`, plus internal helper `sub_8A2CB0`.

**SCOPE LIMIT discovered 2026-05-20:** These hooks do NOT affect menu VISIBILITY of off-window calendar events. The Cat Base -> Special Stages list (Guerrillas, Cyclones, Anniversaries, rotating events) is built from a separate calendar tree populated by `sub_5F92E0` (init, no callers, 23 KB) and `sub_5FF760` (28 KB, called by `sub_64BF10`) that read PONOS-server-pushed schedule data (cached as encrypted `.dat` files in `/data/data/jp.co.ponos.battlecatsen/files/`). The filter that excludes off-window events from the tree was not located. **CORRECTED 2026-05-25: the filter is NOT in sub_5F92E0/sub_5FF760 — those are the game-state DESTRUCTOR / CONSTRUCTOR (the ctor builds the tree EMPTY). The real exclusion is in `sub_525AB0` (boot-time calendar recalc), loop @ `0x5262e9`: `if(!sub_819E20(rec,now)) skip` where sub_819E20 wraps sub_817020 (date/ver/platform). Located + statically patched in the rebuilt APK (sub_819E20→ret1 admits all to the tree) — see [[battlecats-event0-crypto-solved]]. Runtime attach CANNOT reach it (runs at early boot).** Diagnostic 60-second watch with all 8 hooks (3 flip + 5 trace including `sub_5DC7E0`, `sub_5FF760`, `sub_5F92E0`) recorded **zero call activity** while the user navigated Special Stages. Next attempt should either (a) drill into `sub_5F92E0` / `sub_5FF760` to find the time filter, or (b) intercept the server-data cache load to inject all-event-active data.

**Why HGT01 isn't triggered:** device time and save fields (`date_3`, `timestamp`, `energy_penalty_timestamp`) stay correct. We lie about the gate's *answer*, not the time. HGT01 only fires when those fields drift from the device clock.

**Binary verification:** libnative-lib.so SHA256 must equal `99bb6f36db1fc82a082f2a720c88325f9c146346fa0e0dbebae75205ab9eec7a`. Different hash = BC update = re-run the discovery from `find_regex(stage_shortcut_out_of_term)` → `xrefs_to` → `decompile` to find the new offsets.

**Toolkit paths:**
- Agent: `D:\ReverseTools\Android\battlecats-toolkit\tools\frida-trainer\bc_stage_unlock_agent.js`
- Harness: `D:\ReverseTools\Android\battlecats-toolkit\tools\frida-trainer\bc_stage_unlock.py`
- Launcher: `D:\ReverseTools\Android\battlecats-toolkit\launch_battlecats_stage_unlock.cmd`
- Implementation doc with IDA evidence chain: `D:\ReverseTools\Android\battlecats-toolkit\docs\stage-unlock-implementation.md`
- Design doc: `D:\ReverseTools\Android\battlecats-toolkit\docs\plans\2026-05-20-stage-unlock-design.md`

**Codex predecessor:** `event_date_navigation.py` + `bc_event_timewarp.py` are now legacy. They moved save dates and hooked libc time APIs, which triggered HGT01 inevitably. The new hook supersedes them. The Codex tools stay on disk as a fallback path for offset re-discovery if the hook breaks on a future BC update.

**IDA MCP entrypoint:** the analysis was driven via the ida_mcp plugin's HTTP RPC at `http://127.0.0.1:13337/mcp`. IDA must have the binary loaded before the port opens. Funnel only proxies `list_instances` / `select_instance` / `open_file`; the actual tools (`find_regex`, `xrefs_to`, `decompile`, `analyze_function`, `disasm`, `basic_blocks`) are reached by direct HTTP POST. See [[bluestacks-pie64-root-recipe]] for the broader Frida/LSPosed stack the hook depends on.

Related: [[mcp-token-reduction-initiative]] for why the funnel only surfaces management tools (lazy load); [[claude-code-401-auth-notes]] is unrelated and listed only because we share an ~/.claude directory.