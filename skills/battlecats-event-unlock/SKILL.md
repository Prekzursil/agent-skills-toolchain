---
name: battlecats-event-unlock
description: Use when working on Battle Cats (EN 15.3.0, rooted BlueStacks) special/event/tower stage visibility or on-demand unlock RE — gives the proven dual-dependency model (tree-admission + valid schedule row), the decisive offsets, the Event Summoner tool, and the approaches already proven DEAD so you don't repeat them.
---

# Battle Cats — Special / Event Stage Unlock

Reverse-engineering on-demand unlock/visibility for special, event, and tower
(Heavenly Tower) stages in Battle Cats **EN v15.3.0** (`jp.co.ponos.battlecatsen`,
clientVersion `150300`), x86_64 `libnative-lib.so`, on rooted BlueStacks Pie64 +
frida-server, ADB `127.0.0.1:5555`. Module imagebase 0x0, so **RVA == file offset**.

## The one rule — read this first

A tile **RENDERS only if BOTH** of these hold:

1. **Tree admission** — the mapid is admitted to the active-event-window RB-tree
   `sub_5F8AC0` (game_state + 11736), which is built **ONCE at launch** by `sub_525AB0`.
2. **Valid schedule row** — a valid `event_0` (sale.tsv) row covers "now" for that mapid.

Neither half alone works:
- **Row alone** → record loads + passes the activeness gate, but **0 tiles render**
  (mapid not in the tree).
- **Admit alone** → **CRASHES** (null-deref: tree entry with no row body to draw).
- **Time-travel** supplies both, but trips HGT / Recovery Mode → rejected (see below).

You must satisfy BOTH halves, with no clock change and no save edit.

## PROVEN DEAD — do NOT retry these (rigid; do not adapt them away)

These were each tried and failed on this exact stack. Re-attempting them is wasted work.

- **Forcing the render/display gate `sub_817020` TRUE** (callers `0x7f5d17` / `0x81bb53`).
  Too late in the pipeline to create a tree entry. Tower ids 7000–7010 were 11/11 in the
  candidate map yet **0/11 rendered**. The old stage-unlock trainer does this — it does
  NOT surface tree-absent events.
- **Always-on `sale.tsv` row ALONE** (no tree admission). A 470-row always-on patch
  rendered **0 new tiles**. It is a runtime-registration problem, not a row-body schema
  problem.
- **Blanket-forcing `0x5292e4`** → **CRASHES** BC. Any injection must be scoped and
  structurally valid (one mapid, with a backing row).
- **Naive time-skipping / OS clock jump / MITM `getTime` + `.dat` cache-clear.**
  Trips BC 15.3 **Recovery Mode** (which HIDES events) and can cascade into the
  **99-day half-XP HGT penalty**. NEVER do MITM, cache-clear, or time-endpoint
  manipulation on this stack.

## WHAT WORKS

- **Scoped admission.** Force `sub_819E20(rec, now)` @ `0x819E20` → return **1**, at call
  site `0x52653f` inside `sub_525AB0`, **scoped to one target mapid only** (mapid is read
  at `rec+0x5C` / `rec+0x60`). This fires during the Special Stages menu rebuild, so you
  must **attach and then navigate** to the Special Stages menu to trigger it.
- **PLUS a valid `event_0` row** for that same mapid — use an always-on sentinel end-date
  `20300101`.
- Supporting offsets (use only as needed, scoped):
  - `sub_5F8DF0` @ `0x5F8DF0` — id-band fallback gate.
  - `sub_5F8A10` @ `0x5F8A10` — native tree-insert helper (alt path).
  - `sub_81BAF0` @ `0x81BAF0` — render support.
  - Entry gates **to play** the stage: `sub_8A3350` @ `0x8A3350` → 0,
    `sub_8A3520` @ `0x8A3520` → 1.
  - Reversible row-skip NOP @ `0x7F6EAF` (only if the row-builder skips the row).
- **HARD BOUNDARY:** if a mapid has no local StageData / assets on-device, **no hook makes
  it playable**. It needs a content bake (tbcml route, out of scope for the hook approach).
  Forcing a tile for a mapid with absent content crashes on tile-build.
- **General lesson:** single-function Frida hooks are **reliable** here — the working
  stage-progression trainer proves it. The historical failure was *conceptual* (missing
  the data + admission dual requirement), not a hooking-skill gap. Do not overcomplicate
  with multi-hook forging schemes.

## Tools (point to these; do not reproduce their code)

Located in `D:\ReverseTools\Android\battlecats-toolkit\tools\frida-trainer\`:

- `bc_event_index.py` — `list` / `resolve <name|mapid>` → `{name, mapid, windows,
  active_now, local_assets}`. Decodes `event_0.dat` (AES-128-ECB, key `89a0f99078419c28`).
- `bc_event_summon.py` — host CLI (attaches, does **not** spawn):
  `probe` / `summon --mapid <id> [--play] [--render-support] [--keep-alive]` / `stop-host`.
- `bc_event_summon_agent.js` — the Frida agent (probe / summon RPC; fully reversible).
- **event_0 patch:** `dat-cache-decode/build_event0_allon.py` + `push_event0.py`.
  HGT-safe in-place push = `su -c 'cat new > files/<md5(event_0)>.dat'`, then chown 10065,
  restorecon, and **force-stop first**. On dup-device setups push manually with
  `adb -s 127.0.0.1:5555`. Never delete-and-recreate (changes owner/SELinux context).
- **BCSFE time-fix** (clears a NEW drift penalty — not an active recovery countdown):
  `BCSFE-Python` → `Fixes.fix_time_errors`.

## Workflow (the actionable core)

1. **Resolve the target.** `bc_event_index.py resolve <name>` → mapid; confirm
   `local_assets == true`. If false, STOP — this needs a content bake, no hook will help.
2. **Read-only probe** (stock boot). `bc_event_summon.py probe` → confirm the mapid is
   ABSENT from the tree and `sub_819E20` returns 0 for it. Establishes the baseline.
3. **Ensure the data half.** Patch `event_0` with an always-on (`20300101`) row for the
   mapid; push HGT-safe in-place; verify the md5 on device.
4. **Scoped admit.** `summon --mapid <id> [--render-support] --keep-alive`, then
   **navigate to Special Stages** to trigger the rebuild; `treedump` to confirm the mapid
   was admitted.
5. **PASS criteria.** Native tile renders, stage opens, **NO HGT / Recovery**, **NO
   save-timestamp change**, and detach restores stock behavior.
6. **Single actor, serial** for any live Frida / ADB step — the emulator is a shared
   resource. Subagents do code/docs only; they never touch the live game, ADB, clock,
   or save.

## Reference

Full detail lives in:
- `D:\ReverseTools\Android\battlecats-toolkit\docs\EVENT-UNLOCK-PLAYBOOK.md`
- `docs\research\2026-05-25-DEFINITIVE-TRUTH.md`
- `docs\event-summoner-design.md`
- `dat-cache-decode\STARTUP_FILTER_RE.md`
