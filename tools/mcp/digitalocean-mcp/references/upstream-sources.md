---
title: upstream-sources
type: note
permalink: dqverify-repo-20261013/tools/mcp/digitalocean-mcp/references/upstream-sources
---

# Upstream sources

- Selected upstream (user-directed archived repo): https://github.com/digitalocean/digitalocean-mcp
- Archived repo README: `README.md`
- npm package: https://www.npmjs.com/package/@digitalocean/mcp

Key upstream facts used by this wrapper:
- The upstream repository is archived and points to `digitalocean-labs/mcp-digitalocean`, but this wrapper intentionally stays on the archived package because the user asked for that exact upstream.
- The archived package runs locally via `npx @digitalocean/mcp`.
- The archived package uses `DIGITALOCEAN_API_TOKEN` for authentication.
- The archived package documents an App Platform-centric workflow; this wrapper therefore defaults to `--services apps`.