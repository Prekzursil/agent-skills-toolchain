# Workspace Mod Notes (Current Project)

Workspace snapshot source: `/mnt/c/Users/Prekzursil/Downloads/SWFOC editor`

## Present Local Mod Inputs
- `1397421866(original mod)`
- `3447786229(submod)`
- `3661482670(cheat_mode_example)`

## Observed Structure

### `1397421866(original mod)`
- Large full mod payload with:
  - `Data/XML` (extensive multi-folder structure)
  - `Data/SCRIPTS` (AI, evaluator, gameobject, story, library)
  - `Data/ART` (maps/models/textures/shaders/movies)
  - `Data/Audio`, `Data/Text`, `Data/RESOURCES`
- File counts observed:
  - XML: 246
  - Lua: 613
  - TED maps: 428
  - MEG: 2

### `3447786229(submod)`
- Submod-style payload with targeted overrides/additions.
- Includes its own `roe.meg`, XML/Lua sets, maps, models, text resources.
- File counts observed:
  - XML: 83
  - Lua: 98
  - TED maps: 4
  - MEG: 1

### `3661482670(cheat_mode_example)`
- Small script plugin-style mod footprint.
- Contains Lua only in:
  - `Data/Scripts/Library/eawx-plugins/options-handler/...`
- File counts observed:
  - XML: 0
  - Lua: 2
  - TED: 0
  - MEG: 0

## Why This Matters for Tooling in This Repo
- Process detection and profile routing should support both workshop-id-style mods and local `MODPATH` workflows.
- Action safety checks should account for partial submods that do not include full asset trees.
- File-layout heuristics should not assume only one script casing convention (`SCRIPTS` vs `Scripts`).
