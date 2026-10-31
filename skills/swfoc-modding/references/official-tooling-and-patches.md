---
title: official-tooling-and-patches
type: note
permalink: dqverify-repo-20261013/skills/swfoc-modding/references/official-tooling-and-patches
---

# Official Tooling and Patch Baseline

## Petroglyph Mod Support Page (Current Baseline)
Source: https://www.petroglyphgames.com/eawmodtool/

Observed facts (2026-02-15 verification):
- Page states `LAST UPDATED FEB 3 2026`.
- Page states the most recent Steam patch release was October 2024.
- Official links are provided for:
  - Debug executable kit (`EAW_FOC_Debug_Kit_64.zip`)
  - Workshop uploader (`eaw_workshop_uploader.zip`)
  - Terrain editor (`EAW_Terrain_Editor_b.zip`)
  - Shader source package (`foc_shaders.zip`)

## Official Archive Metadata (HTTP headers)
Verified 2026-02-15:
- `EAW_FOC_Debug_Kit_64.zip`
  - Last-Modified: 2026-02-04 02:56:39 GMT
  - Contains debug binaries + PDBs for both `GameData` and `corruption` executables.
  - `corruption` binaries/PDBs are timestamped 2026-02-03 inside archive.
- `eaw_workshop_uploader.zip`
  - Last-Modified: 2023-11-14 04:38:53 GMT
  - Contains `uploader.exe`, config template, sample workshop content, and `SampleWS.workshop.json`.
- `EAW_Terrain_Editor_b.zip`
  - Last-Modified: 2024-10-23 04:01:53 GMT
  - Contains `EAW Terrain Editor.exe`.
- `foc_shaders.zip`
  - Last-Modified: 2023-11-14 04:38:53 GMT

## Debug Kit Operational Flow (from official readme)
Source: `Readme.txt` inside `EAW_FOC_Debug_Kit_64.zip`

High-level process:
1. Copy debug kit files into Steam install directory for EAW Gold Pack.
2. Launch game from Steam and reproduce crash.
3. Let crash upload dialog complete (can take minutes to >1 hour).
4. Disable kit via included `Delete_Debug_Files.bat` when done.

Implication:
- This is the canonical upstream path for reproducible crash telemetry sharing with maintainers.

## Workshop Uploader JSON Contract
Source: `SampleWS.workshop.json` inside uploader archive.

Observed fields:
- `publishedfileid`
- `contentfolder`
- `previewfile`
- `visibility`
- `title`
- `description`
- `metadata`
- `tags` (example includes `SinglePlayer`, `FOC`)

Use this structure for deterministic workshop publish/update automation scripts.

## Steam Patch Timeline (Relevant to Modding and Stability)
Sources:
- https://steamcommunity.com/games/32470/announcements/detail/5455609499987684897
- https://steamcommunity.com/games/32470/announcements/detail/4551542220607036511
- https://steamcommunity.com/games/32470/announcements/detail/3415444546217334775
- https://steamcommunity.com/games/32470/announcements/detail/4473730939641338744

Key points:
- 2023-11-20: both games converted to 64-bit executables (important for memory stability in large mods).
- 2024-10-22: FOC large galactic map performance improvements and additional fixes.
- 2022-11-09: maintenance patch with specific FOC crash fixes.
- 2021-01-14: maintenance patch with gameplay/performance fixes.

Practical guidance:
- Assume users can be on post-64-bit builds.
- Verify behavior tied to memory ceilings, load stability, and performance with current binaries.
- Keep backwards assumptions about 32-bit behavior flagged as historical unless explicitly needed.