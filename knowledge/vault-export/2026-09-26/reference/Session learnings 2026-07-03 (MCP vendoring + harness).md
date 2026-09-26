---
title: Session learnings 2026-07-03 (MCP vendoring + harness)
type: note
permalink: main/reference/session-learnings-2026-07-03-mcp-vendoring-harness
tags:
- learnings
- mcp
- git
- cloud
- gotcha
- self-reflect
---

4 reusable gotchas/patterns from the 2026-07-03 MCP-consolidation + harness session (self-reflect, all approved):

1. **MCP user-scope promotion is Claude-CLOSED-only** (gotcha) — any edit to `~/.claude.json` `mcpServers` (incl. `promote-mcp-userscope.ps1`) MUST run with ALL Claude Code sessions closed: a live session holds `~/.claude.json` in memory and REWRITES it on exit, clobbering external edits. "Make the MCP set load everywhere / no desyncs" is inherently a RESTART action. The promote script guards on a running `claude`; `-Force` bypasses the guard but not the exit-clobber. Dry-run live with `-DryRun -Force` (TEMP preview only) to verify.

2. **Disable SDK progress bars in stdio MCP tools** (gotcha) — a progress bar to STDOUT corrupts a stdio MCP's JSON-RPC stream; pass `progress_bar=False` (e.g. lightning_sdk upload_file).

3. **`git archive` = secret-safe repo-vendoring primitive** (pattern) — `git -C <repo> archive HEAD | tar -x -C <dest>` exports ONLY tracked files → gitignored secrets/venvs/.git excluded by construction. Gate first: `git ls-files | grep -iE 'secret|cookie|token|\.env|\.pem'` clean (a COMMITTED secret would still be archived); re-scan staged before commit.

4. **Verify silent cloud spenders read-only BEFORE alarming** (pattern) — a leftover footprint (SSH artifacts, stale project) is NOT proof of active spend; the feared hourly GCE VM was 0 instances. Confirm at the console (gcloud/az/curl) first.

Relates to: [[MCP fleet expansion 2026-07-03]], [[Workspace hygiene audit + resolution 2026-07-03]] (TIER-D per-file template-vs-rendered hook-merge lesson). PR #22 merged to main.