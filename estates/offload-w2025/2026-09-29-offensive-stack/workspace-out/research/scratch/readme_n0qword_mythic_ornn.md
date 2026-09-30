# Mythic Ornn

<p align="center">
  <img src="docs/ornn.png" alt="Ornn fanart" width="300"/>
</p>

LLM-driven generator for Mythic Agents, Payload-Type and C2 Profiles.

Mythic agents are tedious to write by hand: every one re-implements the same wire protocol, payload-type scaffolding, and C2 plumbing. Mythic Ornn skips the boilerplate by turning the official Mythic developer docs into the retrieval layer of a generation pipeline. An LLM consults a local, pruned copy of those docs and emits agents that match the documented message format out of the box.

The pipeline works in two modes, sharing the same docs and the same rules:

- **Prompt mode** — `template/AGENT.md` turns any coding agent into a Mythic developer. You describe an agent, it reads the docs, and it scaffolds or extends a project. This is the interactive, in-editor workflow.
- **Build mode** — `ornn-agent/` is a Mythic payload type that generates other agents from the Mythic UI. Describe an agent, hit build, and the container (LLM + bundled docs + a Python template) returns a runnable payload. It's a payload type that produces payload types.

## Structure

- `mythic-doc/` — pruned copy of the official Mythic docs; the context fed to the model during generation.
- `template/` — `AGENT.md` is the single source of truth for the agent's behavior (build order, container library versions, rules). Tool-agnostic; `template/README.md` covers opencode, Claude Code, Cursor, and plain chat.
- `.opencode/` — thin adapter wiring `template/AGENT.md` into opencode's subagent system.
- `examples/` — drop complete Mythic bundles here; the agent uses them as an alternative reference source alongside the docs.
- `ornn-agent/` — self-contained product built with this setup; bundles the docs inside the container. See `ornn-agent/README.md`.

## Requirements

- Docker + a Mythic install to build and run generated agents
- Any coding agent that can read a markdown prompt file, or an OpenAI-compatible endpoint for build mode

## Attribution

- `mythic-doc/` is a pruned copy of the official Mythic docs (github.com/MythicMeta/Mintlify_Documentation). See `NOTICE` for attribution and license status. Mythic itself is BSD 3-Clause.
- Thanks to Adam Chester([@xpn](https://github.com/xpn)) of SpecterOps for the idea and his post: [Disposable Tooling: Building LLM-Generated Mythic Agents from Prompt to Deployment](https://specterops.io/blog/2026/06/24/disposable-tooling-building-llm-generated-mythic-agents-from-prompt-to-deployment/#)
