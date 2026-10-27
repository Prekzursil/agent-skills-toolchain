---
name: swfoc-reverse-engineering
description: Use when working on SWFOC editor runtime or native analysis, or on the swfoc_memory dump bundle, especially for dump triage, debugger attach flows, signature generation, binary comparison, import repair, or moving evidence between WinDbg Preview, x64dbg, Cheat Engine, IDA Pro, Binary Ninja, and Ghidra.
---

# SWFOC Reverse Engineering

## Overview

Use this skill for SWFOC-native evidence work: dump triage, runtime tracing, static follow-up, and signature or diff workflows. Keep XML, Lua, MEG packaging, and submod integration in `$swfoc-modding`; use this skill when the question is really about the executable, dump, memory layout, or runtime behavior.

## Workspace Anchors

- Source and trainer workspace: `C:\Users\agentuser\Downloads\SWFOC editor`
- Dump and artifact workspace: `C:\Users\agentuser\Downloads\swfoc_memory`
- Primary dump artifact: `StarWarsG.DMP`
- Prebuilt evidence pack: `swfoc_memory\chatgpt_pro_bundle\`

## Recommended Workflow

1. Validate the target first. Confirm whether the request is about the SWFOC runtime, a dump artifact, or source-side modding. If it is XML, Lua, or packaging work, hand back to `$swfoc-modding`.
2. For the dump path, start with `$windbg-preview` on `StarWarsG.DMP`. Use `$windbg-command-cookbook` when you need exact WinDbg commands, and capture exception context, loaded modules, and the most relevant threads before opening a disassembler.
3. For the live-runtime path, use `$x64dbg` plus `$cheat-engine-workflow`. Use `$cheat-engine-x64dbg-ida-handoff` when the target workflow explicitly spans Cheat Engine, x64dbg, and IDA. Add `$ret-sync` only after the debugger path is stable enough to justify syncing into a disassembler.
4. Move into static analysis once you know which module, function family, or address range matters. Use `$ida-decompiler-cleanup` for Hex-Rays cleanup, `$binary-ninja-diff-signatures` for Binary Ninja-centered diff/signature work, or `$ghidra-automation-recipes` when Ghidra should be scripted. Use `$apply-callee-type-ex` in IDA, `$peutils` in Binary Ninja, or `$ghidra-bridge` for the narrower helper cases.

### Common Mistakes
### Reference Map
