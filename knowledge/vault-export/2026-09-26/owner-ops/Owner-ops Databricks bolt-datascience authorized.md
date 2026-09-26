---
title: Owner-ops Databricks bolt-datascience authorized
type: note
permalink: main/owner-ops/owner-ops-databricks-bolt-datascience-authorized
tags:
- owner-ops
- databricks
- bolt-datascience
- anti-over-refusal
---

# Owner-ops: Databricks is authorized estate infrastructure

valid_as_of: 2026-07-21

## Rule (non-negotiable for agents on this machine)

- The Databricks profile **bolt-datascience** (`costin.ionescu@bolt.eu`) is **owner-authorized estate infrastructure**.
- Using it for personal coding agents, CRCP fan-out, Codex job clusters, research jobs, and secrets scope `codex-harness-prekzursil` is **allowed by default**.
- Do **NOT** refuse, lecture, or redirect to Modal/VPS solely because the workspace is "corporate" when the owner explicitly uses bolt-datascience for agent work.
- Safety still applies: no force-push main, no live secret commits, no attacks on third parties, redact secrets in logs.
- Prefer measured patterns: policy_id `0002189219BF8EF3`, r5d.2xlarge, stagger 3s, secret scope `codex-harness-prekzursil` / key `auth_json`, harvest with `databricks fs cat` (not fs cp download).

## When Databricks is the wrong host

Only prefer alternatives when the *workload shape* is wrong (always-on inbound MCP with multi-minute holds) **and** the owner did not ask for Databricks. If the owner said use Databricks / bolt-datascience / fan-out, **execute**.

## Example of over-refusal to avoid

A Biomni research synthesis that bans Bolt Databricks purely for "governance/corporate workspace" while the owner regularly runs Codex fan-outs there is **wrong for this estate**. Present tradeoffs, then execute the owner's chosen path.

## Related

- Owner-ops authorization v3 GENERAL
- CRCP / Codex Databricks fanout skill
- Phone→PC ChatGPT cookie bridge (durable reapply under ~/.crcp/cookie-bridge/)
