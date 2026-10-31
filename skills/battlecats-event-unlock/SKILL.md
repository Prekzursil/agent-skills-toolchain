---
name: battlecats-event-unlock
description: Use when working on Battle Cats (EN 15.4.1, rooted BlueStacks) special/event/tower
  stage visibility or on-demand unlock RE - gives the proven dual-dependency model
  (tree-admission + valid schedule row), the decisive 15.4.1 offsets, the Event Summoner
  tool, the full event atlas cross-links, and the approaches already proven DEAD.
  Earlier-version offsets in a changelog.
metadata:
  status: active
  valid_as_of: 2026-08-27
permalink: dqverify-repo-20261013/skills/battlecats-event-unlock/skill
---

# Battle Cats — Special / Event Stage Unlock

Reverse-engineering on-demand unlock/visibility for special, event, and tower
(Heavenly Tower) stages in Battle Cats **EN v15.4.1** (`jp.co.ponos.battlecatsen`,
clientVersion `150400`, app_version_code `1504010`), x86_64 `lib/x86_64/libnative-lib.so`,
on rooted BlueStacks Pie64 + frida-server, ADB `127.0.0.1:5555`. Module imagebase 0x0,
so **RVA == file offset** (unchanged from 15.3).

- **Binary identity (15.4.1):** native build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`;
  `so_sha256 = 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`
  (so_size 12 666 808). All offsets below are `bindiff`-verified against this exact
  on-device image (confirm-basis: `so_sha256` byte-matched the running BC pid 3807 on
  2026-06-16 — the running binary IS the manifest-pinned binary, so every static offset is
  correct by construction). Pinned manifest: `tools/offsets/en-15.4.1.json`.
- **getGlobal fingerprint (15.4.1):** `488d0599fe5b00c3` (AOB `48 8D 05 ?? ?? ?? ?? C3`,
  `lea_ret`; 13502 call-xrefs; ptr table `0xC1D7A0`).
- **Older versions:** 15.3.0 offsets/identity preserved in the **Version history / changelog**
  at the end of this file (do not delete — reference for cross-version RE).

## The one rule — read this first

A tile **RENDERS only if BOTH** of these hold:

1. **Tree admission** — the mapid is admitted to the active-event-window RB-tree
   (game_state + 11736 = +0x2DD8; read side `sub_5F8AC0`), which is built **ONCE at launch**
   by the calendar-rebuild `sub_525AB0`.
2. **Valid schedule row** — a valid `event_0` (sale.tsv) row covers "now" for that mapid.

Neither half alone works:
- **Row alone** → record loads + passes the activeness gate, but **0 tiles render**
  (mapid not in the tree).
- **Admit alone** → **CRASHES** (null-deref: tree entry with no row body to draw).
- **Time-travel** supplies both, but trips HGT / Recovery Mode → rejected (see below).

You must satisfy BOTH halves, with no clock change and no save edit.

## PROVEN DEAD — do NOT retry these (rigid; do not adapt them away)

These were each tried and failed on this exact stack. Re-attempting them is wasted work.

- **Forcing the render/display gate `sub_817020` TRUE** (the date/activeness gate, callers
  near `0x7f5d17` / `0x81bb53` in 15.3 numbering). Too late in the pipeline to create a tree
  entry. Tower ids 7000–7010 were 11/11 in the candidate map yet **0/11 rendered** when forced
  this way. The old stage-unlock trainer does this — it does NOT surface tree-absent events.
- **Forcing an OFF-WINDOW `sale.tsv` row + forcing `sub_817020`.** A forced/off-calendar row
  that is made "active" by hammering the display gate does NOT create a tree entry (Tower 7xxx
  routes to its own container `[r13+0x374388]`; gauntlet/all-day fall through). This is the
  scope of the original "towers can't be injected" finding — see the correction in WHAT WORKS:
  a **calendar-active always-on sentinel** row is a *different* thing and DOES work.
- **Always-on `sale.tsv` row ALONE for a mapid that routes to a foreign container** (no tree
  admission for gauntlet/dojo/colosseum bands). A 470-row always-on patch rendered **0 new
  tiles** for those. For Special-Stages-tree bands a sentinel row IS sufficient (see below) —
  the dead case is the foreign-container bands, which need the patch.
- **Blanket-forcing the rebuild call site `0x5292e4`-class** → **CRASHES** BC. Any injection
  must be scoped and structurally valid (one mapid, with a backing row).
- **Forced tree-admission ALONE (no valid row body)** → **CRASHES** on the menu rebuild
  (null-deref on missing row data). Admission must be backed by a row.
- **Naive time-skipping / OS clock jump / MITM `getTime` + `.dat` cache-clear.**
  Trips BC **Recovery Mode** (which HIDES events) and can cascade into the
  **99-day half-XP HGT penalty**. NEVER do MITM, cache-clear, or time-endpoint
  manipulation on this stack. (It was the *delivery*, not the data, that did the damage.)

## WHAT WORKS

**Primary path (verified live 2026-05-26 on 15.3 — data-only, no Frida, no `.so` patch;
data path unchanged on 15.4.x):**

- **Patch `event_0`** with an always-on row (`20300101` end-date sentinel,
  `20160101` start, `min_ver 50700`) for the target mapid(s). A calendar-active row makes
  the admission filter `sub_819E20` return true *naturally* during the launch-time
  tree-populate loop → the mapid enters the calendar tree → the Special-Stages menu
  rebuild draws the tile → entry gates allow play. **Neither a Frida hook nor a static
  `.so` patch is required** for any mapid with `local_assets=Y` **that routes to the
  Special-Stages tree** (towers, Legend Quest, Challenge Battle, Behemoth Culling, Grand
  Abyss, Way of the Cat, cyclones, seasonal/anniversary/collab-EN). Persistent, reversible,
  survives relaunch.
- **TOWERS ARE DATA-ONLY ACTIVATABLE** (correction to the old "towers PROVEN DEAD" note):
  Heavenly Tower 7000 rendered + was **PLAYED on an unmodified `.so`** via a calendar-active
  sentinel row (2026-05-26 [VALIDATED]). The earlier "tower 7xxx can't be injected via
  sale.tsv" finding was scoped to **off-window forced rows + forcing `sub_817020`** — it does
  NOT apply to an always-on sentinel row whose window covers now. **7011 Fascinating Fallen
  Tower content IS on EN** (stageID 7011 / `MapStageDataV_011.csv`); it just lacks an event_0
  row in either file → append one sentinel row to activate.

**Reset-risk caveat (the "Golden Tower bug" class):** re-admitting a **repeatable** stage as
a fresh always-on window presents it as uncleared → **clear-progress / treasure RESETS**
(reset is keyed to the event-window *instance* for repeatables — helpers
`sub_4DF750`/`sub_4DF8B0`/`sub_4DFA10`). HIGHEST risk: **Golden Tower 7010** (treasure re-roll
= the named bug). Other reset_risk=Y: all Towers 7000–7011, Legend Quest 16000, Grand Abyss
33000, Challenge Battle 12000, all Cyclones, all Gauntlets, Colosseum 36xxx, all Collabs.
**Behemoth Culling 31000–31002 is the ONE reset-SAFE repeatable** (it keeps genuine daily
stock rows, not sentinel-only injection — natural daily cadence, nothing to lose).
**Mitigation:** prefer a **scoped Frida `sub_819E20→1`** admit (reverses on detach, never
rewrites the persistent window) over a permanent `20300101` row when in-progress state
matters; or snapshot the save (BCSFE, read-only) FIRST.

**Edge case — scoped Frida admission OR static `.so` patches** (when a mapid routes to a
foreign container — gauntlet 24xxx / dojo / colosseum 36xxx — so a row alone doesn't admit;
when you want a mapid admitted *without* making its row calendar-active, e.g. RE/diagnostics;
or when unlock should persist as part of an APK build rather than a data file):

- Force `sub_819E20(rec, now)` @ **`0x823B00`** → return **1**, at the populate-loop call site
  inside `sub_525AB0` @ **`0x52CE20`**, **scoped to one target mapid only** (mapid is read at
  `rec+0x5C` / `rec+0x60`). Fires during the Special Stages menu rebuild — attach and navigate.
- Supporting offsets (15.4.1; use only as needed, scoped):
  - `sub_5F8DF0` @ **`0x600D70`** — id-band fallback gate (GATE-C; true for 900–999 / 35000–35045).
  - Render/activeness bridge + tree-insert helpers: re-derive on 15.4 if needed (the 15.3
    `sub_5F8A10`/`sub_81BAF0` numbers no longer apply; not in the 15.4.1 manifest — host-fn
    delta pass).
  - Entry gates **to play** the stage: `sub_8A3350` @ **`0x8AD600`** → 0 (entry-status),
    `sub_8A3520` @ **`0x8AD7D0`** → 1 (in-window predicate).
- **HARD BOUNDARY:** if a mapid has no local StageData / assets on-device, **no hook makes
  it playable**. It needs a content bake (tbcml route, out of scope for the hook approach).
  tbcml canonical home is **Codeberg** (`codeberg.org/fieryhenry/tbcml`, source install) — the
  GitHub repo is ARCHIVED and PyPI 1.1.0 is stale (2023); do not fetch from either.
  Forcing a tile for a mapid with absent content crashes on tile-build. For **collabs**,
  `local_assets=Y` is metadata only — retired (旧) collab art can be GC'd → **crash on icon
  draw if forced**; gate on EN-named + non-旧 + all-on-covered.
- **General lesson:** single-function Frida hooks are **reliable** here — the working
  stage-progression trainer proves it. The historical failure was *conceptual* (missing
  the data + admission dual requirement), not a hooking-skill gap. Do not overcomplicate
  with multi-hook forging schemes.

Static byte stubs (rebuilt-APK route, all HGT-safe — lie about gate answers only, never time):
`B8 01 00 00 00 C3` = `mov eax,1; ret` (for `sub_819E20` @ `0x823B00`, `sub_5F8DF0` @
`0x600D70`, `sub_8A3520` @ `0x8AD7D0`); `31 C0 C3` = `xor eax,eax; ret` (for `sub_8A3350` @
`0x8AD600`). The live preference is the scoped Frida hook, which forces these per-target and
reverses on detach.

## Trainer self-verify + GUI (15.4.x)

The trainer now **self-verifies the binary identity at launch** before writing any memory:
`tools/offsets/bc_self_verify.py` hashes the on-device `.so` (resolved from `/proc/<pid>/maps`
for the attached PID — TOCTOU-bound) against the manifest pin (`en-15.4.1.json` `so_sha256`).
**MATCH → offsets are correct by construction → writes enabled; anything else fails closed.**
Re-derives the verdict on any reconnect / PID change. The PySide6 trainer GUI ships as a
self-contained `.exe`. The legacy stage-unlock path is unchanged: the **data-only event_0
patch** + the **`enable-combined` Frida hook** (offsets bumped to the 15.4.x values above).

## Event atlas (the full per-stage knowledge base — cross-link, do not duplicate)

The complete activation atlas for EVERY non-regular stage lives in five read-only
game-knowledge docs (synthesized 2026-06-16, EN 15.3.0 content authority / 15.4.1 game-data):

- `D:\ReverseTools\Android\battlecats-toolkit\docs\game-knowledge\BC-EVENT-ARCHITECTURE.md`
  — **activation-model authority**: dual-dependency model, the event_0 row schema, the
  band→category map, the master table of ALL specials, the **activation matrix**
  (DATA-ONLY / NEEDS-TREE-ADMIT-patch / NEEDS-BAKE), and the reset-risk class.
- `BC-STAGE-COMPENDIUM.md` — living 8-dimension atlas (cross-region asset matrix, cat-linkage,
  semi-story/progressive chains, version history, critic gap-closures).
- `BC-EVENT-GLOSSARY.md` — every event family named + defined.
- `BC-EVENT-ROSTER.generated.tsv` — per-stage name roster (647 rows; regenerate on version bump).
- `BC-DATA-FORMATS.md` — field-by-field decode of every cited data file (event_0, MapStageData,
  Map_option, All_day_event, ...).

Key structural facts these docs add (fold into any unlock plan):
- **THREE mapid namespaces**, not two: content (`Map_option` stageID), schedule (`event_0`
  MapStageData mapid), and a **runtime 5xxxx** space (`stagedatamgr_dump.json` — 50321/50732/
  51035 + gauntlet 5100/5110).
- **Six schedule-only artifact bands** (8xxx / 9089–9682 / 15xxx / 17xxx / 26xxx / 28xxx) carry
  well-formed live PONOS rows but have **ZERO EN content** → a row cannot fabricate a tile
  without content (these need a bake or are non-events). 9xxx (74 ids) is the largest collab hole.
- **event_0 row-schema correction:** field 7 = `n_slot_groups` (NOT "map_count"); structure is
  `8-field header → N slot-groups → [map_count, mapid × map_count, trailing_flag?]`. The
  multi-mapid carrier-row template (Way of the Cat 37000–37011 = ONE row, `map_count=12`,
  `min_ver 140000`) is now documented. Full decode in `BC-DATA-FORMATS.md` §1.

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
- **Identity self-verify:** `tools/offsets/bc_self_verify.py` (hashes on-device `.so` vs the
  `en-15.4.1.json` pin; MATCH → writes safe; read-only, fail-closed).
- **BCSFE time-fix** (clears a NEW drift penalty — not an active recovery countdown):
  `BCSFE-Python` → `Fixes.fix_time_errors`.

## Workflow (the actionable core)

**For "play any event on demand" — DATA-ONLY (no Frida needed; Special-Stages-tree bands):**

1. **Resolve target.** `bc_event_index.py resolve <name>` → mapid; confirm
   `local_assets == true`. If false, STOP — needs a content bake, no patch helps. Check the
   activation matrix (`BC-EVENT-ARCHITECTURE.md` §4): if it routes to a foreign container
   (gauntlet/dojo/colosseum), the data-only path won't admit it — use the Frida/patch edge case.
2. **Build patched event_0** (or use a bundled all-on file, dojo excluded):
   `python dat-cache-decode/build_event0_allon.py`
3. **HGT-safe in-place push** (round-trip check + force-stop happen for you):
   `python dat-cache-decode/push_event0.py push <plain.tsv>`
4. **Launch BC. PASS** = tile renders, stage plays, NO Frida, NO HGT/Recovery, **no
   save-timestamp change**, persists across relaunches.
5. **Revert to stock anytime:** `python dat-cache-decode/push_event0.py revert`
   (restores from bundled `event0_backup/ev0_binpull.dat`).
6. **Repeatable + want to keep progress?** Snapshot the save (BCSFE, read-only) first, or use
   the scoped Frida admit instead of a permanent row (see reset-risk caveat above).

**Edge case — Frida scoped admit (foreign-container bands / off-calendar admission / RE):**

a. **Read-only probe** (stock boot). `bc_event_summon.py probe` → confirm the mapid
   is ABSENT from the tree.
b. **Scoped admit.** `summon --mapid <id> --keep-alive`, then navigate to Special
   Stages to trigger the rebuild; `treedump` to confirm admission. Detach restores
   stock.

**Discipline:** single actor, serial for any live Frida / ADB step — the emulator is
a shared resource. Subagents do code/docs only; they never touch the live game, ADB,
clock, or save.

## Reference

Full detail lives in:
- `D:\ReverseTools\Android\battlecats-toolkit\docs\EVENT-UNLOCK-PLAYBOOK.md`
- The five `docs\game-knowledge\BC-EVENT-*` docs (event atlas, above).
- `docs\research\2026-05-25-DEFINITIVE-TRUTH.md`
- `docs\event-summoner-design.md`
- `dat-cache-decode\STARTUP_FILTER_RE.md`
- `tools\offsets\en-15.4.1.json` (the pinned offset manifest) + `bc_self_verify.py`.

---

## Version history / changelog

Offsets are pinned per game version in `tools/offsets/en-<ver>.json`. Earlier versions are
kept here packed for cross-version RE reference (NOT scraped). When BC updates, re-derive via
`bc_self_verify.py` + a bindiff pass and add a new subsection — do not overwrite this history.

### 15.4.0 / 15.4.1 (clientVersion 150400, app_version_code 1504010) — CURRENT

- **Identity:** native build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`;
  `so_sha256 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`; so_size
  12 666 808; getGlobal fingerprint `488d0599fe5b00c3`. Verified live 2026-06-16 (BC pid 3807).
- **Offset drift vs 15.3.0** (all bindiff-verified against `en-15.4.1.json`):

  | symbol | 15.3.0 RVA | 15.4.1 RVA | drift | note |
  |---|---|---|---|---|
  | `getGlobal` | `0x653C80` | `0x65D900` | **+0x9C80** | NOT the +0x53A0 wallet cluster — its own drift |
  | `getCash` | `0x37C170` | `0x381510` | +0x53A0 | wallet table |
  | `setCash` | — | `0x381550` | +0x53A0 | — |
  | `getCap` | — | `0x3815D0` | +0x53A0 | wallet base 0x468→0x450 |
  | `sub_819E20` (admission filter) | `0x819E20` | `0x823B00` | **+0x9CE0** | field 0xfd8→0xfc8 |
  | `sub_817020` (activeness gate) | `0x817020` | `0x820D00` | **+0x9CE0** | — |
  | `sub_5F8DF0` (id-band GATE-C) | `0x5F8DF0` | `0x600D70` | +0x7F80 | field 0x2ea8→0x2e98; band 0x88B8 kept |
  | `sub_8A3350` (entry-status →0) | `0x8A3350` | `0x8AD600` | **+0xA2B0** | masks 0x188000/0x402001 kept |
  | `sub_8A3520` (in-window →1) | `0x8A3520` | `0x8AD7D0` | +0xA2B0 | — |
  | `sub_525AB0` (calendar rebuild) | `0x525AB0` | `0x52CE20` | +0x7370 | r2 body-anchored, MED-HIGH conf |
  | `sub_4F1E20` (guerrilla getter) | `0x4F1E20` | `0x4F9060` | +0x7240 | tiny-leaf byte-identical |
  | `SPEED_OFF` (game_state field) | `0x317B30`* | `0x31D7A0` | — | reader site 0x4B4DE2→0x4BB392 |
  | `GLOBAL_WALLET_OFFSET` | — | `0x23E0` | — | moved DOWN -0x10 (IDA-resolved) |
  | `INBATTLE_OFF` | — | `0x37D9F8` | — | `mov [rbx+0x37D9F8],1` |
  | `OUTBREAK_OFFSET` | — | `0x321F80` | — | zombie_event_remaining_time double |

  *15.3 `SPEED_OFF` shown for orientation; the load-bearing event-unlock offsets are the
  `sub_*` rows. The three drift bands are **+0x9CE0** (admission/activeness), **+0xA2B0**
  (entry gates), **+0x53A0** (getGlobal / wallet cluster); `sub_5F8DF0` (+0x7F80) and
  `sub_525AB0` (+0x7370) drift independently.

- **LIVE-ONLY (no static candidate — re-derive on device each session):** calendar tree
  `gs+0x2DD8`, guerrilla array `gs+0x11B8`, Aku block, the render/forge/list-builder code
  sites (`RA_RENDERER` / `RA_FORGE` / `RA_LISTBUILDER`), and the outbreak Interceptor anchors —
  all null in the 15.4.1 manifest (feature-gated off / layout drifted; a wrong RA on the render
  path crashes). Use IDA host-fn delta pass when a feature is re-enabled.
- **What ALSO changed (non-offset):**
  - **Trainer self-verify** added (`bc_self_verify.py`) — launch-time identity hash gate;
    the PySide6 GUI ships as a self-contained `.exe`.
  - **Towers correction:** towers ARE data-only activatable via a calendar-active sentinel row
    (the old "PROVEN DEAD" entry was scoped to off-window forced rows + forcing `sub_817020`).
  - **7011 Fascinating Fallen Tower** content confirmed present on EN.
  - **THREE mapid namespaces** + **six schedule-only artifact bands** documented (event atlas).
  - **event_0 row-schema correction:** field 7 = `n_slot_groups`, not "map_count".
- **The data-only event_0 path is binary-version-INDEPENDENT** — it patches a data file, not
  the `.so`, so it carried over from 15.3 unchanged. Only the Frida-hook / static-patch RVAs
  needed the bump above.

### 15.3.0 (clientVersion 150300) — SUPERSEDED

- **Identity:** x86_64 `lib/x86_64/libnative-lib.so`, IDA imagebase `0x0` ⇒ RVA == file offset;
  `so_sha256 99bb6f36db1fc82a082f2a720c88325f9c146346fa0e0dbebae75205ab9eec7a`. Stack:
  BlueStacks Pie64 + Magisk/Kitsune + frida-server 17.9.1, ADB `127.0.0.1:5555`.
- **Offsets (15.3.0; RVA == file offset)** — superseded by the 15.4.1 table above:

  | Address | Symbol | Role |
  |---|---|---|
  | `0x819E20` | `sub_819E20` | **PRIMARY LEVER** — startup tree-populate admission filter (call site `0x52653f` in `sub_525AB0`) |
  | `0x817020` | `sub_817020` | display/activeness gate (date+ver+platform+slots); callers `0x7f5d17`, `0x81bb53`, rebuild `0x5292e4` — **PROVEN DEAD** as a lever |
  | `0x5F8DF0` | `sub_5F8DF0` | id-band wall (GATE-C): true for 900–999 / 35000–35045 |
  | `0x4D2430` | `sub_4D2430` | main-chapter catalog (ids 1..721); −1 for all specials (GATE-C other half) |
  | `0x5F8AC0` | `sub_5F8AC0` | calendar-tree enable query (Gate 1, read side) |
  | `0x5F8A10` | `sub_5F8A10` | calendar-tree insert / set-enable (Map A, write side) |
  | `0x81BAF0` | `sub_81BAF0` | sale↔mapid activeness bridge (row provides date window) |
  | `0x7F52D0` | `sub_7F52D0` | unified special/event menu builder (the renderer) |
  | `0x525AB0` | `sub_525AB0` | per-day recalc: builds tree + HGT gate + calls builder |
  | `0x527270` | `sub_527270` | menu parent |
  | `0x8A3350` | `sub_8A3350` | stage-entry status gate (`→0` to allow entry) |
  | `0x8A3520` | `sub_8A3520` | in-window entry predicate (`→1` to allow entry) |
  | `0x7F6EAF` | (row-skip branch) | builder skip of completed/progress-gated rows (reversible 6-byte NOP) |

- **15.3 facts that changed in 15.4:** all `sub_*` RVAs drifted (+0x9CE0 / +0xA2B0 / +0x7F80 /
  +0x7370 — see 15.4.1 table); the towers "PROVEN DEAD" framing was corrected (towers ARE
  data-only activatable via a calendar-active sentinel row); `sub_5F8A10` / `sub_81BAF0` /
  `sub_4D2430` / `sub_5F8AC0` / `sub_7F52D0` / `sub_527270` are NOT in the 15.4.1 pinned
  manifest (re-derive via host-fn delta if a hook needs them). The dual-dependency model,
  the event_0 crypto (`89a0f99078419c28`), the `20300101` sentinel, and the HGT-safe in-place
  delivery recipe are all UNCHANGED.