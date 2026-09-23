---
name: hexstrike-ai-authorized-engagement
description: Use when routing an authorized security assessment, bug bounty, red-team exercise, or CTF task through the local HexStrike AI runtime ; do NOT use for installation or MCP wiring (use hexstrike-ai-setup or hexstrike-ai-mcp) ; returns HexStrike AI engagement results for authorized targets only.
---

# HexStrike AI Authorized Engagement

## Overview
Use this skill when the user wants HexStrike to drive an explicitly authorized security workflow. The core rule is scope first: ownership, permission, and target boundaries must be explicit before using HexStrike for live testing.

## When to use
- The user asks to run HexStrike against a site, host, API, binary, or challenge target
- The task is a bug bounty, red-team, security research, or CTF workflow and HexStrike is the requested tool
- A user wants help choosing which HexStrike capability to use for a permitted target

## Workflow
1. Confirm the target is user-owned, in-scope, or otherwise explicitly authorized.
2. Confirm the local HexStrike runtime is healthy with the setup skill if needed.
3. Translate the request into explicit HexStrike tool intent: recon, web security, cloud, binary, forensics, orchestration, or — when the approved plan names exact module/options — `metasploit_run`.
4. Keep the engagement bounded to the stated target and report blocked tool availability when the local host is missing required security binaries.

## Metasploit via HexStrike

When `executor_owner` is `hexstrike` and the scope sidecar allows the target,
`metasploit_run` is wired (see `hacktricks` `security-mcp-routing.md`). Requirements:

- Local HexStrike `/health` shows MSF available on the HexStrike host
- Coordinator `ExecutionPlan` lists exact module name, canonical target, bounded options, abort conditions
- Do not use `metasploit_run` in the same phase as the dedicated `metasploit-run` MCP

For full MSF RPC (listeners, sessions, payload generation outside HexStrike's wrapper), use `executor_owner: metasploit` and the `metasploit-run` registry server in a separate phase.

## Stop rules
- Do not use HexStrike for unauthorized targets or vague "test this random site" requests.
- Do not imply coverage that the local toolchain cannot provide; the local `/health` result is the source of truth for available tools.
- Prefer explicit scope and operator intent over broad autonomous scanning.
