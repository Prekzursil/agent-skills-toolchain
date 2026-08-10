---
name: swfoc-modding
description: "Research-backed workflow for Star Wars: Empire at War / Forces of Corruption modding, SDK/tooling, debugging, and submod integration. Use when Codex needs to implement, troubleshoot, or explain SWFOC mods and submods, including XML/Lua edits, MEG packaging, workshop publishing, MODPATH/STEAMMOD launching, map/model pipelines, file formats (ALO/ALA/MTD/DAT/LUA), or patch/tool compatibility. For dump, runtime, debugger, signature, or native executable analysis, route to $swfoc-reverse-engineering first."
---

# SWFOC Modding

## Overview
Use this skill to work accurately on SWFOC modding tasks with source-grounded procedures instead of guesswork. Prioritize official Petroglyph + Petrolution documentation, then use community sources for practical edge cases.

## Workflow
1. Classify the request.
- Dump files, runtime tracing, debugger attach flows, signature generation, binary diffing, import repair, or MCP-backed disassembler work: use `$swfoc-reverse-engineering` first, with `$reverse-engineering-toolkit` when tool selection is still unclear. For explicit Cheat Engine -> x64dbg -> IDA workflows, use `$cheat-engine-x64dbg-ida-handoff`.
- Launch/setup/workshop/submod routing: read `references/mod-architecture-and-workflow.md`.
- Crashes/performance/weird runtime behavior that still look mod-level rather than native-runtime-level: read `references/debugging-playbook.md`.
- File format or asset pipeline work: read `references/file-formats-and-toolchain.md`.
- Patch/tool compatibility questions: read `references/official-tooling-and-patches.md`.
- Community patterns, AI quirks, forum-established gotchas: read `references/community-knowledge.md`.
- Project-specific context for this workspace: read `references/workspace-mod-notes.md`.

2. Validate time-sensitive facts before acting.
- Run `python3 scripts/check_sources.py` to quickly verify source availability and freshness (`Last-Modified`, `ETag`, status code).
- Treat patch/tool version assumptions as unstable unless verified.

3. Execute changes in the user workspace.

### Source Priority
### Quick Commands
### Verify key URLs and update signals
### Optional: only print non-200 sources
### Inspect a specific source
