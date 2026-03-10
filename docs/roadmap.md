# Roadmap

## Now

- Reframe the repo as a combined platform for skills, MCP-native tools, and web-agent tooling.
- Keep `quality-gate-automation-architect` as the first validated live skill.
- Keep the tool surfaces separate because MCP-native and browser-mediated work have different runtime and auth models.
- Keep derived summaries in references and docs without storing raw session artifacts.

## Next skill candidates

### `quality-gate-autofix-planner`

Specialize in turning an existing repo's current checks, failures, and workflow files into a concrete PR-repair implementation plan.

### `coverage-ratchet-playbook`

Specialize in coverage-only uplift strategies, target sizing, and stop rules.

### `debt-burndown-orchestrator`

Specialize in analyzer backlog batching, allowlists, reviewer-only zones, and safe recurring schedules.

### `skill-knowledge-refresh`

Specialize in mining recurring lessons from accepted work and updating skill references with derived summaries only.

## Next tool candidates

### `codex-as-mcp`

Incubate a clearly bounded MCP-native tool surface for exposing Codex workflows through an MCP-friendly interface without confusing it with skill packaging.

### `agentify-web-chatgpt-bridge`

Incubate a browser- or web-mediated tool surface for interacting with the ChatGPT web product without conflating it with MCP-native transport.

## Promotion criteria

Promote an incubation note into a live skill or tool only when:

- the workflow or integration has been used repeatedly
- the failure modes are understood
- the trigger or runtime boundary is clear enough that Codex can load or run the right thing reliably
- the artifact can be pressure-tested, not just described

## Non-goals

- stuffing multiple overlapping workflows into one giant skill
- hiding MCP-native and browser-mediated tooling under one generic bucket
- storing raw transcript or session exports in the repo
- adding scripts before a repeated deterministic task is proven
