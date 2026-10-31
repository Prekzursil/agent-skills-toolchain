---
title: README
type: note
permalink: dqverify-repo-20261013/command-center/ssot/salvaged-from-scratch/tools/web/readme
---

# Web Tools

`tools/web/` is the live home for browser- or session-mediated tooling.

## Current bounded projects

### `agentify-desktop`

- vendored Electron desktop control center source for the installed Agentify Desktop app
- includes the local HTTP/MCP bridge entrypoints, UI, orchestrator helpers, and tests
- excludes bundled build output and `node_modules`

### `agent-lanes-chatgpt-web`

- direct ChatGPT web lane with explicit session, readiness, and lane-routing behavior

### `promptbridge-talk-lane`

Location:

```text
tools/web/promptbridge-talk-lane
```

Purpose:

- expose PromptBridge/Agentify as a talk-only lane
- support discussion and curation roles without turning the web lane into the execution authority
- keep session inspection and configuration explicit and fail-closed when confirmation is missing

Primary tools:

- `promptbridge_discuss`
- `promptbridge_curate`
- readiness/status/session tools
- `agentify_*` aliases for compatibility during `0.1.x`

## Boundary

PromptBridge can discuss and curate. It does not own repo execution.