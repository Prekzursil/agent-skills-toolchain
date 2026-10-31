---
title: mod-architecture-and-workflow
type: note
permalink: dqverify-repo-20261013/skills/swfoc-modding/references/mod-architecture-and-workflow
---

# Mod Architecture and Workflow

## Canonical Mod Folder Shape
Primary sources:
- https://modtools.petrolution.net/articles/Creating_A_Mod
- https://steamcommunity.com/sharedfiles/filedetails/?id=2812662575

Baseline structure for manual mods:
- `Star Wars Empire at War\corruption\Mods\<mod_name>\Data\...`
- Common subfolders under `Data`:
  - `XML`
  - `Scripts`
  - `Art`
  - `Text`
  - `Audio` (as needed)

Naming constraints from Petrolution guide:
- Mod folder names should use only letters, digits, underscore, and hyphen.
- Avoid spaces unless you are careful with launch quoting.

## Launching Mods
Primary sources:
- https://modtools.petrolution.net/articles/Creating_A_Mod
- https://steamcommunity.com/discussions/forum/1/4841930637303525852/
- https://www.moddb.com/mods/republic-at-war/downloads/republic-at-war-v18

Manual mod launch patterns:
- FoC executable with explicit mod path:
  - `swfoc.exe MODPATH=Mods\MyMod`
- If mod path contains spaces:
  - `swfoc.exe MODPATH="C:\...\My Mod"`

Workshop launch pattern:
- `swfoc.exe STEAMMOD=<workshop_item_id>`

Notes:
- `STEAMMOD` is the cleanest route for subscribed workshop items.
- `MODPATH` is still useful for local development builds and local submod testing.

## Workshop and Submod Packaging
Primary sources:
- https://www.petroglyphgames.com/eawmodtool/
- https://www.moddb.com/mods/republic-at-war/downloads/republic-at-war-v18
- https://steamcommunity.com/sharedfiles/filedetails/?id=2812662575

Rules that avoid common breakage:
- Do not repack or redistribute full parent mods for submods unless licensing explicitly permits it.
- Keep submod payload minimal: only overridden/added files.
- Keep install instructions exact (target folder + launch argument).
- For workshop-only parent mods, either:
  - publish a workshop dependency-friendly structure, or
  - provide clear copy/install instructions for local testing.

## AI and Script Loading Nuance
Community source:
- https://focumentation.fandom.com/wiki/AI_Guide

Historical behavior noted by community:
- Some AI/perception edits historically needed MEG packaging + `MegaFiles.xml` registration to load reliably.

How to use this safely:
- Treat this as version-sensitive and verify against current game build.
- If loose-file AI edits are ignored, test MEG packaging path before concluding logic is wrong.