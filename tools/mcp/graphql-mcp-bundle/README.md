---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/graphql-mcp-bundle/readme
---

# GraphQL MCP Bundle

Minimal manifest bundle for wiring `blurrah/mcp-graphql` into Codex, Claude Code, and Gemini CLI.

This bundle intentionally reuses the shared registration helper at:

- `tools/mcp/reverse-engineering-mcp-bundle/scripts/register_mcp_server.py`

## Default assumption

If no GraphQL endpoint is provided by the operator, use:

- `http://localhost:4000/graphql`

## Example registration

```powershell
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client codex --manifest .\tools\mcp\graphql-mcp-bundle\manifests\mcp-graphql.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client claude --manifest .\tools\mcp\graphql-mcp-bundle\manifests\mcp-graphql.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client gemini --manifest .\tools\mcp\graphql-mcp-bundle\manifests\mcp-graphql.json
```