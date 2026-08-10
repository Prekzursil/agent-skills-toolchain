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

### ... mutate parsed objects (sf.catfood, sf.ototo.cannons, ...) ...
### PUSH safely (the non-obvious part)
### MSYS PUSH GOTCHA (cost an empty-file wipe — also applies to event_0 pushes)
### Ototo cannon unlock (the "no equip button" fix)
