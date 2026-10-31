---
title: file-formats-and-toolchain
type: note
permalink: dqverify-repo-20261013/skills/swfoc-modding/references/file-formats-and-toolchain
---

# File Formats and Toolchain

## Tools (Petrolution)
Source portal: https://modtools.petrolution.net/

Key tools and what they solve:
- ALO Viewer: inspect ALO models, skeletons, hardpoints.
- ALO Importer/Exporter: 3ds Max pipeline for ALO conversion.
- Animation Converter: convert animation files.
- Particle Editor: edit particle definitions.
- MTD Editor: inspect/edit icon/material texture metadata.
- String Editor: edit DAT string resources.
- Mega File Editor: pack/unpack MEG archives.
- Lua Tools: compile/decompile Lua/LUC forms.
- Map Editor: build/edit `.TED` maps and placements.

Version/dependency details (from tool pages):
- Most classic tools target .NET Framework 4.5 and require x86 VC++ redistributables.
- ALO Importer/Exporter require Autodesk 3ds Max support matrix per version in tool page.

## Core Formats

### MEG (archive container)
Source: https://modtools.petrolution.net/docs/MegFileFormat
- Contains multiple embedded files with a table of metadata (size, offset, CRC).
- Used for packaging deployable content and reducing loose-file sprawl.

### ALO (3D model)
Source: https://modtools.petrolution.net/docs/AloFileFormat
- Stores meshes, bones, hardpoints, materials, and references to textures.
- Supports one animation track directly in the model and can reference separate animation data.

### ALA (animation)
Source: https://modtools.petrolution.net/docs/AlaFileFormat
- Animation data for ALO skeletons.
- Frame timing is determined via keyframe intervals; interpolation logic matters for in-game motion.

### MTD (texture metadata wrapper)
Source: https://modtools.petrolution.net/docs/MtdFileFormat
- Wraps texture and metadata fields used by the engine/material pipeline.
- Includes identifiers and references; often paired with texture/icon workflows.

### DAT (localized text strings)
Source: https://modtools.petrolution.net/docs/DatFileFormat
- String entries keyed by CRC hash with UTF-16 text payloads.
- Used for in-game localization labels and descriptions.

### PARTICLE format
Source: https://modtools.petrolution.net/docs/ParticleFileFormat
- Text-based particle configuration with indentation/scoping semantics.
- Supports keyed value curves over normalized time.

### LUA/LUC
Source: https://modtools.petrolution.net/docs/LuaFileFormat
- Lua source and compiled chunks with version-specific bytecode nuances.
- Tooling differs by game/version (`eaw-luac`, `foc-luac`, and decompilers).

## Practical Pipeline Recommendations
1. Keep source assets in a clean authoring tree; output only deployable game files.
2. Validate model hardpoints in ALO Viewer before XML hookup.
3. Keep text changes tracked by source string XML where possible; rebuild DAT deterministically.
4. Prefer script + XML diffs first, package to MEG when load-order behavior requires it.
5. For map work, maintain `.TED` naming conventions and map preview extraction as part of release prep.