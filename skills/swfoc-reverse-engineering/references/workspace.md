# SWFOC Reverse Engineering Workspace Notes

## Important paths

- `C:\Users\Prekzursil\Downloads\SWFOC editor` -> .NET trainer/editor codebase
- `C:\Users\Prekzursil\Downloads\swfoc_memory` -> dump-analysis workspace
- `C:\Users\Prekzursil\Downloads\swfoc_memory\StarWarsG.DMP` -> primary dump
- `C:\Users\Prekzursil\Downloads\swfoc_memory\chatgpt_pro_bundle` -> precomputed analysis bundle

## First-pass commands

- `windbg-preview -z "C:\Users\Prekzursil\Downloads\swfoc_memory\StarWarsG.DMP"`
- `x64dbg` then open or attach to the target executable
- `binaryninja` / `ida64` / `ghidraRun` for static follow-up

## Existing evidence bundle

Useful files inside `chatgpt_pro_bundle` include:
- `00_manifest.json`
- `01_modules.json`
- `02_exception_and_threads.md`
- `03_damage_chain_candidates.jsonl`
- `04_vtable_scan_gameobjects.jsonl`
- `05_string_hits_and_symbols.md`
- `06_lua_state_candidates.md`
- `07_live_ce_notes.md`

Read those before reproducing heavy dump analysis from scratch.
