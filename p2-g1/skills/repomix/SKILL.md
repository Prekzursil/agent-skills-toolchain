---
name: repomix
description: Use when packing a repository into an AI-friendly bundle with Repomix, or when exposing Repomix as an MCP server to Codex, Claude Code, or Gemini CLI.
---

# Repomix

## Overview

Use Repomix for two related workflows: packing a codebase into a single AI-friendly artifact, and exposing that same capability as an MCP server. It is useful both for reverse-engineering context capture and for turning large repos into manageable AI inputs.

## Quick Workflow

1. For one-off packaging, run `repomix` or `npx repomix@latest` from the target repository.
2. For MCP mode, register `manifests/repomix.json` with the shared bundle helper.
3. Keep the packed output small by filtering junk, binaries, or generated folders before handing it to an agent.
4. Use Repomix output as a source artifact when creating or testing skills against remote repositories.

## Common Mistakes

- Confusing the normal packaging CLI with the MCP server mode.
- Packing the whole repo without excluding giant generated trees or vendor folders.
- Assuming the packed artifact is self-updating; rerun Repomix after meaningful source changes.

## Reference Map

Read `references/upstream.md` for the upstream MCP examples and Claude Code plugin notes.
