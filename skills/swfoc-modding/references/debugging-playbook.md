---
title: debugging-playbook
type: note
permalink: dqverify-repo-20261013/skills/swfoc-modding/references/debugging-playbook
---

# Debugging Playbook

## 1. Confirm Runtime Context First
- Identify game target: `sweaw.exe` or `swfoc.exe`.
- Identify launch mode: base game, `MODPATH`, or `STEAMMOD`.
- Record exact mod/submod IDs and path that loaded.

Why:
- Most "it doesn't work" reports are mis-launch issues, stale files, or wrong folder target.

## 2. Establish Binary/Patch Baseline
Primary sources:
- https://www.petroglyphgames.com/eawmodtool/
- https://steamcommunity.com/games/32470/announcements/detail/5455609499987684897
- https://steamcommunity.com/games/32470/announcements/detail/4551542220607036511

Checklist:
- Confirm user is on current Steam binaries (post-64-bit era from 2023 onward).
- If issue is crash-heavy, request debug-kit reproduction path.

## 3. Crash Triage with Official Debug Kit
Source: debug kit readme in official archive.

Procedure:
1. Install `EAW_FOC_Debug_Kit_64.zip` into game directory.
2. Reproduce crash.
3. Allow upload prompt to finish completely.
4. Remove debug files afterward with provided cleanup script.

## 4. Inspect Logs
Practical sources:
- https://steamcommunity.com/sharedfiles/filedetails/?id=2726462029

Useful logs:
- `...\Star Wars Empire at War\corruption\LogFile.txt`
- `...\<mod>\Data\Scripts\LuaScriptLog.txt` (if script logging is enabled/generated)

What to scan for:
- missing asset references
- XML parse warnings
- Lua runtime errors
- file-not-found issues indicating path/case mismatch

## 5. Isolate by Subsystem
Fast isolation order:
1. Launch without mod to verify base runtime.
2. Launch with parent mod only.
3. Add submod changes in slices (XML-only, Lua-only, art-only).
4. If map-specific, test alternative map to isolate `.TED` or placed object issues.
5. If AI-specific, test loose-file vs MEG-packaged AI data.

## 6. Common Failure Classes
- Wrong executable target (`sweaw` vs `swfoc`).
- Wrong launch argument or path quoting in `MODPATH`.
- Submod installed in wrong directory depth.
- Asset references mismatching file casing or extension.
- Script bytecode/source mismatch or unsupported Lua tooling output.
- Stale cached content from previous iterations.

## 7. Regression Checklist Before Shipping
- Launch path works on clean install instructions.
- Core GC and tactical loads pass without script spam.
- No immediate `LogFile.txt` fatal errors.
- Workshop package metadata is valid and preview/content paths resolve.
- Parent-mod compatibility expectations are explicit in release notes.