# Gem-hunt 2026-09-02 / hosted models / lens 01 - native-capability audit

**Lens id:** `01-native-capability-audit`
**Mode:** discovery, ENABLE-not-BUILD. No code changed. One file, committed after each section.
**Question:** for every runtime installed on the Windows 11 box, what does it *natively* offer
for pointing at a custom model provider (OpenAI-compatible base URL, Anthropic-compatible
endpoint, per-model config blocks, provider registries such as models.dev, MCP sampling), and
which of those doors can consume a Hugging Face router / Space / Inference Endpoint or a local
Ollama / LM Studio server with **zero code**? Where a door is bolted shut by an estate lock, say
so, so the integration layer that replaces `tools/mcp/glm53-space` knows where an MCP tool is the
only remaining entrance.

## 0. Grading key, dedup-set and estate locks (read first)

**Confidence grades.** Every sourced claim carries `[A|B|C, corroborated|UNVERIFIED, YYYY-MM]`.
A = official docs or the vendor's own repo/reference page; B = vendor blog, release notes, or a
high-signal third party (models.dev, a maintainer's issue reply); C = community post, forum, or
inference from code. `corroborated` = two independent sources agree; `UNVERIFIED` = one source
only or I could not open the page in this run. The date is the month the source was fetched or
last known updated. Sentences are tagged **[fact]**, **[inference]** or **[recommendation]**.

**Dedup-set (exists, not re-proposed):** (1) skill `.agents/skills/hosted-model-agents` on
`live-capture/2026-09-02` (HF Hub MCP + Spaces + Endpoints, Modal/RunPod/Lightning, Azure
Foundry, llama.cpp, Cursor Max via auth2api); (2) `tools/mcp/glm53-space` on `main`, hardcoded to
`router.huggingface.co/v1` + `zai-org/GLM-5.3`, being DEPRECATED for a general integration layer;
(3) auth2api on `127.0.0.1:8317`, the ONLY Cursor-quota OpenAI-compatible bridge (36 `cursor-*`
model ids), consumed by goose (`GOOSE_PROVIDER goose-cursor-proxy`), grok `config.toml`
`[model."cursor-grok-4.6"]`, and the `fabric-cursor` / `claude-cursor` / `codex-cursor` wrappers
in `~/.local/bin`; (4) registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by
name only in `.agents/local.json`; (5) installed runtimes: claude (Claude Code), codex,
cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider
0.86, ollama, lms (LM Studio), ralph (cargo), basic-memory :8765, agent-mail :8812,
browser-bridge hub :8770; wrappers ai-mode, grok-mode, qwen-space (deprecated pointer),
claude-swap.

**Estate locks (hard constraints, cited as such below, never proposed against):**

| Lock | Consequence for this lens |
|---|---|
| OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | Any "route Claude Code through OpenRouter" or "put OpenRouter into Cursor Models settings" finding is marked **LOCKED**, not recommended. |
| No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | Findings that require a proxy such as LiteLLM to translate protocols are marked **LOCKED**; only the vendor-native door or an MCP tool inside the existing registry qualifies. |
| auth2api `:8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA | I do not propose a second Cursor bridge. I record what an official Cursor `/v1` would replace. |
| Ports 8765 / 8812 / 8317 owned | No new listener may claim them; Ollama (11434) and LM Studio (1234) defaults do not collide. |
| `.agents/skills` is the ONE prompt SSOT (Fabric / Goose consume it) | Provider config lives in each runtime's own file; prompts do not move. |
| Never rotate credentials; never remove a feature to buy reliability | Tradeoffs are presented, nothing is retired in this lens. |

## 1. Method

1. For each runtime, open the current official configuration reference (or the repo README /
   `config` docs where no separate site exists) and record: the config file path, the exact keys
   for (a) OpenAI-compatible base URL + API-key env, (b) Anthropic-compatible endpoint,
   (c) per-model blocks, (d) provider registry (models.dev or similar), (e) MCP sampling
   (server-initiated `sampling/createMessage`), and (f) whether a HF router / Space / Endpoint or
   a local Ollama / LM Studio server can be consumed with zero code.
2. Cross-check against a second source where one exists (release notes, models.dev, the HF
   router docs) and grade.
3. Overlay the estate locks and mark each cell ENABLE / LOCKED / IMPOSSIBLE / MCP-ONLY.
4. Produce the runtime x mechanism matrix and the per-find rubric table.

Sections 2-15 are one runtime each, in the dedup-set order. Section 16 is the matrix, 17 the
Hugging Face and local-server consumption view, 18 the rubric, 19 the summary.

_(Sections below are filled in incrementally; each is committed as it lands.)_
