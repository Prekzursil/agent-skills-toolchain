---
name: bcsfe-save-roundtrip
description: Use when pulling, editing, or pushing a Battle Cats (EN, rooted BlueStacks) SAVE_DATA file - the byte-exact PowerShell + HOME-key flush pull, the headless BCSFE-Python library edit (no interactive menu), and the in-place cat-redirect push that preserves uid 10065 and the SELinux app_data_file context so the game accepts the save. Includes the MSYS path-conversion gotcha that silently truncates the device file to 0 bytes (cost a full wipe), the force-stop-before-push rule, and the Ototo cannon-unlock fields. NOT for non-rooted devices or the iOS save format.
license: MIT
---

# BCSFE Save Round-Trip (Battle Cats EN, rooted BlueStacks)

> Edit the **live** Battle Cats EN save end to end: pull byte-exact, edit
> headlessly, push **in place** so uid + SELinux context survive. The non-obvious
> parts (RAM flush, in-place `cat >`, MSYS path mangling) are what bite.

## Environment

- Package `jp.co.ponos.battlecatsen`; save at `/data/data/<pkg>/files/SAVE_DATA`
  (~539 KB primary). Siblings: `SAVE_DATA.OLD` = BC's own rollback,
  `BACKUP_SAVE_DATA` = cloud/transfer, `SAVE_DATA4` = secondary slot.
- adb = `C:\ADB\adb.exe`, device `127.0.0.1:5555`. App uid `u0_a65` = numeric
  **10065**. BCSFE-Python 3.3.0 venv: `D:\ReverseTools\Android\BCSFE-Python\.venv`.
- Serial changes across BlueStacks restarts (`emulator-5554` vs `127.0.0.1:5555`)
  — `adb devices` first, then target `-s <serial>`.

## PULL (byte-exact, no CRLF/MSYS mangling)

Do it in **PowerShell**, not git-bash (MSYS rewrites `/data` & `/sdcard` args).
BC holds the save in RAM, so **flush first**:

```powershell
& C:\ADB\adb.exe shell input keyevent KEYCODE_HOME   # backgrounding flushes to disk
Start-Sleep -Seconds 3                                # mtime should now ~= device clock
& C:\ADB\adb.exe shell "su -c 'cp /data/data/jp.co.ponos.battlecatsen/files/SAVE_DATA /sdcard/SAVE_DATA && chmod 666 /sdcard/SAVE_DATA'"
& C:\ADB\adb.exe pull /sdcard/SAVE_DATA D:\WSA\saves\SAVE_DATA
```

(Force-stop does **not** flush — only backgrounding does. Confirm freshness by
mtime ≈ device clock.)

## EDIT headlessly (no interactive menu)

```python
from bcsfe import core
sf = core.SaveFile(core.Path(p).read())   # cc auto-detected as 'en'
# ... mutate parsed objects (sf.catfood, sf.ototo.cannons, ...) ...
sf.to_file(core.Path(out))                # re-serializes via to_data(), incl. checksum
```

For a human, open the editor with `bcsfe -i <path>` (`-i`/`--input-path` skips
the load prompt).

## PUSH safely (the non-obvious part)

1. **`am force-stop <pkg>` FIRST** — else BC's autosave overwrites you.
2. Back up on device: `cp SAVE_DATA SAVE_DATA.before-<ts>`.
3. `adb push` to `/sdcard`, then overwrite **in place** with `cat >`:

```bash
su -c 'cat /sdcard/new_save > /data/data/jp.co.ponos.battlecatsen/files/SAVE_DATA; \
       chown 10065:10065 /data/data/jp.co.ponos.battlecatsen/files/SAVE_DATA; \
       chmod 660 /data/data/jp.co.ponos.battlecatsen/files/SAVE_DATA; \
       restorecon /data/data/jp.co.ponos.battlecatsen/files/SAVE_DATA'
```

The `cat >` **reuses the existing inode**, so owner + SELinux `app_data_file`
context survive. A fresh `cp`/`push` as root lands `root:root` with the wrong
context and BC rejects/resets the save. Then **verify** `md5sum` device == local.
User reopens BC to load it.

## MSYS PUSH GOTCHA (cost an empty-file wipe — also applies to event_0 pushes)

In git-bash, `adb push <src> /sdcard/<dst>` silently mangles the destination via
MSYS path-conversion (`/sdcard/...` → `C:/Program Files/Git/sdcard/...`) so the
push **fails** — and the in-place step `cat /sdcard/<dst> > <devfile>` opens
`<devfile>` for write, **truncating it to 0 bytes BEFORE `cat` runs**, leaving the
device file EMPTY (md5 `d41d8cd98f00b204e9800998ecf8427e`).

**Fix:** `export MSYS_NO_PATHCONV=1` before any git-bash `adb push`/`shell` with
`/sdcard` or `/data` args (or just do the push in PowerShell). **Always `md5sum`
the device file after the write** — that is what catches the empty/wrong-content
state.

## Ototo cannon unlock (the "no equip button" fix)

`sf.ototo.cannons` = `{cannon_id: Cannon(development, levels)}` plus
`selected_parts` (a `[foundation, style, effect]` triple **per formation slot** =
the equip state). `cannon_id 0` = basic; 1–7 = Slow Beam / Iron Wall / Thunderbolt
/ Waterblast / Holy / Breaker / Curse-blast. `development`: 0 none / 1 foundation /
2 style / 3 effect(full).

The in-game Change/customize button **only appears once lines are developed past
default** — set `development=3` and `levels >= 1` (effects need level ≥ 1; merely
building gives no effect). Editing the save does **not** auto-equip — the player
still picks the Foundation/Style/Effect mix in the Ototo screen (Gamatoto → swipe
left); it binds per formation slot.

> Live-game care: read-only discovery is safe; prefer reversible save-edits over
> forcing unverified in-memory fields. On a "broken" state, kill all hooks +
> restart BC first, then restore the `SAVE_DATA.before-*` backup.
