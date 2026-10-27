---
name: deep-research
description: Multi-source research with runtime MCP tool inventory, live/down/quota preflight, role-scoped routing, caching, academic consolidation, FACT/RACE-style verification, two-axis source assessment, and grounded cited reports. Use for thorough evidence-backed research, due diligence, technology evaluation, or current-state synthesis.
---

# Deep Research

> **Drift-prone skill.** Provider registrations, tool names, result shapes, and
> quotas change. Never promise provider coverage from this file alone. Obtain a
> fresh MCP `tools/list` inventory, run the provider data probes, then route only
> exact tools that are both configured and live. The policy choke-point is
> `references/research_harness/routing.py`; `preflight.py` catches inventory,
> quota, and freshness drift before dispatch.

The existing spine remains unchanged:

`understand -> plan -> search -> deep-read -> synthesize -> deliver`

Research Harness M-16 adds exact-tool preflight, role-scoped routing, caching,
academic consolidation, claim/evidence validation, bounded reflection, and a
cited Markdown renderer to that spine. It is a small pure Python package, not a
new MCP server or daemon.

## When to Activate

- In-depth research, investigation, or current-state questions
- Competitive analysis, due diligence, market/technology evaluation
- Literature reviews and evidence synthesis
- Questions that need multiple independent sources and explicit uncertainty

## Runtime MCP Tool Contract

Routing stores logical providers plus exact tool names. The configured server
prefix is bound at runtime, so moving tools behind `search-hub`, another lazy
hub, or a direct provider registration does not break policy. A same-name tool
may be exposed as `server__tool` by one client and `mcp__server__tool` by
another; normalize that client wrapper into the inventory boundary, not in the

### Workflow
### Step 1: Scope — write a research brief
### Step 2: Preflight — inventory, probe, then bind
### Step 3: Plan and dispatch with provider roles
### Step 4: Academic path — discover, resolve, read, consolidate
### Step 5: FACT-style claim/evidence table
### Step 5a: Native Anthropic Citations when the execution path exposes them
### Step 6: Synthesize once, in one context
### Step 7: Reflect — targeted gap fill, at most two waves
### Step 8: Fresh external RACE-style verifier
### Step 9: Deliver and persist
