---
name: mcp-graphql
description: Use when installing or configuring blurrah/mcp-graphql for Codex, Claude Code, or Gemini CLI, or when an MCP client needs GraphQL schema introspection and query execution against a known endpoint.
---

# MCP GraphQL

## Overview

Use `mcp-graphql` when an MCP client should talk to a GraphQL API through schema introspection and query execution. Treat the endpoint and headers as deployment-specific inputs; if no endpoint is provided, use the upstream default and make that explicit.

## Quick Workflow

1. Confirm the target GraphQL endpoint before changing client configs. If nothing is specified, default to `http://localhost:4000/graphql` and note that assumption.
2. Register the server as a stdio MCP using `npx mcp-graphql` plus environment variables such as `ENDPOINT`, optional `HEADERS`, optional `SCHEMA`, and optional `ALLOW_MUTATIONS`.
3. Keep mutations disabled unless the user explicitly asks for them.
4. Verify the MCP registration in Codex, Claude Code, and Gemini after writing the config entry.
5. Revisit the endpoint env var whenever the target GraphQL service changes.

## Common Mistakes

- Adding the MCP entry without setting `ENDPOINT`, then assuming the server will target the intended API.
- Enabling mutations by default for convenience.
- Treating one project's headers or schema path as reusable across all GraphQL targets.

## Reference Map

Read `references/upstream.md` for the upstream environment-variable contract and the manual client config shape.
