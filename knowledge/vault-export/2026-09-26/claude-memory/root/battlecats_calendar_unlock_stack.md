---
name: battlecats-calendar-unlock-stack
description: BC v15.3.0 calendar/Special-Stages unlock working stack — MITM + surgical
  sub_817020 hook + pack keys; HGT trigger map; 12-iter outcome
metadata:
  node_type: memory
  type: project
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/battlecats-calendar-unlock-stack
---

Working unlock stack for time-limited events in Battle Cats (jp.co.ponos.battlecatsen v15.3.0) on BlueStacks Pie64 (`127.0.0.1:5555`, Magisk + Frida-server PID auto-managed):

**Why:** 12 Ralph-loop iterations established what works vs what triggers HGT anti-tamper. Stack is reversible and HGT-safe.

**How to apply:** Final delivery script `D:\ReverseTools\Android\battlecats-toolkit\dat-cache-decode\deliver_final.ps1` — verifies BlueStacks alive + filesystem RW + frida-server, launches BC, attaches proven Codex `bc_stage_unlock.py` hook (67-tile unlock at ra=0x81bb53), additionally attaches `probe_launchtime.js` to capture launch-time populator data for next-iter RE.

**BlueStacks emergency-RO**: If `/data` is mounted read-only, BC cannot launch. Symptoms: `am start` succeeds but `pidof` returns nothing, `adb push` to /sdcard or /data/local/tmp returns "Read-only file system". Fix: restart the BlueStacks Pie64 instance via Multi-Instance Manager. Cannot be fixed from inside the guest.

## Working components (all verified)

| Component | Effect | Key path |
|---|---|---|
| `mitm_addon.py` | Rewrites gatya/sale/item TSVs from `nyanko-events.ponosgames.com` — 485+ rows widened to 2024-01-01..2099-12-31 per launch | `dat-cache-decode/mitm_addon.py` |
| `force_menu_only.py` + `caller_filter_hook.js` | Surgical hook on `sub_817020`: forces TRUE ONLY when ra=`0x81bb53` (caller in `sub_81BAF0` menu-iter loop). 170 menu-iter visibility checks pass per menu open. Zero side effects on sales/gacha/tutorials (different ra). | `dat-cache-decode/force_menu_only.py` |
| `decrypt_packs.py` | Decrypts BC `.pack`/`.list` files via BCGM-Python public keys. `.list` = AES-ECB(md5_str("pack")[:8].hex()); `*Server.pack` = AES-ECB(md5_str("battlecats")[:8].hex()); EN local `.pack` = AES-CBC(key/iv from BCGM-Python) | `dat-cache-decode/decrypt_packs.py` |
| `recover_battlecats_hgt.cmd` | Aligns save HGT fields back to real time. Recovers from HGT01/HGT02. | `recover_battlecats_hgt.cmd` |

## sub_817020 caller fingerprints (libnative-lib.so + 0x...)

7 unique callers in libnative-lib.so. Surgical hook targets ra=`0x81bb53` only.

| ra | Caller | Calls/menu | Purpose | Hook decision |
|---|---|---|---|---|
| `0x81bb53` | `sub_81BAF0` (menu-iter loop) | 96 | **Special Stages tile visibility** | FORCE TRUE |
| `0x5292e4` | parent menu builder | 361 | Stage list enumeration | leave natural |
| `0x7f5d17` | sales check | 722 | Sale window | leave natural |
| `0x7f93f4/9c/5f7` | gacha banners | 47×3 | Gacha (MITM already widens) | leave natural |
| `0x81a3de` | tutorial trigger | 46 | Tutorial gate | leave natural |

## HGT trigger map (don't repeat the mistakes)

- ❌ **Hook libc `localtime_r`/`gmtime_r` PLT directly** → HGT02 fires within seconds. BC anti-tamper validators go through libc PLT.
- ❌ **Lie about `time(NULL)` return** → HGT01 fires. Server time mismatch.
- ✅ **Hook BC tm wrappers `sub_ACEBB0`/`ACEC40`/`ACF430`** → HGT-safe (10K+ lies, no fire). Botan/Tapjoy/HGT use libc PLT, bypassing these wrappers. **BUT ineffective at unlocking tiles** because BC's filter uses real time_t from xmm0, not the wrapper-tm output. Wrapper-tm is consumed for UI text + first-launch-today reset only.
- ✅ **Modify FilterData rows in transit via MITM** → No HGT (rows still match what server-time would have said).
- ✅ **Caller-filtered hook on `sub_817020`** → Surgical. No HGT, no popups.

## Side-effect notes

- The "Tactics for Japan" / stage-clear cutscenes / expired-sale popups from iteration 9 came from the BROAD hook on `sub_817020` (forced ALL 4 callers TRUE). Surgical hook (ra=0x81bb53 only) has zero such effects.
- The User Rank 7777→10500+ reward popup chain is a PRE-EXISTING queue accumulated from prior gameplay — verified persistent after killing hook. Clear with `clear_user_rank_rewards.py` save edit OR manually tap through (one Yes per ~100 ranks).

## What's still impossible

- Tiles for OTHER days/months simultaneously (e.g. Tuesday + Wednesday at once) — requires patching `sub_525AB0`'s ID-vector pre-build (~700 bytes of dense logic to RE)
- Past collab event tiles — assets not on device, PONOS server controls
- HGT02 cleared after server sync — `recover_battlecats_hgt.cmd` works ONLY if used before BC syncs

Related: [[battlecats_stage_unlock_hook]] for the stage-entry hook from earlier session, [[bluestacks_pie64_root_recipe]] for the device stack underneath.