---
title: EVENT-UNLOCK-PLAYBOOK
type: note
permalink: dqverify-repo-20261013/skills/battlecats-event-unlock/event-unlock-playbook
---

# Battle Cats EN 15.4.1 — Event-Unlock Playbook (DEFINITIVE)

**The one file to read.** Single authoritative reference + index for making special/event
stages visible and playable on demand on the live (rooted BlueStacks) client. It consolidates
weeks of scattered RE into the one decisive truth, the offsets that matter, the approaches
already proven dead, the Event Summoner tool, and an honest confirmed-vs-pending status.

- **Target:** Battle Cats EN **v15.4.1** (`jp.co.ponos.battlecatsen`, clientVersion `150400`,
  app_version_code `1504010`), x86_64 `lib/x86_64/libnative-lib.so`, IDA imagebase `0x0`
  ⇒ **RVA == file offset** (unchanged from 15.3).
  Binary `so_sha256 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`
  (so_size 12 666 808); native build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`;
  getGlobal fingerprint `488d0599fe5b00c3`. Pinned manifest: `tools/offsets/en-15.4.1.json`.
  All offsets `bindiff`-verified against this exact on-device image (the running BC pid 3807
  binary byte-matched the manifest pin live on 2026-06-16, so every static offset is correct
  by construction). **Older versions: see the Version history / changelog (§12) — the 15.3.0
  offsets are preserved there, not deleted.**
- **Stack:** BlueStacks Pie64 + Magisk/Kitsune + frida-server 17.9.1, ADB `127.0.0.1:5555`.
- **Date:** 2026-06-16 (15.4.1 bump); core RE dated 2026-05-25.
- **Confidence tags:** **[VALIDATED]** byte-exact round-trip and/or in-game visual; **[VERIFIED-IDA]**
  read from the IDB address-exact; **[VERIFIED-FP]** operator's controlled on-device run;
  **[BINDIFF]** offset confirmed by binary-identity match (the running `.so` IS the manifest
  pin); **[PENDING]** not yet visually confirmed.

---

## 1. TL;DR — the decisive truth + status

A special/event tile **RENDERS only if BOTH hold at once:**

1. **Tree admission** — the mapid is in the active-event-window RB-tree (the "calendar tree",
   `game_state + 11736` = `+0x2DD8`, read side `sub_5F8AC0`). The tree is populated **once at
   launch** inside the calendar-rebuild `sub_525AB0` @ **`0x52CE20`**, which admits a record
   only if the startup filter `sub_819E20(rec, now)` @ **`0x823B00`** returns true (15.3 call
   site was `0x52653f`; re-derive the 15.4 call site inside `sub_525AB0`). **[VERIFIED-IDA / BINDIFF]**
2. **Valid schedule row** — a `sale.tsv` (event_0, the 0x80 container) row whose date window
   covers "now" lists that mapid, so the activeness gate `sub_817020` @ **`0x820D00`** reports
   it active. **[VERIFIED-IDA / BINDIFF]**

**Neither alone works.** Row-alone: file loads/parses fully but the mapid never enters the
tree → 0 tiles render, no crash (a 470-row always-on patch rendered 0 new tiles, **[VALIDATED]**).
Tree-admission-alone (no row body): crashes on the Special Stages menu rebuild (null-deref on
missing row data). Time-travel "works" only because it naturally supplies BOTH — but it trips
HGT/Recovery + a 99-day half-XP penalty, so it is rejected.

**Status (verified live 2026-05-26 on 15.3; data path unchanged on 15.4.x):** the **data-only
path is the primary recipe** — Heavenly Tower (mapid 7000) was patched into event_0 with the
`20300101` sentinel and **rendered + played in-game** against an **unmodified
`libnative-lib.so`** on the live BlueStacks client **[VALIDATED]**. A valid (calendar-active)
row makes `sub_819E20` return true *naturally* → tree admission falls out for free →
**neither a Frida hook nor a static `.so` patch is required** for any mapid with
`local_assets=true` **that routes to the Special-Stages tree**. The data-only path patches a
data file, not the `.so`, so it is **binary-version-independent** and carried over to 15.4.x
unchanged. The scoped `sub_819E20→1` admit hook (Event Summoner) AND the four static unlock
patches (`sub_819E20→1`, `sub_5F8DF0→1`, `sub_8A3350→0`, `sub_8A3520→1`, at the **15.4.1**
RVAs `0x823B00` / `0x600D70` / `0x8AD600` / `0x8AD7D0`) are **belt-and-suspenders** for edge
cases — foreign-container bands (gauntlet/dojo/colosseum) that a row alone can't admit,
off-calendar admission, a mapid you specifically want admitted *without* making its row
calendar-active, or RE diagnostics. Rarely needed once you can author any row you like.

---

## 2. Architecture — the render pipeline and the dual dependency

Menu path: **`sub_527270` → `sub_525AB0` (15.4.1 `0x52CE20`) → `sub_7F52D0`**.
*(15.3 RVAs below for `sub_527270`/`sub_7F52D0`/the call sites; on 15.4.1 only `sub_525AB0`
@ `0x52CE20` is pinned in the manifest — re-derive the menu-parent/builder + the inner call
sites via an IDA host-fn delta pass when a hook actually needs them.)*

- `sub_527270` (15.3 `0x527270`) — menu parent / refresh entry.
- `sub_525AB0` (15.3 `0x525AB0`, **15.4.1 `0x52CE20`**, size `0x1081`) — per-day/session
  recalc. Two jobs in one function: (a) **(re)builds the calendar tree** in the tree-populate
  loop (`while(1)`, 15.3 `0x5262e9`), and (b) runs the **HGT drift gate** (separate code, §7 —
  do not touch). It ends by calling the menu builder `sub_7F52D0`. **[VERIFIED-IDA / BINDIFF]**
- `sub_7F52D0` (15.3 `0x7F52D0`, size `0x39D0`) — the **single unified builder** for every
  special/event section (Special Stages, Tower, Gauntlet, Behemoth, Cyclone, Catfruit, and the
  Catclaw Dojo — the Dojo is the MapID-11000 branch, not a separate builder). **[VERIFIED-IDA]**

**The calendar tree** (`game_state + 11736` = `+0x2DD8`, root at `+0x20`) holds two parallel
ordered maps keyed on mapid (`node+0x1C`): an **enable map** (Gate 1; write `sub_5F8A10`, read
`sub_5F8AC0` → enable byte at `node+0x20`) and a state map (write `sub_5F8B00`, read
`sub_5F8BB0`). A tile is visible iff its enable byte == 1. The tree is empty until `sub_525AB0`
populates it. (15.3 helper RVAs; the tree-offset `+0x2DD8` is LIVE-ONLY in 15.4 — re-derive on
device. The insert/read helpers `sub_5F8A10`/`sub_5F8AC0` are NOT in the 15.4.1 manifest →
host-fn delta pass.) **[VERIFIED-IDA]**

**The tree-populate gate inside `sub_525AB0`** (15.4.1 `0x52CE20`) — per FilterData record `rec`
(addresses are 15.3 IDA labels; the admission filter and GATE-C are now `sub_819E20` @ `0x823B00`
and `sub_5F8DF0` @ `0x600D70`):

```c
if (!sub_819E20(rec, now)) goto SKIP;          // 15.3 site 0x52653f  THE admission filter (15.4.1 sub @ 0x823B00)
mapid = sub_81A750(rec);                        // rec+0x5C  tree key
gate_mapid = sub_81A760(rec);                   // rec+0x60  catalog/id-band key
if (sub_4D2430(gate_mapid)==-1 && !sub_5F8DF0(gate_mapid)) goto SKIP;   // GATE-C (sub_5F8DF0 15.4.1 @ 0x600D70)
sub_5F8A10(tree, mapid, 1);                     // INSERT enable=1  -> tile can render
```

So a mapid is admitted iff `sub_819E20` passes **AND** GATE-C passes (main-chapter catalog
`sub_4D2430` returns ≥0, OR id-band `sub_5F8DF0` true: 900–999 / 35000–35045 — band `0x88B8`
preserved across the version bump). The stock ~223-event ceiling exists because only pre-seeded
mapids pass both unaided. **[VERIFIED-IDA / BINDIFF]**

**The schedule half (sale.tsv body):** after the FilterData prefix, a `sale.tsv` row is an
`8-field header → N slot-groups → trailing map block` (field 7 = `n_slot_groups`, **NOT**
"map_count" — corrected; full decode in `BC-DATA-FORMATS.md` §1). The trailing map block is
`[map_count, mapid × map_count, trailing_flag?]` read into the record's `std::vector<int>` at
`+0x60` (begin `+0x60`, end `+0x68`), with the optional trailing int at `+0x78` (always `0`).
There is **no type-letter vector** on the sale row. The activeness gate `sub_817020` @
**`0x820D00`** (15.4.1) runs per row and reports the mapid active iff some active row lists it.
The row's only job is to make the mapid **active-now**; it does not create a tree node.
**[VERIFIED-IDA / BINDIFF]**

> Record-type trap: `+0x60` means two different things. On the **sale (0x80)** record it is a
> `std::vector<int>` of mapids (read by `sub_8186C0`/`sub_8186D0`). On the **StageData (0xB0)**
> record it is a scalar mapid (read by `sub_81A760`). Earlier iterations (ITER13/14) read the
> 0xB0 plane and mislabelled it as the sale row — the source of much prior confusion. See
> `SALE_ROW_BODY_SCHEMA_RE.md`.

---

## 3. PROVEN DEAD (do not re-litigate)

| Approach | Why it's dead | Evidence |
|---|---|---|
| **Force the display gate `sub_817020` (15.4.1 `0x820D00`; or its 15.3 callers `0x81bb53`/`0x7f5d17`)** | Display gate fires too late to create a tree entry. The old trainer forced it; tower ids 7000–7010 were 11/11 present in the candidate map yet 0/11 reached a rendered row. | **[VERIFIED-FP]** |
| **OFF-WINDOW / forced `sale.tsv` row + forcing `sub_817020`** for a foreign-container band (Tower 7xxx, Gauntlet 24xxx, all-day) | A forced/off-calendar row made "active" by hammering the display gate does NOT create a tree entry — Tower routes to its own container `[r13+0x374388]`; gauntlet/all-day fall through. **This is the precise scope of the old "towers can't be injected" finding.** A *calendar-active always-on sentinel* row is a DIFFERENT case → see §4 CORRECTION (towers ARE data-only activatable). | **[VERIFIED-IDA]** |
| **Always-on `sale.tsv` row ALONE for a FOREIGN-CONTAINER band (gauntlet/dojo/colosseum)** | File loads, rows parse + pass activeness, but those mapids never enter the Special-Stages calendar tree → 0 new tiles (no crash). A 470-row always-on patch produced 0 new tiles **for those bands**. (For Special-Stages-tree bands a sentinel row IS sufficient — that is the WHAT-WORKS path, not a dead one.) | **[VALIDATED]** |
| **Forced tree-admission ALONE (no valid row body)** | Crashes BC on the Special Stages menu rebuild — null-deref on missing row body data. Any admission injection must be scoped + structurally backed by a row. | **[VERIFIED-FP]** |
| **Blanket-force the rebuild call site (15.3 `0x5292e4`)** | Crashes BC. The Special-Stages candidate vector is pre-built upstream there; forcing the whole set there is fatal. Any injection must be scoped/structurally valid. | **[VERIFIED-FP]** |
| **Naive time-travel / clock set / forward save-date** | Supplies BOTH halves naturally, but trips HGT/Recovery (hides events) and the half-XP penalty. | **[VALIDATED]** §7 |
| **Full MITM proxy (intercept all PONOS traffic, clear .dat cache)** | Corrupts the client's time/notices path → HGT recovery + a 99-day half-XP penalty, confirmed in-game. NOT the same as a clean clock set; it was the *delivery* that did the damage. | **[VALIDATED]** §7 |
| **Runtime forge of the FilterData vector (DEC-001)** | Reallocs the vector without updating the global `qword_108C5A8` + 9 cached readers → use-after-free crash on the next rebuild. Even fixed, it still hits the same gates. | **[VERIFIED-FP]** |
| **Inject Gauntlet(24xxx)/all-day ids via a row ALONE (no patch)** | Not registered in the Special-Stages tree (gauntlet/all-day fall through). A row cannot fabricate a tree entry for them — they need the static patch (`sub_819E20→1` + `sub_5F8DF0→1`) or scoped Frida summon. (Tower 7xxx is NO LONGER in this dead list — corrected, see §4.) | **[VERIFIED-IDA]** |
| **Inject dojo ids (11000s) / route a row to colosseum (36xxx) via `sale.tsv`** | Mis-binds them into the Special-Stages container and desyncs the list. Dojo rides a separate ranking channel; colosseum a separate Legend-Quest channel. Builder excludes the dojo family by default. | **[VERIFIED-IDA]** |

> **The historical miss:** sessions chased the "render gate is a sale.tsv body-schema problem"
> theory for weeks. It is not. The body is trivial and identical between rendering and
> non-rendering rows; the gate is a **runtime registration** problem (tree admission). Forcing
> the wrong (display) function or supplying only one of the two halves was the recurring error.
>
> **TOWER CORRECTION (2026-06-16):** the prior blanket "Tower 7xxx cannot be injected via
> sale.tsv — routes to `[r13+0x374388]`" applied ONLY to off-window forced rows + forcing
> `sub_817020`. A **calendar-active `20300101` sentinel** row makes `sub_819E20` pass naturally
> → 7000 admitted at launch → Heavenly Tower 7000 **rendered + PLAYED** on an unmodified `.so`
> (2026-05-26). **Towers ARE data-only activatable.** See `BC-EVENT-ARCHITECTURE.md` §0/§6.

---

## 4. What WORKS — scoped `sub_819E20→1` admission + a valid event_0 row

The lever is the **startup admission filter** `sub_819E20`, scoped to one target mapid, paired
with a valid always-on `sale.tsv` row for that mapid.

- `sub_819E20(rec, now)` @ **`0x823B00`** (15.4.1) = (content prerequisites) **AND** the pure
  date-window gate `sub_817020(rec,1,0,now)` @ **`0x820D00`**. Forcing it `→1` neutralizes both
  the off-window exclusion and the prerequisite lock in one stroke, and it is **scoped to
  event/calendar surfaces only** (8 callers, all event-menu/calendar; NOT the sales/gacha/reward
  server-validated paths). To admit one off-window record, force `→1` only when the record's
  mapid (read at `rec+0x5C` / `rec+0x60`) matches the target. **[VERIFIED-IDA / BINDIFF]**
- `sub_819E20` fires during the Special Stages menu rebuild, so **attach + navigate triggers it**
  — a probe that never opens Special Stages sees 0 calls.
- HARD BOUNDARY: if a mapid has no local StageData/assets on device, no hook makes it playable —
  that needs a content bake (tbcml, out of scope; canonical home is Codeberg
  `codeberg.org/fieryhenry/tbcml` via source install — GitHub repo ARCHIVED, PyPI 1.1.0 stale).
  Heavenly Tower 7000 has local assets, which is why it is the chosen first target.

### Offsets table (module `libnative-lib.so`, RVA == file offset)

**The four load-bearing levers are bindiff-pinned for 15.4.1** (from `tools/offsets/en-15.4.1.json`).
Helpers that have no 15.4.1 manifest candidate are marked *re-derive* — their 15.3 RVA no longer
applies; run an IDA host-fn delta pass before hooking them. (Drift bands: `sub_819E20`/`sub_817020`
**+0x9CE0**; `sub_8A3350`/`sub_8A3520` **+0xA2B0**; `sub_5F8DF0` +0x7F80; `sub_525AB0` +0x7370.)

| 15.4.1 RVA | 15.3.0 RVA | Symbol | Role | Action to use it |
|---|---|---|---|---|
| **`0x823B00`** | `0x819E20` | `sub_819E20` | **PRIMARY LEVER** — startup tree-populate admission filter (called from `sub_525AB0`; 15.3 site `0x52653f` — re-derive 15.4 site) | scoped `→1` for target mapid only |
| **`0x820D00`** | `0x817020` | `sub_817020` | DISPLAY/activeness gate (date+ver+platform+slots) | leave intact — too late / too broad; **PROVEN DEAD** as the lever |
| **`0x600D70`** | `0x5F8DF0` | `sub_5F8DF0` | id-band wall (GATE-C): true for 900–999 / 35000–35045 (band `0x88B8` kept) | scoped fallback `→1` to lift the band ceiling |
| **`0x52CE20`** | `0x525AB0` | `sub_525AB0` | per-day recalc: builds tree + HGT gate + calls builder | (host of the filter loop) |
| **`0x8AD600`** | `0x8A3350` | `sub_8A3350` | stage-entry status gate (masks `0x188000`/`0x402001` kept) | `→0` to allow entry |
| **`0x8AD7D0`** | `0x8A3520` | `sub_8A3520` | in-window entry predicate | `→1` to allow entry |
| *re-derive* | `0x4D2430` | `sub_4D2430` | main-chapter catalog (ids 1..721); −1 for all specials | read-only (GATE-C other half) |
| *re-derive* | `0x5F8AC0` | `sub_5F8AC0` | calendar-tree enable query (Gate 1, read side) | read-only / `treedump` |
| *re-derive* | `0x5F8A10` | `sub_5F8A10` | calendar-tree insert / set-enable (Map A, write side) | native insert helper |
| *re-derive* | `0x81BAF0` | `sub_81BAF0` | sale↔mapid activeness bridge (row provides date window) | render support |
| *re-derive* | `0x7F52D0` | `sub_7F52D0` | unified special/event menu builder | (the renderer) |
| *re-derive* | `0x527270` | `sub_527270` | menu parent | — |
| *re-derive* | `0x7F6EAF` | (row-skip branch) | builder skip of completed/progress-gated rows | reversible 6-byte NOP (only if rows get skipped) |

> Tree offset `game_state + 0x2DD8` is LIVE-ONLY in 15.4 (no static candidate — read on device).
> The render/forge/list-builder code sites and outbreak anchors are null in the 15.4.1 manifest
> (feature-gated off; a wrong RA on the render path crashes) — re-derive per feature.

Static byte stubs (rebuilt-APK route, all HGT-safe — lie about gate answers only, never time):
`B8 01 00 00 00 C3` = `mov eax,1; ret` (for `sub_819E20` @ `0x823B00`, `sub_5F8DF0` @ `0x600D70`,
`sub_8A3520` @ `0x8AD7D0`); `31 C0 C3` = `xor eax,eax; ret` (for `sub_8A3350` @ `0x8AD600`).
Use `bc_self_verify.py` to confirm the on-device `.so` matches the `en-15.4.1.json` pin BEFORE
patching (MATCH ⇒ offsets correct by construction). The live preference is the **scoped Frida
hook** (§6), which forces these per-target and reverses on detach.

---

## 5. event_0 crypto + the HGT-safe in-place patch

### 5.1 Crypto (SOLVED, byte-exact verified)

```
on_disk_dat = AES128_ECB( PKCS7(plaintext_tsv) )  ‖  md5_hex("battlecats" + cc + ciphertext)
key    = md5(b"battlecats").digest()[:8].hex().encode()   # b'89a0f99078419c28' (16 ASCII bytes, used directly)
cipher = AES-128 ECB, PKCS7 padding
footer = 32 ASCII hex = md5(("battlecats"+cc).encode() + ciphertext).hexdigest()
cc     = "en" for EN client
```

**[VALIDATED]** round-trips every device `.dat` byte-for-byte. Filenames are MD5 of the
**logical** name: `event_0` → `002a4b18244f32d7833fd81bc833b97f.dat` (= `sale.tsv`, the schedule),
`event_1` → `09b1058188348630d98a08e0f731f6bd.dat` (gatya), `event_2` → `408f66def075926baea9466e70504a3b.dat`
(item). The device file is **binary (LF)**; CRLF that appears via a text-mode `cat` pull is a
pull artifact — always pull/push binary-safe.

### 5.2 The always-on row sentinel

```
<start_yyyymmdd>  0  20300101  0  <min_ver>  999999  0  0  1  <mapid>
e.g.              20160101  0  20300101  0  50700  999999  0  0  1  7000
```

The permanent sentinel is **`20300101`** (NOT `20991231` — that was a prior wrong guess; the
device file uses `20300101` for 341/362 rows). `total_items=0` skips the FilterItem loop so the
row passes activeness on date alone; `map_count=1` then the mapid. **[VALIDATED]**

### 5.3 HGT-safe in-place delivery recipe (CRITICAL — never MITM / cache-clear / time-endpoint)

```
1. PULL binary-safe:   adb pull <files>/002a4b18244f32d7833fd81bc833b97f.dat   (never text-mode `cat`)
2. DECODE:             dat-cache-decode/push_event0.py  (or _event0_codec.py decrypt)
3. EDIT plaintext:     append/modify the always-on row (20300101 sentinel)
4. RE-ENCRYPT BINARY:  no CRLF, cc="en", fresh footer
5. PUSH IN PLACE:      su -c 'cat newfile > <files>/002a4b18244f32d7833fd81bc833b97f.dat'
                       then chown 10065, restorecon  (preserves inode/uid 10065/SELinux ctx;
                       do NOT delete-and-recreate)
6. force-stop BC first.   NO cache-clear, NO MITM, NO clock change, NO save-timestamp write.
```

**[VALIDATED]** the in-place patch **survives relaunch** — on-device md5 stayed stable across a
relaunch (BC does not re-download event_0 every boot; `f048fe88cdf14883f1a3a6d99e73d121` persisted).

Tooling (in `dat-cache-decode/`):
- `build_event0_allon.py` — builds an all-on event_0 from `--base` + `--catalog`, using the
  `20300101` sentinel + `allon_row` template; excludes the dojo family by default.
- `push_event0.py` — decode/encode/push with a mandatory round-trip check. **NOTE:** its `adb
  push` breaks with duplicate devices — push manually with `adb -s 127.0.0.1:5555`.
- `event0_backup/_event0_codec.py` — the verified codec (its docstring re-applies CRLF for
  *text-mode pulled* files; for **device** delivery use the binary, no-CRLF encrypt).

---

## 6. The Event Summoner tool (built 2026-05-25)

`D:\ReverseTools\Android\battlecats-toolkit\tools\frida-trainer\`

- **`bc_event_summon_agent.js`** — Frida agent. `rpc.exports`:
  - `install({ target_mapids:[int], mode:'probe'|'summon', entry_gates:bool, with_render_support:bool })`
  - `stats()` — `sub_819E20` admit/reject histogram + per-mapid `tree_admitted` flags
  - `treedump()` — read-only active-event-window tree snapshot (`game_state+11736`)
  - `uninstall()`
  - `probe` = observe-only (histogram + tree dump, forces nothing). `summon` = scoped
    `sub_819E20→1` for the target mapids only (+ optional render support + entry gates).
    Scoping is always on; an empty target list forces nothing. Fully reversible on detach.
- **`bc_event_index.py`** — decode event_0 →
  `list` / `resolve <name|mapid>` → `{name, mapid, windows, active_now, local_assets}`
  (e.g. `resolve 7000` = Heavenly Tower, `local_assets=true`).
- **`bc_event_summon.py`** — host CLI. Uses `device.attach(pid)` (NOT spawn — admission fires on
  menu rebuild, so attach + navigate is enough). Modes: `probe` / `summon --mapid <id> [--play]
  [--render-support] [--keep-alive]` / `stop-host`. Reports to `reports/event-summon/`. Reuses
  `bc_stage_unlock.py` transport/attach/report/lock plumbing.

Usage examples:

```powershell
$PY = 'D:\ReverseTools\Android\BCSFE-Python\.venv\Scripts\python.exe'
# 1. Read-only probe (prove the gate before forcing anything)
& $PY tools\frida-trainer\bc_event_index.py resolve 7000
& $PY tools\frida-trainer\bc_event_summon.py probe
# 2. Scoped admission of one mapid (no entry gates, no render support yet)
& $PY tools\frida-trainer\bc_event_summon.py summon --mapid 7000 --keep-alive
# 3. Add render support / playability if admitted-but-no-tile / want to actually play
& $PY tools\frida-trainer\bc_event_summon.py summon --mapid 7000 --render-support --play --keep-alive
# 4. Stop + restore stock
& $PY tools\frida-trainer\bc_event_summon.py stop-host
```

---

## 7. HGT / Recovery + the BCSFE time-fix

Recovery Mode is a **client-side** anti-time-cheat state that **hides events** on a clock jump.
The tripwire is drift between three save timestamps and the device clock, enforced natively in
`sub_525AB0` (15.4.1 `0x52CE20`; constants: 600s=10min, 129600s=1.5d, 86400s=1d, 259200s=3d).
The string "HGT" does not exist in the native lib — HGT00/01/02 are server/Java-UI labels.
**[VERIFIED-IDA / BINDIFF]**

| Save field | Governs | Allowed drift |
|---|---|---|
| `date_3` (packed date) | HGT02 (gacha / Special Stages) | must NOT be ahead at all |
| `timestamp` (double, `+0x176E0`) | HGT01/HGT00 (events/general) | ≤ 10 min ahead; ≤ 1.5 d behind |
| `energy_penalty_timestamp` (double) | energy / Gamatoto | ≤ 1 d ahead/behind |

**What killed time-travel:** the catastrophic 99-day half-XP cascade was triggered by a **full
MITM delivery** (intercepting `getTime`/notices + clearing the .dat cache, corrupting the date
via `sub_525AB0`'s drift check) — NOT necessarily a clean OS clock set. The **event injection is
HGT-orthogonal**; the *delivery* was the problem. This is exactly why the in-place `.dat` edit
(§5.3) is the safe path: it never writes a save timestamp, never intercepts time, never
cache-clears. The Frida hook (§6) is equally safe — it lies about gate answers only. **[VALIDATED]**

**Time-fix:** BCSFE `Fixes.fix_time_errors` (`BCSFE-Python/src/bcsfe/cli/edits/fixes.py`) resets
`date_3` / `timestamp` / `energy_penalty_timestamp` to now — it prevents a **new** drift penalty
but does **not** cancel an already-running recovery/half-XP countdown (separate state). Events
still render during the half-XP state. Recovery only sticks if the device clock is genuinely
correct before the next server sync. Recovery helper: `recover_battlecats_hgt.cmd`. **[VERIFIED-SRC]**

---

## 8. Validation-first sequence (single actor, serial — the live gate)

One actor at a time; no parallel device access. Each step is the precondition for the next.

1. **Read-only probe on stock boot** — confirm the target mapid is **absent** from the tree and
   `sub_819E20` returns 0 for it (`bc_event_summon.py probe`).
2. **Minimal scoped hook** — real clock, `summon --mapid <one>` (scoped `sub_819E20→1` only) →
   `treedump` shows the mapid **admitted** to the tree.
3. **If admitted but no tile** → add `--render-support`; add entry gates (`--play`) only when you
   actually want to enter the stage.
4. **PASS** = tile renders natively, stage opens, HGT/Recovery absent, **no save-timestamp
   change**, and detach restores stock behavior.

---

## 9. Current status — verified live 2026-05-26

**CONFIRMED LIVE [VALIDATED]:**
- event_0 crypto solved byte-exact; in-place HGT-safe delivery proven, survives relaunch.
- event_0 patched with a permanent **Heavenly Tower (mapid 7000, `local_assets=true`)** always-on
  row (`20300101` sentinel); md5 verified on device; persisted across a relaunch.
- **The tile rendered in Special Stages and the stage was played** — operator-confirmed on
  the live BlueStacks client running an **unmodified `libnative-lib.so`**. The data-only
  path is sufficient; **neither a Frida hook nor any static `.so` patch was in flight**.
  The four "unlock_patches" static patches (`sub_819E20→1`, `sub_5F8DF0→1`, `sub_8A3350→0`,
  `sub_8A3520→1`) are therefore belt-and-suspenders, not the primary lever.
- The dual-dependency model is verified end-to-end: a row whose date window covers "now"
  makes `sub_819E20` return true *naturally*, the mapid enters the calendar tree at launch,
  the Special-Stages menu rebuild draws the tile, and the entry gates let the stage be played.

### Primary recipe (data-only, no Frida)

Bundled artifacts live in `dat-cache-decode/`. Steps:

1. **Pick the all-events bundle** (or generate fresh from catalog):
   ```bash
   # Use bundled prebuilt (627 rows / ~403 events, dojo excluded):
   ls dat-cache-decode/event0_allon_20300101.dat
   # OR regenerate from current catalog:
   python dat-cache-decode/build_event0_allon.py
   ```

2. **HGT-safe in-place push** (round-trip check + force-stop):
   ```bash
   python dat-cache-decode/push_event0.py push \
       dat-cache-decode/event0_allon_20300101.plain.tsv
   ```

3. **Launch BC.** All events with `local_assets=true` appear in Special Stages and are
   playable. Persists across relaunches.

4. **Revert to stock scheduling anytime:**
   ```bash
   python dat-cache-decode/push_event0.py revert
   # Restores from bundled event0_backup/ev0_binpull.dat
   ```

### Where the Frida hook still matters (edge cases)

- **Read-only probing** of the calendar tree state (`bc_event_summon.py probe` — observe-only,
  no mutation).
- Admitting a mapid that should **not** have a calendar-active row (rare; e.g. RE of
  tree-membership questions for the off-rotation pool).
- Diagnostic instrumentation of `sub_819E20` for unrelated investigations.

For typical "play any event on demand" the hook is **not required**.

---

## 10. Doc index — where to dig deeper

| Topic | Doc |
|---|---|
| **Event atlas — activation-model authority** (dual-dependency model, row schema, band→category map, master table of ALL specials, activation matrix DATA-ONLY/NEEDS-PATCH/NEEDS-BAKE, reset-risk) | `docs/game-knowledge/BC-EVENT-ARCHITECTURE.md` |
| **Event atlas — living 8-dimension compendium** (cross-region asset matrix, cat-linkage, semi-story chains, version history) | `docs/game-knowledge/BC-STAGE-COMPENDIUM.md` |
| **Event atlas — glossary** (every event family named + defined) | `docs/game-knowledge/BC-EVENT-GLOSSARY.md` |
| **Event atlas — per-stage name roster** (647 rows; regen on version bump) | `docs/game-knowledge/BC-EVENT-ROSTER.generated.tsv` |
| **Event atlas — data-format reference** (field-by-field decode of event_0/MapStageData/Map_option/All_day_event) | `docs/game-knowledge/BC-DATA-FORMATS.md` |
| **Pinned offset manifest (15.4.1)** + launch-time identity self-verify | `tools/offsets/en-15.4.1.json`, `tools/offsets/bc_self_verify.py` |
| Full reconciled truth + superseded-claims appendix | `docs/research/2026-05-25-DEFINITIVE-TRUTH.md` |
| Live-device validation summary + same appendix | `docs/research/2026-05-25-GROUND-TRUTH.md` |
| Startup filter located + static patch set + tree internals | `dat-cache-decode/STARTUP_FILTER_RE.md` |
| Render gate three-gate model + builder control flow | `dat-cache-decode/RENDER_GATE_RE.md` |
| sale.tsv row-body schema (proves body is NOT the gate) + the 0x80/0xB0 trap | `dat-cache-decode/SALE_ROW_BODY_SCHEMA_RE.md` |
| The `20300101` sentinel, always-on encoding, builder | `dat-cache-decode/EVENT0_SENTINEL_RE.md` |
| HGT/Recovery native mechanism (addresses, constants, flags) | `docs/research/2026-05-24-hgt-recovery-mechanism.md` |
| Full architecture IDA pass + ceiling accounting | `docs/research/2026-05-24-bc-event-architecture-complete.md` |
| Early gate-chain map + forge/DEC-001 history | `docs/research/2026-05-24-event-unlock-architecture.md` |
| Event Summoner design spec | `docs/event-summoner-design.md` |
| The working single-gate trainer (proof single-fn hooks are reliable) | `docs/stage-unlock-implementation.md` |
| Event Summoner tool | `tools/frida-trainer/bc_event_summon{.py,_agent.js}`, `bc_event_index.py` |

> Where any older iteration doc (ITER1–15, MITM runbooks, `2026-05-24-*`) disagrees with this
> file or the two `2026-05-25-*` truth docs, **this file and those win**. See the Appendix A
> sections in the two truth docs for the catalogued superseded claims.

---

## 11. Lessons learned

1. **The render gate is a runtime-registration problem, not a data-schema problem.** Weeks were
   lost chasing the `sale.tsv` body schema. The body is trivial and identical between rendering
   and non-rendering rows; what matters is whether the mapid is admitted to the calendar tree at
   launch. Closing the body-schema question was necessary to *stop* chasing it.
2. **Single-function forced-constant hooks are reliable** — the stage-unlock trainer proved
   `sub_8A3350→0` / `sub_8A3520→1` work cleanly. The failure was never hook reliability; it was
   hooking the **wrong** function (the display gate `sub_817020` instead of the admission filter
   `sub_819E20`) and at the wrong time (after the tree was already built).
3. **The dual requirement was the blind spot.** Tree-admission and a valid row are *both*
   necessary. Row-alone renders nothing; admission-alone crashes. Time-travel only "worked"
   because it accidentally supplied both — and paid the HGT tax.
4. **Don't overcomplicate, and keep scope tight.** Blanket forcing (`0x5292e4`) and runtime
   vector forging (DEC-001) crashed. The winning shape is the minimal, scoped lever: one
   `sub_819E20→1` for one mapid + one always-on row, fully reversible.
5. **Delivery, not data, trips HGT.** Event injection is HGT-orthogonal. Full MITM and
   cache-clear corrupt the time path; the in-place `.dat` edit and scoped Frida hook do not.
   Never route the `.dat` through a text-mode shell redirect, and never delete-and-recreate it.
6. **Offsets are version-pinned; the data path is not.** The `.so` RVAs drift every BC update —
   pin them per version (`tools/offsets/en-<ver>.json`) and `bc_self_verify.py` the on-device
   binary before any patch (MATCH ⇒ offsets correct by construction). The data-only event_0
   path patches a data file, so it survives version bumps unchanged.

---

## 12. Version history / changelog

Offsets are pinned per game version in `tools/offsets/en-<ver>.json`. Earlier versions are kept
here packed for cross-version RE reference (NOT scraped). On a BC update: re-derive via
`bc_self_verify.py` + a bindiff pass, add a new subsection, and DO NOT overwrite this history.

### 15.4.0 / 15.4.1 (clientVersion 150400, app_version_code 1504010) — CURRENT

- **Identity:** native build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`;
  `so_sha256 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`; so_size
  12 666 808; getGlobal fingerprint `488d0599fe5b00c3` (AOB `48 8D 05 ?? ?? ?? ?? C3`,
  `lea_ret`). Verified live 2026-06-16 (BC pid 3807): the running binary byte-matched the
  manifest pin, so every static offset is correct **by construction** [BINDIFF].
- **Event-unlock offset drift vs 15.3.0** (all bindiff-verified against `en-15.4.1.json`):

  | symbol | 15.3.0 | 15.4.1 | drift |
  |---|---|---|---|
  | `sub_819E20` (admission filter — PRIMARY LEVER) | `0x819E20` | `0x823B00` | **+0x9CE0** |
  | `sub_817020` (activeness/display gate — dead lever) | `0x817020` | `0x820D00` | **+0x9CE0** |
  | `sub_5F8DF0` (id-band GATE-C) | `0x5F8DF0` | `0x600D70` | +0x7F80 |
  | `sub_525AB0` (calendar rebuild / HGT host) | `0x525AB0` | `0x52CE20` | +0x7370 |
  | `sub_8A3350` (entry-status →0) | `0x8A3350` | `0x8AD600` | **+0xA2B0** |
  | `sub_8A3520` (in-window →1) | `0x8A3520` | `0x8AD7D0` | +0xA2B0 |
  | `getGlobal` (own drift, NOT wallet cluster) | `0x653C80` | `0x65D900` | **+0x9C80** |
  | `getCash`/`setCash`/`getCap` (wallet cluster) | `0x37C170` … | `0x381510`/`0x381550`/`0x3815D0` | +0x53A0 |
  | `sub_4F1E20` (guerrilla getter) | `0x4F1E20` | `0x4F9060` | +0x7240 |
  | `SPEED_OFF` (game_state field) | — | `0x31D7A0` | reader 0x4B4DE2→0x4BB392 |
  | `INBATTLE_OFF` / `OUTBREAK_OFFSET` (game_state) | — | `0x37D9F8` / `0x321F80` | — |
  | `GLOBAL_WALLET_OFFSET` (game_state) | — | `0x23E0` | moved DOWN -0x10 |

  Three drift bands: **+0x9CE0** (admission/activeness), **+0xA2B0** (entry gates), **+0x53A0**
  (getGlobal/wallet cluster); `sub_5F8DF0` and `sub_525AB0` drift independently.
- **LIVE-ONLY (no static candidate — re-derive on device):** calendar tree `gs+0x2DD8`,
  guerrilla array `gs+0x11B8`, Aku block; the render/forge/list-builder code sites
  (`RA_RENDERER`/`RA_FORGE`/`RA_LISTBUILDER`) and the outbreak Interceptor anchors are null in
  the manifest (feature-gated off — a wrong RA on the render path crashes).
- **Helpers NOT in the 15.4.1 manifest** (15.3 RVA no longer applies — host-fn delta pass before
  hooking): `sub_4D2430`, `sub_5F8AC0`, `sub_5F8A10`, `sub_81BAF0`, `sub_7F52D0`, `sub_527270`,
  the row-skip branch `0x7F6EAF`, and the 15.3 call sites `0x52653f`/`0x5292e4`/`0x7f5d17`/`0x81bb53`.
- **Non-offset changes folded in:**
  - **Trainer self-verify** (`tools/offsets/bc_self_verify.py`) — launch-time identity hash gate
    (MATCH→writes enabled, else fail-closed); the PySide6 trainer GUI ships as a self-contained `.exe`.
  - **Towers correction** (§3/§4): towers ARE data-only activatable via a calendar-active
    sentinel row; the old "PROVEN DEAD" framing was scoped only to off-window forced rows +
    forcing `sub_817020`.
  - **7011 Fascinating Fallen Tower** content confirmed present on EN (append a sentinel row to activate).
  - **THREE mapid namespaces** (content / schedule / runtime-5xxxx) + **six schedule-only artifact
    bands** (8xxx/9xxx/15xxx/17xxx/26xxx/28xxx, zero EN content) documented in the event atlas.
  - **event_0 row-schema correction:** field 7 = `n_slot_groups`, not "map_count" (full decode in
    `BC-DATA-FORMATS.md` §1); multi-mapid carrier-row template (Way of the Cat 37000-37011 = ONE row).
- **The data-only event_0 path is binary-version-independent** and carried over from 15.3 unchanged.

### 15.3.0 (clientVersion 150300) — SUPERSEDED

- **Identity:** x86_64 `lib/x86_64/libnative-lib.so`, IDA imagebase `0x0` ⇒ RVA == file offset;
  binary `so_sha256 99bb6f36db1fc82a082f2a720c88325f9c146346fa0e0dbebae75205ab9eec7a`. Stack:
  BlueStacks Pie64 + Magisk/Kitsune + frida-server 17.9.1, ADB `127.0.0.1:5555`. Core RE 2026-05-25;
  live data-only validation (Heavenly Tower 7000 rendered + played, unmodified `.so`) 2026-05-26.
- **15.3.0 offsets (RVA == file offset)** — the lever set, superseded by the 15.4.1 table above:

  | Address | Symbol | Role |
  |---|---|---|
  | `0x819E20` | `sub_819E20` | PRIMARY LEVER — startup tree-populate admission filter (call site `0x52653f` in `sub_525AB0`) |
  | `0x817020` | `sub_817020` | display/activeness gate (callers `0x7f5d17`/`0x81bb53`, rebuild `0x5292e4`) — PROVEN DEAD as a lever |
  | `0x5F8DF0` | `sub_5F8DF0` | id-band wall (GATE-C): 900–999 / 35000–35045 |
  | `0x4D2430` | `sub_4D2430` | main-chapter catalog (ids 1..721); −1 for all specials |
  | `0x5F8AC0` | `sub_5F8AC0` | calendar-tree enable query (read side) |
  | `0x5F8A10` | `sub_5F8A10` | calendar-tree insert / set-enable (write side) |
  | `0x81BAF0` | `sub_81BAF0` | sale↔mapid activeness bridge |
  | `0x7F52D0` | `sub_7F52D0` | unified special/event menu builder |
  | `0x525AB0` | `sub_525AB0` | per-day recalc: builds tree + HGT gate + calls builder |
  | `0x527270` | `sub_527270` | menu parent |
  | `0x8A3350` | `sub_8A3350` | stage-entry status gate (`→0`) |
  | `0x8A3520` | `sub_8A3520` | in-window entry predicate (`→1`) |
  | `0x7F6EAF` | (row-skip branch) | builder skip of completed/progress-gated rows |

- **What changed in 15.4:** every `sub_*` RVA drifted (see the 15.4.1 table); the tower
  "PROVEN DEAD" framing was corrected (towers ARE data-only activatable); the trainer added a
  launch-time `bc_self_verify.py` identity gate; the event atlas (5 game-knowledge docs) added the
  three-namespace model, schedule-only bands, reset-risk class, and the row-schema correction.
  **UNCHANGED:** the dual-dependency model, the event_0 crypto (`89a0f99078419c28` + the
  `md5("battlecats"+cc+ct)` footer), the `20300101` sentinel, and the HGT-safe in-place delivery.