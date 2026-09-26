---
title: battlecats_startup_filter_rebuilt_apk
type: note
permalink: main/claude-memory/root/battlecats-startup-filter-rebuilt-apk
---

# BC EN 15.3.0 startup event-visibility filter — LOCATED + static patch (rebuilt APK)

Repo: D:\ReverseTools\Android\battlecats-toolkit (branch ralph-hardening, commit a4c12e8).
Supersedes the "runtime can't reach it" dead-end. The user-approved rebuilt-APK path.

## The crux (corrects the sub_5FF760 hypothesis)
- sub_5FF760 (0x702f, 28KB) = game-state CONSTRUCTOR called from .init_array ctor
  sub_64BF10 @0x64c295 with rdi=&unk_C17530. Builds the calendar tree EMPTY (sub_5F8690).
  NO date filter. sub_5F92E0 (0x5b0b, 23KB) = its __cxa_atexit DESTRUCTOR (not init).
- The REAL filter is in **sub_525AB0** (0x1081) — per-day/session recalc that (re)builds
  the active-event-window calendar tree (container = game_state+11736), then calls the
  menu builder sub_7F52D0. It runs during early boot (before Frida attach) → why runtime
  failed. Tree = two libc++ maps: Map-A enable (root+0x20, sub_5F8A10 insert / sub_5F8AC0
  query=Gate1), Map-B state (root+0x08, sub_5F8B00 / sub_5F8BB0).
- Populate loop @0x5262e9: per FilterData record, `if(!sub_819E20(rec,now)) goto skip;`
  then GATE-C `if(sub_4D2430(mapid)==-1 && !sub_5F8DF0(mapid)) goto skip;` else
  sub_5F8A10(tree,mapid,1) => tile visible.
- sub_819E20(rec,now) = prerequisite checks (sub_4DF750/8B0/A10 progress, flag rec+0xA0)
  AND tail `sub_817020(rec,1,0,now)` (the pure date-window+ver+platform+slot gate). It is
  the off-window+lock filter. Called by 8 event/calendar builders; NOT on sales/gacha/
  reward paths (those use sub_817020 direct / sub_817010 thunk / sub_81BAF0).

## The patch set (HGT-safe: gate answers only, never time/save) — all forced-const stubs
RVA==file offset (imagebase 0x0). Stock .so SHA256
99bb6f36db1fc82a082f2a720c88325f9c146346fa0e0dbebae75205ab9eec7a (byte-verified).
| fn | RVA | bytes | forced |
| sub_819E20 | 0x819E20 | B8 01 00 00 00 C3 | ret 1 (admit every record to tree) |
| sub_5F8DF0 | 0x5F8DF0 | B8 01 00 00 00 C3 | ret 1 (id-band GATE-C: any mapid passes) |
| sub_8A3350 | 0x8A3350 | 31 C0 C3 | ret 0 (stage-entry enterable) [proven] |
| sub_8A3520 | 0x8A3520 | B8 01 00 00 00 C3 | ret 1 (in-window entry) [proven] |
Verified 2 ways: IDA decompile + objdump; present in final signed APK; .so size unchanged.
sub_5F8DF0 also alters sub_523DB0 (per-record detail-proc + loop terminator) → pipeline
has --no-idband to test the safer patch-1-only config.

## Tooling + build (works end-to-end)
- tools/tbcml-bake/lib_patches.py: SHA-locked patch defs + tbcml LibPatch builder +
  standalone LIEF-free .so patcher/verifier (CLI: `python lib_patches.py <so> [--out X]`,
  detects stock vs ALREADY-PATCHED). LIEF NOT installed in toolkit venv → tbcml FuncPatch
  does a pure in-place byte write (no ELF re-emit, no offset drift). Key fact.
- tools/tbcml-bake/bake_pipeline.py: --patch-only (default=crux), --bake(+content),
  --probe; pre-flight SHA+prologue check, post-pack patch-byte re-verify. Venv =
  D:\ReverseTools\Android\BCSFE-Python\.venv (has tbcml 2.0.0 vendored). Needs
  apk.set_allowed_script_mods(True) or add_patch_mods returns early. apksigner at
  tools/apk-build/bt/android-14 on PATH; Java 21.
- OUTPUT (gitignored): tools/apk-build/out/bc-15.3.0-event-unlock.apk (signed, ~143MB).
  Manifest: reports/tbcml_event_unlock_build.json. RE: dat-cache-decode/STARTUP_FILTER_RE.md
  + decompiles in dat-cache-decode/startup_filter_re/.

## Alongside-install rename + DETERMINISTIC verification (2026-05-25, commit 79e6a48)
- tools/tbcml-bake/rename_repackage.py: repackages the patched APK under
  jp.co.ponos.battlecatsen.unlock so it coexists with stock (own /data/data, uid u0_a66 vs
  u0_a65 — ZERO save risk). apktool decode → rewrite manifest (whole-token
  jp.co.ponos.battlecatsen→…unlock = package + DYNAMIC_RECEIVER perm + 8 provider
  authorities; MUST rename authorities/perm or install fails CONFLICTING_PROVIDER/
  DUPLICATE_PERMISSION) → fix 1 hardcoded smali literal (MyActivity openNotificationSettings,
  non-boot) → apktool build → zipalign → apksigner sign (debug ks in gitignored
  tools/apk-build/_local_keystore/). Class names jp.co.ponos.battlecats.* (NO "en") preserved.
  Patched .so survives apktool verbatim (doNotCompress has `so`).
- BOOTS under new id (PONOS splash + Language screen; no Cocos pkg-check/hardcoded-ref crash).
- VERIFIED via frida (tools/frida-trainer/bc_verify_patch_live.py + bc_calendar_tree_dump.py,
  read-only): unlock app's 4 patched fns are LIVE in process memory (mov eax,1;ret etc.);
  stock shows original prologues. sub_819E20: STOCK returns 0 (EXCLUDES) for 42/57 calls,
  unlock byte-stubbed →always 1 → off-window skip is dead code → all records admitted.
  Stock tree=686 nodes (off-window monthly 1009-1038/advent present but enable=0, only 1
  enabled). Evidence: reports/verify_{unlock,stock}.json, tree_stock.json,
  dat-cache-decode/RENAMED_APK_VERIFICATION.md.

## 2026-06-05 RUNTIME MEASUREMENT (data + code patches are COMPLEMENTARY — both old claims overstated)
Live calendar-tree dumps (read-only): **stock + event_0-always-active data patch = 704 nodes / 537
ENABLED / 269 off-window** (Empress 1269-1281 incl.); **`.unlock` (4 code patches CONFIRMED live in
memory via bc_verify_patch_live.py, but its own data dir NOT event_0-patched) = 704 / 38 / 0**.
The two builds differ in BOTH variables (data + code), so this does NOT isolate the code patch's
effect. The populate loop runs PER FilterData record → `sub_819E20→1` only stops EXISTING records
being skipped; it can't enable a mapid with no schedule row. So 38-enabled is equally consistent
with "fresh data dir schedules ~38" as with "patch inert." ⇒ the data patch (rows) and code patch
(date-gate) are **complementary**; the old "all records admitted" inference was overstated, and
"code patch runtime-inert" would be the OPPOSITE overstatement — **unresolved**. DISCRIMINATING TEST
(not yet run): event_0-always-active patch `.unlock`'s OWN /data/data/.../files/ + re-dump → ~537
⇒ data was missing piece; still ~38 ⇒ code patch genuinely inert. SOLID regardless: tree-admit ≠
menu-visible (menu reads `qword_108C5A8`; assets = true ceiling). Full evidence: toolkit
`docs/research/runtime-confirmations/` (origin/main).

## GOTCHAS (BlueStacks Pie64, this device)
- frida-server runs but `pidof frida-server`/ARGS-grep miss it (renamed proc); bc_stage_unlock.py
  `_ensure_transport` then says "frida-server not running". Fix: restart clean —
  `su -c 'nohup /data/local/tmp/frida-server -l 0.0.0.0:27042 …'` then adb forward tcp:27042.
  Connect via `add_remote_device("127.0.0.1:27042")` (NOT get_device — that USB-bridge path
  enumerates but `attach` fails ServerNotRunning here).
- `adb install --bypass-low-target-sdk-block` REJECTED on Android 9 (unknown option). Omit it;
  targetSdk35 installs on API28 fine. Streamed `adb install` of 143MB STALLS over network-ADB
  → use `adb push /data/local/tmp/x.apk` + `pm install -r`.
- Synthetic touch (input tap / sendevent 0..32767 / input swipe) on "BlueStacks Virtual Touch"
  lands on Cocos buttons (visibly highlights) but click often DOESN'T register → couldn't drive
  fresh-profile Language→Cat Base programmatically. Needs a real human tap. Game render is
  letterboxed; screencap sizes vary (480/960/1920) — touch coords are physical 1920x1080.
- Game can deep-link the system Date&Time picker on clock mismatch — CANCEL it, never set date
  (HGT). Device clock left real (May 25 2026).

## NOT verified in-game (honest)
Byte patches verified statically only. Operator must sideload
(adb install --bypass-low-target-sdk-block -r) + open Special Stages. Caveats: patch
widens events the fetched event_0.dat schedules; events with NO FilterData row still need
a schedule row (content alone ≠ a record); mapid w/o on-device stage content crashes on
entry (region/collab art out of scope).

## IDA MCP access (this session)
IDA live on port 13337 (HTTP JSON-RPC at /mcp, SSE framing). MCP funnel only exposes 3
meta-tools (list/open/select instance) — the decompile/disasm/xrefs/patch/get_bytes verbs
are reachable ONLY via direct HTTP POST to http://127.0.0.1:13337/mcp (use urllib, not
shell-interpolated curl — shell mangles JSON args). Helper pattern saved the session.