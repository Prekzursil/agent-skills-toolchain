---
name: swfoc-editor-project
description: SWFOC Editor is a .NET 8 WPF app at C:\Users\Prekzursil\Downloads\SWFOC
  editor\ — the production platform for the trainer
type: project
permalink: main/claude-memory/downloads-swfoc-memory/project-swfoc-editor
---

The SWFOC Editor (SwfocTrainer.sln) is the production-grade WPF application that replaces the CE Lua trainer.

**Location:** `C:\Users\Prekzursil\Downloads\SWFOC editor\`
**Stack:** .NET 8, WPF, CommunityToolkit.Mvvm, C++20 native bridge
**Size:** 271 C# files, 221 tests, 11 project assemblies

**Architecture:**
- MVVM with custom AsyncCommand (not MVVM Toolkit's AsyncRelayCommand)
- ViewModel hierarchy: CoreStateBase → BindableMembersBase → LiveOpsBase → QuickActionsBase → SaveOpsBase → MainViewModel
- Native bridge: SwfocExtender.Host.exe (C++20) communicates via named pipe with JSON protocol
- Plugin system: EconomyPlugin, BuildPatchPlugin, GlobalTogglePlugin, HelperLuaPlugin
- Profile system with inheritance for mod support (TR, vanilla, submods)
- Catalog service parses MEG archives + XML for unit/planet/hero data

**Working features:** credits, fog reveal, AI toggle, instant build, unit cap, god mode, one-hit kill, spawn presets, selected unit inspection, save editor

**v5 expansion planned:** 21 features across 6 waves — roster browser, planet manager, diplomacy, camera director, Lua workshop, damage log, corruption controller, etc.

**Quality gates:** 100% coverage (line + branch), 0 issues on SonarCloud/CodeQL/QLTY/DeepSource, TDD mandatory, CCN≤15

**How to apply:** When working on game-facing features, implement in this project (not the CE trainer). The swfoc_memory project is the RE knowledge base that feeds into this editor.