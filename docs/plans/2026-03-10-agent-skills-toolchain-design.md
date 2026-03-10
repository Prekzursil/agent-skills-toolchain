# agent-skills-toolchain Design

## Summary

This repo is a private platform for three distinct live surfaces:

- installable skills under `skills/`
- MCP-native tools under `tools/mcp/`
- browser- or web-mediated tools under `tools/web/`

The first shipped live artifact remains `quality-gate-automation-architect`, but it now sits inside a broader platform instead of defining the whole repo identity.

## Key decisions

- Keep the repo private under the personal `Prekzursil` account.
- Rename the repo from `codex-skills-lab` to `agent-skills-toolchain`.
- Keep `skills/`, `tools/mcp/`, and `tools/web/` as separate live surfaces.
- Keep future ideas as incubation docs instead of fake live artifacts.
- Store only derived summaries from prior work, not raw conversation exports.

## Why the tooling is split

MCP-native tooling and browser-mediated tooling are not the same class of system.

MCP-native work is transport- and protocol-oriented. Its core risks tend to be schema drift, auth configuration, runtime compatibility, and tool boundary clarity.

Browser- or web-mediated work is interaction- and session-oriented. Its core risks tend to be login handling, DOM drift, browser setup, page reliability, and higher maintenance cost.

Keeping those surfaces separate prevents the repo from collapsing into a vague `tools/` bucket where auth, runtime, and validation expectations are constantly mixed together.

## Repo structure

- `skills/quality-gate-automation-architect/`
  - live installable skill
  - lean `SKILL.md`
  - modular `references/`
- `tools/mcp/`
  - live home for MCP-native tool projects
- `tools/web/`
  - live home for browser- or web-mediated tool projects
- `docs/incubating/skills/`
  - future skill concepts
- `docs/incubating/tools/`
  - future tool concepts
- `scripts/`
  - repo-level validation helpers

## Codex environment defaults

Use the Codex environment with:

- name `Prekzursil/agent-skills-toolchain`
- description `Private platform repo for the skills, MCP-native tools, and web-agent tooling I use and deploy together. Includes live artifacts, validation helpers, and incubation docs.`
- `universal` container image
- container caching `On`
- agent internet access `On`
- a manual setup script that checks Python, Git, Node, npm, then installs dependencies only when manifests exist for the repo root, `tools/mcp/`, or `tools/web/`

Default non-secret environment variables:

- `PYTHONUNBUFFERED=1`
- `PIP_DISABLE_PIP_VERSION_CHECK=1`
- `GH_PAGER=cat`
- `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`

Default secrets:

- `OPENAI_API_KEY`
- optionally `GH_TOKEN` for explicit CLI- or token-backed GitHub flows

ChatGPT account credentials should not be treated as normal repo-wide env vars. Any web-session handling belongs to the specific tool that needs it.

## Future direction

This repo should grow by promoting repeated, pressure-tested workflows into real skills and by promoting repeated, pressure-tested integrations into real MCP or web tools. The live surfaces stay clean; incubation docs hold the rough ideas until they are ready.
