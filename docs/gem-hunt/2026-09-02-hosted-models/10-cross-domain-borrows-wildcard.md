# Gem-hunt 2026-09-02 / hosted models / lens 10: cross-domain borrows + wildcard

Lens id: `10-cross-domain-borrows-wildcard`
Branch: `gemhunt/hosted-models-10-cross-domain-borrows-wildcard` (from `main` @ `5fa34fda1`)
Mode: discovery only. No code changed. No PR.

Status legend used below:

- **[FACT]** sourced claim, cited with URL + tier + date checked.
- **[INFER]** my inference from sourced facts; can be wrong.
- **[REC]** recommendation for this estate.
- Tier A = primary/official docs, standards bodies, regulators, peer-reviewed. Tier B = reputable secondary
  (vendor engineering blogs, well-maintained OSS READMEs, trade press). Tier C = forum / single blog / model-training
  memory. **UNVERIFIED** = I could not fetch a live source in this run.

## 0. Constraints honoured (estate locks, cited as constraints)

- OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never `ANTHROPIC_BASE_URL`, never a new
  OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA.
- Ports 8765 / 8812 / 8317 are owned.
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials. Never remove a feature to buy reliability; present tradeoffs instead.

Dedup-set (exists, not re-proposed): `hosted-model-agents` skill (live-capture/2026-09-02), `tools/mcp/glm53-space`
(to be deprecated), `auth2api :8317`, `.agents/agents.json` + `.agents/local.json`, installed runtimes on the Win11 box.

## 1. Telecom: least-cost routing + carrier failover

_(pending)_

## 2. Finance: smart order routing + best execution

_(pending)_

## 3. Pharmacy: formulary + therapeutic substitution

_(pending)_

## 4. Aviation: dispatch reliability + MEL/ETOPS

_(pending)_

## 5. Power grid: unit commitment + reserves

_(pending)_

## 6. Wildcard: the find the other lenses would miss

_(pending)_

## 7. Rubric table

_(pending)_

## 8. Ten-line summary

_(pending)_
