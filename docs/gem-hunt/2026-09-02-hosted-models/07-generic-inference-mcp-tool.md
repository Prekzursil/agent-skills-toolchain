# Gem-hunt lens 07 - the generic inference MCP tool that replaces `glm53_chat`

- **Hunt:** `2026-09-02-hosted-models`
- **Lens id:** `07-generic-inference-mcp-tool`
- **Mode:** discovery, design + eval plan only. No code was changed by this lens.
- **Branch:** `gemhunt/hosted-models-07-generic-inference-mcp-tool` (cut from `origin/main` at `5fa34fda`)
- **Author:** Cursor cloud agent, 2026-09-02
- **Status:** IN PROGRESS - sections are pushed as they land; a section that is not listed as DONE
  in the checklist below was not finished when this run ended.

## Section checklist

| # | Section | Status |
|---|---------|--------|
| 0 | Frame, constraints, dedup-set, grading legend | DONE |
| 1 | What `glm53_chat` does today and what a replacement must keep | DONE |
| 2 | Survey: OSS MCP servers that expose OpenAI-compatible / HF endpoints as tools | pending |
| 3 | Alternative: the MCP sampling primitive (and why it is not enough alone) | pending |
| 4 | Hosting: how `tools/mcp/mcp-http-host` should host it once, not per session | pending |
| 5 | Tool surface specification | pending |
| 6 | Error taxonomy with truthful degradation | pending |
| 7 | Eval-harness spec (capability, regression, pass@k, fake endpoints for CI) | pending |
| 8 | Per-find rubric table | pending |
| 9 | Open questions and what this lens did NOT verify | pending |

## Grading legend (applies to every claim below)

- **Tier A** - primary source: the project's own repository, spec, or vendor documentation, read this run.
- **Tier B** - secondary but reputable: maintainer blog, package registry metadata, a widely cited write-up.
- **Tier C** - tertiary: aggregator, directory listing, forum post, or a single uncorroborated page.
- **corroborated** - two or more independent sources agree; **UNVERIFIED** - one source, or inferred from
  repository shape without running the code.
- Every claim is dated with the day it was read (all reads in this file: 2026-09-02 unless stated).
- Each statement is labelled **[FACT]** (sourced), **[INFERENCE]** (derived by this lens), or
  **[RECOMMENDATION]** (what this lens thinks the estate should do).

---

## 0. Frame, constraints and the dedup-set

### 0.1 The question this lens answers

The owner has decided to **deprecate `tools/mcp/glm53-space`** (one MCP tool, `glm53_chat`, hard-wired to
`router.huggingface.co/v1` and the single model `zai-org/GLM-5.3`) and replace it with a **general
integration layer**. This lens asks: *what should the one generic "call a hosted or local chat model"
MCP tool look like, what already exists in the open that we could adopt instead of building, is the MCP
sampling primitive a better fit than a tool at all, how does it get hosted exactly once under the
`mcp-http-host` doctrine, and how would we know it works (evals, fake endpoints, pass@k)?*

Design and eval plan only. Nothing here was built or run against a live model.

### 0.2 Estate locks (hard constraints, cited as given by the hunt brief)

These are inputs to this lens, not findings. Every recommendation below was checked against them.

| Lock | Consequence for this lens |
|------|---------------------------|
| OpenRouter is a spend-capped CLI/Codex sidecar only - never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | The generic tool MAY list an `openrouter` profile as one backend among many for CLI/Codex callers, but this lens does **not** propose an OpenRouter-specific MCP server, and the tool must never be wired so that Cursor or Claude Code route their own traffic through it. |
| No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | Rules out the most common "generic inference" shortcut (a LiteLLM proxy) and every candidate below that embeds LangChain/LangGraph. The tool must be a thin HTTP client, not a router product. |
| auth2api `:8317` stays the only Cursor bridge and retires within 7 days of an official Cursor `/v1` GA | The tool may register `:8317` as a backend **profile** (so a Fabric/Goose caller can reach Cursor-quota models) but must not become a second Cursor bridge and must not re-expose Cursor-quota models to Cursor itself. |
| Ports 8765 / 8812 / 8317 are owned | The shared host for this tool needs its own port; this lens proposes one in section 4 and does not touch the three owned ones. |
| `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it) | Any system-prompt "profile" the tool ships must be a pointer into `.agents/skills`, never a second prompt store inside the MCP server. |
| Never rotate credentials | Secret handling below is name-based (`${HUGGINGFACE_TOKEN}` style, as `.agents/agents.json` already does); no rotation is proposed. |
| Never remove a feature to buy reliability - present trade-offs instead | Section 6 (error taxonomy) presents degradation modes as trade-off tables, not as removed features. |

### 0.3 Dedup-set (already exists; not re-proposed)

| Existing thing | Where | What this lens does with it |
|----------------|-------|-----------------------------|
| Skill `hosted-model-agents` (SKILL.md, environments.md, profiles.md, tool-loop.md, evals.md, recipes/hf-space-openai.md) | branch `live-capture/2026-09-02` | Treated as the **doctrine** this tool must implement. Its hard rule 2 ("an inference URL is not Hub MCP ... do not register every GPU URL in `agents.json` as MCP") is the reason the replacement is **one** generic tool with a model **registry**, not one MCP server per endpoint. Its rule 3 ("the hosted model proposes; the harness executes") decides the tools-passthrough question in section 5. [FACT, Tier A, read this run from `git show origin/live-capture/2026-09-02:skills/hosted-model-agents/SKILL.md`] |
| `tools/mcp/glm53-space` (`glm53_core.py`, `mcp_server.py`, `openai_proxy.py`) | brief says "on main" | **Finding:** the *directory is not present on `origin/main`* (`5fa34fda`) nor on any pushed remote branch (`git ls-tree -r` over every `origin/*` for the string `glm53` returned only registry/test/provenance hits, no `tools/mcp/glm53-space/*` path). Only the **registry entry** `mcp.servers.glm53-space` in `.agents/agents.json` (lines 593-625), its provenance note, and the control-plane tests reference it. The code therefore lives only in an unpushed checkout on the Windows box - exactly the failure mode `CLAUDE.md` warns about ("132 of them hold unpushed commits"). [FACT, Tier A, measured this run] **[RECOMMENDATION]** before deprecating it, push the directory to a branch so its `openai_proxy.py` behaviour can be diffed against the replacement's eval fixtures; deprecating unpushed code loses the only executable spec of what `glm53_chat` accepted. |
| auth2api on `127.0.0.1:8317` | Windows box | A backend profile candidate, see 0.2. Not re-described. |
| Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by name in `.agents/local.json` | main | The **model registry** the tool reads from should be a sibling section of this file (or a file it points at), reusing `requiredEnv` / `credentialNames` / `maxPrivateBytes` conventions that already exist there (`maxPrivateBytes` on line 27 and 713; `credentialNames` throughout). [FACT, Tier A] |
| Installed runtimes (claude, codex, cursor-agent, grok, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, ollama, lms, ralph, basic-memory :8765, agent-mail :8812, browser-bridge :8770) | Windows box | Consumers, not competitors. Section 5 states which of them can call an MCP tool and which need the OpenAI-compatible shim instead. |

### 0.4 One correction to the brief's assumptions

The brief says "no GPU assumed unless you find otherwise". The in-repo audit
`.agents/local-models-audit_2026-08-27.md` line 29 records `nvidia-smi` -> **NVIDIA GeForce RTX 4050 Laptop
GPU, 6141 MiB total, 5762 MiB free**, and lines 36-48 record **Ollama v0.33.0** (OpenAI-compatible,
weights on `D:`, `qwen2.5:7b` present) and **LM Studio** (JIT server, 1 h TTL, headless service) installed
and running. [FACT, Tier A, dated 2026-08-27, corroborated by two sections of the same audit but not
re-measured this run] **[INFERENCE]** the generic tool therefore has two *local* OpenAI-compatible backends
available at zero marginal cost, which changes the eval plan (section 7): a "local smoke" tier can run
against Ollama without any network, and the 6 GB VRAM envelope is a real constraint the registry should
record per model (`fits_local_vram: true|false`).

---

## 1. What `glm53_chat` does today, and what the replacement must keep

Sourced from the registry entry, since the code itself is not on any pushed branch.

- **Surface today.** "Exposes one text-only chat tool with separate `user_prompt` and blank-default editable
  `system_prompt` fields. Never send secrets or raw private transcripts." Transport `stdio`, launched with
  `uv run --locked --directory ...\tools\mcp\glm53-space python mcp_server.py`, env `HUGGINGFACE_TOKEN`
  only, targets `claude` only, tags `approved, claude-only, hosted-inference, owner-requested, stdio`.
  [FACT, Tier A, `.agents/agents.json` lines 593-625]
- **Attachment policy today.** Cursor attaches it by default (`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS =
  CURSOR_DEFAULT_APPROVED_SERVERS | {"glm53-space"}`) but it is *not* one of the "core six" runtime-approved
  servers; tests pin that it uses the locked absolute `uv` path and carries the `owner-requested` tag.
  [FACT, Tier A, `.agents/scripts/merge_generated_cursor_mcp.py` line 141-143;
  `.agents/tests/test_mcp_control_plane_live.py` lines 651-662]
- **Companion shim.** The brief names `openai_proxy.py`, "a mini OpenAI-compatible wrapper". [FACT, Tier C -
  brief only; code UNVERIFIED this run] **[INFERENCE]** this exists because several installed consumers
  (fabric, goose, aider, opencode) speak OpenAI `/v1`, not MCP; the replacement must keep *both* faces or
  those consumers lose the backend.

### 1.1 Keep / change / drop matrix for the replacement

| Property of `glm53_chat` | Keep? | Why |
|--------------------------|-------|-----|
| One tool, not one tool per model | **Keep** | hosted-model-agents rule 2; `mcp-fleet-curation` catalogue pressure. |
| Text-only chat | **Change** -> messages array with optional images left as a declared *unsupported* capability per model (section 5) | Vision models exist on every listed backend; refusing them silently is a truthfulness failure (section 6). |
| Hard-coded `router.huggingface.co/v1` + `zai-org/GLM-5.3` | **Drop** -> model id resolved from a registry | The whole point of the deprecation. |
| `HUGGINGFACE_TOKEN` as the only secret | **Change** -> per-backend `credentialNames` | Ollama needs none; `:8317` needs whatever auth2api wants; HF and Azure differ. |
| Blank-default editable `system_prompt` | **Keep, but as a pointer** | `.agents/skills` is the SSOT; a free-text `system_prompt` stays allowed, a `profile` argument resolves to a skill path. |
| "Never send secrets or raw private transcripts" (a sentence in a description) | **Change** -> an enforced redaction pass with a redaction receipt in the result (section 5.6) | A description is not a control. `tools/mcp/proxy-mcp/redaction.py` already has `redact_obj` / `redact_text` / `_is_sensitive_key` that can be lifted. [FACT, Tier A, file read this run] |
| `stdio`, spawned per session | **Drop** -> one shared HTTP host (section 4) | The estate's measured RAM problem (`mcp-http-host/README.md`: "2037 -> 633 processes", "6 concurrent search-hub stdio copies"). |
| `claude-only` target | **Change** -> `claude`, `codex`, `cursor` via HTTP; CLI consumers via the `/v1` face | Nothing about an inference tool is Claude-specific. |
