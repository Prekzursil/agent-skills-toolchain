---
name: swfoc-modding
description: "Research-backed workflow for Star Wars: Empire at War / Forces of Corruption modding, SDK/tooling, debugging, and submod integration. Use when Codex needs to implement, troubleshoot, or explain SWFOC mods and submods, including XML/Lua edits, MEG packaging, workshop publishing, MODPATH/STEAMMOD launching, map/model pipelines, file formats (ALO/ALA/MTD/DAT/LUA), or patch/tool compatibility. For dump, runtime, debugger, signature, or native executable analysis, route to $swfoc-reverse-engineering first."
---

# SWFOC Modding

## Overview
Use this skill to work accurately on SWFOC modding tasks with source-grounded procedures instead of guesswork. Prioritize official Petroglyph + Petrolution documentation, then use community sources for practical edge cases.

## Workflow
1. Classify the request.
- Dump files, runtime tracing, debugger attach flows, signature generation, binary diffing, import repair, or MCP-backed disassembler work: use `$swfoc-reverse-engineering` first, with `$reverse-engineering-toolkit` when tool selection is still unclear.
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
- Apply minimal edits first, then verify with concrete checks (logs, launch params, file placement, script load behavior).
- For submods, preserve upstream mod compatibility and do not mirror/rebundle full parent mods unless explicitly requested.

4. Communicate source confidence.
- Mark official source claims as high confidence.
- Mark forum/wiki guidance as community-derived and version-sensitive.

## Source Priority
1. Official: Petroglyph mod-support + official Steam announcements.
2. Technical documentation: Petrolution mod-tools/docs pages.
3. Community references: Revora/ModDB/Steam guides/Fandom wiki.
4. Local workspace evidence: existing mod/submod layout and files.

## Quick Commands
```bash
# Verify key URLs and update signals
python3 scripts/check_sources.py

# Optional: only print non-200 sources
python3 scripts/check_sources.py --only-errors

# Inspect a specific source
python3 scripts/check_sources.py --filter "petroglyphgames.com/eawmodtool"
```
