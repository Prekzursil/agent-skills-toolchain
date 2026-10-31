---
title: hunting-notes
type: note
permalink: dqverify-repo-20261013/skills/swfoc-runtime-address-hunting/references/hunting-notes
---

# SWFOC Runtime Address Hunting Notes

## Local workspaces

- `C:\Users\Prekzursil\Downloads\SWFOC editor` -> source + trainer workspace
- `C:\Users\Prekzursil\Downloads\swfoc_memory` -> dump + artifact workspace

## Prebuilt evidence to consult first

Inside `swfoc_memory\chatgpt_pro_bundle`:
- `01_modules.json`
- `02_exception_and_threads.md`
- `03_damage_chain_candidates.jsonl`
- `04_vtable_scan_gameobjects.jsonl`
- `05_string_hits_and_symbols.md`
- `06_lua_state_candidates.md`
- `07_live_ce_notes.md`

## Rule of use

Do not treat a found address as stable until you have:
- the module name
- the module-relative offset
- at least one confirming static-analysis check
- a path to regenerate the finding in another run or build