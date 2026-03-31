---
name: swfoc-reverse-engineering
description: Use when working on SWFOC editor runtime or native analysis, or on the swfoc_memory dump bundle, especially for dump triage, debugger attach flows, signature generation, binary comparison, import repair, or moving evidence between WinDbg Preview, x64dbg, Cheat Engine, IDA Pro, Binary Ninja, and Ghidra.
---

# SWFOC Reverse Engineering

## Overview

Use this skill for SWFOC-native evidence work: dump triage, runtime tracing, static follow-up, and signature or diff workflows. Keep XML, Lua, MEG packaging, and submod integration in `$swfoc-modding`; use this skill when the question is really about the executable, dump, memory layout, or runtime behavior.

## Workspace Anchors

- Source and trainer workspace: `C:\Users\Prekzursil\Downloads\SWFOC editor`
- Dump and artifact workspace: `C:\Users\Prekzursil\Downloads\swfoc_memory`
- Primary dump artifact: `StarWarsG.DMP`
- Prebuilt evidence pack: `swfoc_memory\chatgpt_pro_bundle\`

## Recommended Workflow

1. Validate the target first. Confirm whether the request is about the SWFOC runtime, a dump artifact, or source-side modding. If it is XML, Lua, or packaging work, hand back to `$swfoc-modding`.
2. For the dump path, start with `$windbg-preview` on `StarWarsG.DMP`. Capture exception context, loaded modules, and the most relevant threads before opening a disassembler.
3. For the live-runtime path, use `$x64dbg` plus Cheat Engine. Add `$ret-sync` only after the debugger path is stable enough to justify syncing into a disassembler.
4. Move into static analysis once you know which module, function family, or address range matters. Use `$apply-callee-type-ex` in IDA, `$peutils` in Binary Ninja, or `$ghidra-bridge` for automation-heavy Ghidra follow-up.
5. When a finding must survive across game builds or variants, export both sides with `$binexport`, compare with `$bindiff`, and generate resilient patterns with `$binja-sigmaker` or a Cheat Engine AOB workflow.
6. Escalate to the existing `$volatility-3` or `$angr` skills only for genuinely memory-forensics-specific extraction or symbolic analysis needs.

## Common Mistakes

- Jumping straight from a dump to random decompiler browsing without first capturing the exception and thread context.
- Mixing modding tasks and runtime RE tasks in one workflow without deciding which artifact is authoritative.
- Treating one-off absolute addresses as stable without diffing or signature work.
- Forgetting to reuse the existing evidence bundle under `swfoc_memory\chatgpt_pro_bundle` before redoing work.

## Reference Map

Read `references/workspace.md` for the local workspace layout, the recommended first-pass commands, and the exact artifact folders that are already present.
