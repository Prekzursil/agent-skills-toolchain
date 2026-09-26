---
name: bcsfe-save-roundtrip
description: BCSFE save pull/edit/push recipe for the rooted BlueStacks Battle Cats
  (EN) — incl. the in-place push that preserves uid/SELinux, and the Ototo cannon-unlock
  fields
metadata:
  node_type: memory
  type: reference
  originSessionId: 36cba66d-b7f5-47e0-86a9-0861130bb158
permalink: main/claude-memory/root/bcsfe-save-roundtrip
---

Round-trip for editing the live Battle Cats EN save on the rooted BlueStacks RE stack (see [[bluestacks_pie64_root_recipe]]). Package `jp.co.ponos.battlecatsen`, save at `/data/data/<pkg>/files/SAVE_DATA` (539 KB primary; `SAVE_DATA.OLD`=BC's own rollback, `BACKUP_SAVE_DATA`=cloud/transfer, `SAVE_DATA4`=secondary slot). adb=`C:\ADB\adb.exe`, device `127.0.0.1:5555`, app uid `u0_a65` = numeric **10065**. BCSFE-Python 3.3.0 venv: `D:\ReverseTools\Android\BCSFE-Python\.venv`.

**PULL (byte-exact, no CRLF/MSYS mangling):** do it in PowerShell, not git-bash (MSYS rewrites `/data` & `/sdcard` args). Force a flush first — BC holds the save in RAM: `adb shell input keyevent KEYCODE_HOME`, wait ~3s (mtime then within seconds of device clock = fresh). Then `su -c 'cp <save> /sdcard/SAVE_DATA && chmod 666 …'` → `adb pull /sdcard/SAVE_DATA <local>`.

**EDIT headlessly (no interactive menu):** `from bcsfe import core; sf = core.SaveFile(core.Path(p).read())` (cc auto-detects `en`), mutate parsed objects, `sf.to_file(core.Path(out))` (re-serializes via `to_data()` incl. checksum). Open the editor for a human with `bcsfe -i <path>` (`-i`/`--input-path` skips the load prompt).

**PUSH safely (the non-obvious part):** `am force-stop <pkg>` first (else BC's autosave overwrites you; force-stop does NOT flush, background does). Back up on-device (`cp SAVE_DATA SAVE_DATA.before-<ts>`). Then `adb push` to `/sdcard` and overwrite **in place**: `su -c 'cat /sdcard/new > <files>/SAVE_DATA; chown 10065:10065 …; chmod 660 …; restorecon …'`. The `cat >` reuses the existing inode so owner + SELinux `app_data_file` context survive — a fresh `cp`/`push` as root lands `root:root` with wrong context and BC rejects/resets it. Verify `md5sum` device == local. User reopens BC to load it.

**MSYS PUSH GOTCHA (cost an empty-file device wipe 2026-05-27, applies to event_0 pushes too):** in git-bash, `adb push <src> /sdcard/<dst>` silently mangles the destination via MSYS path-conversion (`/sdcard/...` → `C:/Program Files/Git/sdcard/...`) → the push FAILS. And the in-place step `cat /sdcard/<dst> > <devfile>` opens `<devfile>` for write — **truncating it to 0 bytes BEFORE `cat` runs** — so a failed push leaves the device file EMPTY (md5 `d41d8cd98f00b204e9800998ecf8427e`). Fix: `export MSYS_NO_PATHCONV=1` before any git-bash `adb push`/`shell` with `/sdcard` or `/data` args (or do the push in PowerShell). ALWAYS `md5sum` the device file after the write — that's what catches the empty-file/wrong-content state. Device serial also changes across BlueStacks restarts (`emulator-5554` vs `127.0.0.1:5555`) — `adb devices` first, target `-s <serial>`.

**Ototo cannon unlock (the "no equip button" fix, confirmed 2026-05-25):** `sf.ototo.cannons` = `{cannon_id: Cannon(development, levels)}` + `selected_parts` (a `[foundation, style, effect]` triple **per formation slot** = the equip state). `cannon_id 0`=basic; 1–7=Slow Beam/Iron Wall/Thunderbolt/Waterblast/Holy/Breaker/Curse-blast. `development`: 0 none / 1 foundation / 2 style / 3 effect(full). **The in-game Change/customize button only appears once lines are developed past default** — set `development=3` and `levels` ≥1 (effects need level≥1; just building gives no effect). Editing the save does NOT equip — the player still picks the Foundation/Style/Effect mix in the Ototo screen (Gamatoto → swipe left), and it binds per-formation-slot.