# codex-as-mcp

> **Closed 2026-08-09 — solved upstream, do not promote.** This note used to point at
> `tools/mcp/agent-lanes-codex/` as its promotion target; that tree was deleted with the rest
> of the ChatGPT-web lane. The idea itself is now delivered by OpenAI's own
> `codex mcp-server`, mounted at user scope and reached as `mcp__codex__codex` /
> `mcp__codex__codex-reply`. The questions below are kept as a record of what a repo-local
> build would have had to answer; nothing here is an open work item.

## Goal

Define a clearly bounded MCP-native tool surface that exposes Codex workflows through an MCP-friendly interface.

## Why it belongs here now

This idea is important enough to track, but it is not yet a live runnable tool with settled runtime, auth, or validation boundaries.

## Questions to close before promotion

- What exact Codex capabilities are exposed through MCP
- what auth model the tool expects
- how request and response boundaries are represented
- what the minimum runnable smoke test is
- what must stay out of scope to avoid turning it into a generic remote shell

## Promotion target

The naming direction for promotion is now `Agent Lanes Codex`. Keep this note only as historical incubation context.
