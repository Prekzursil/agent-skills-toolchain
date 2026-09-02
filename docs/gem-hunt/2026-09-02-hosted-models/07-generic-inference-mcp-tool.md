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
| 2 | Survey: OSS MCP servers that expose OpenAI-compatible / HF endpoints as tools | DONE |
| 3 | Alternative: the MCP sampling primitive (and why it is not enough alone) | DONE - deprecated upstream 2026-07-28 |
| 4 | Hosting: how `tools/mcp/mcp-http-host` should host it once, not per session | DONE |
| 5 | Tool surface specification | DONE |
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

---

## 2. Survey: OSS MCP servers that expose OpenAI-compatible / HF endpoints as tools

Method: candidates named from prior knowledge and one web search, then **every repository's metadata was
pulled from the GitHub REST API this run** (`gh api repos/<owner>/<repo>` - license SPDX id, stars,
`pushed_at`, archived flag, language, open issues). Those seven fields are Tier A, dated 2026-09-02. Source
reads are noted per row; anything not read is marked UNVERIFIED.

### 2.1 Direct competitors: "call a chat model as an MCP tool"

| Project | License | Stars | Last push | Lang | What it exposes | Fit for us |
|---------|---------|-------|-----------|------|-----------------|------------|
| [pyroprompts/any-chat-completions-mcp](https://github.com/pyroprompts/any-chat-completions-mcp) | MIT | 160 | **2025-05-01** | JS/TS | ONE tool `chat-with-<name>` per process; provider fixed by env (`AI_CHAT_BASE_URL`, `AI_CHAT_KEY`, `AI_CHAT_MODEL`, `AI_CHAT_NAME`, optional `AI_CHAT_SYSTEM_PROMPT`, `AI_CHAT_TIMEOUT`); input is a single `content` string. [FACT, Tier A - `src/index.ts` and `package.json` read this run] | Closest published match to `glm53_chat`, and it has the **same architectural defect**: one model = one process, so N models = N stdio children per session. Pins `@modelcontextprotocol/sdk` **0.6.0** (pre-Streamable-HTTP), 16 months without a push. Loads `dotenv` from cwd. No messages array, no tools, no usage/cost, no redaction. **Adopt: NO. Learn from: its 40-line shape proves how little code the wire needs.** |
| [pierrebrunelle/mcp-server-openai](https://github.com/pierrebrunelle/mcp-server-openai) | MIT | 84 | 2024-11-28 | Python | OpenAI-only `ask-openai` tool. [Tier A metadata; code UNVERIFIED] | Vendor-fixed, 21 months stale. NO. |
| [mzxrai/mcp-openai](https://github.com/mzxrai/mcp-openai) | MIT | 76 | 2024-12-06 | JS | OpenAI-only. [Tier A metadata; code UNVERIFIED] | Vendor-fixed, stale. NO. |
| [sammcj/mcp-llm](https://github.com/sammcj/mcp-llm) | MIT | 78 | 2025-03-15 | JS | `generate_code`, `generate_documentation`, `ask_question` via LlamaIndexTS over any provider. [Tier A metadata; Tier C description from README summary, UNVERIFIED] | Embeds a framework (LlamaIndex) - brushes the "no second orchestration runtime" lock; task-shaped tools, not a generic chat surface. NO. |
| [rawveg/ollama-mcp](https://github.com/rawveg/ollama-mcp) | **AGPL-3.0** | 170 | 2026-08-13 | TS | Ollama-native tools (list/pull/chat). [Tier A metadata; code UNVERIFIED] | Actively maintained but **AGPL** - fine to *run*, a licence question the moment any of it is vendored into this MIT-style repo. Ollama-only. NO as the generic layer; a possible reference for the local profile. |
| [NightTrek/Ollama-mcp](https://github.com/NightTrek/Ollama-mcp) | **none** | 74 | 2025-01-01 | JS | Ollama-native. [Tier A metadata] | No licence = cannot adopt. NO. |
| [infinitimeless/LMStudio-MCP](https://github.com/infinitimeless/LMStudio-MCP) | MIT | 168 | 2026-04-10 | Python | LM Studio chat/list via its OpenAI-compatible port. [Tier A metadata; code UNVERIFIED] | Vendor-fixed to LM Studio; but recent, MIT, Python - a candidate to **read** for the LM Studio profile's quirks (JIT load, TTL). NO as the layer. |
| [shreyaskarnik/huggingface-mcp-server](https://github.com/shreyaskarnik/huggingface-mcp-server) | MIT | 72 | 2025-03-19 | Python | Hub search/metadata, not inference. [Tier A metadata] | Wrong layer (Hub control plane; the estate already has the official Hub MCP). NO. |

**[INFERENCE, corroborated by the seven rows above]** Every published "LLM as a tool" MCP server in this
class is (a) one provider per process, (b) text-in/text-out, (c) silent on usage, cost and redaction, and
(d) mostly stale (5 of 7 last pushed before 2025-06). None reads a *registry* of models, none ships an eval
harness, none runs as a shared HTTP host. The gap the owner identified is real and un-filled upstream.
The correct posture is therefore **BUILD a thin house server (stdlib Python, house style) that adopts the
40-line wire shape of any-chat-completions-mcp and adds the registry, ledger, redaction and evals** -
not adopt-and-fork.

### 2.2 Adjacent, inverse-direction projects (do not confuse with the target)

| Project | License | Stars | Last push | What it is | Relevance |
|---------|---------|-------|-----------|------------|-----------|
| [SecretiveShell/MCP-Bridge](https://github.com/SecretiveShell/MCP-Bridge) | MIT | 929 | 2025-12-08 | Python; exposes **MCP tools to OpenAI-compatible clients** (the inverse: OpenAI API in, MCP tools out). [Tier A metadata; behaviour Tier C from README summary, UNVERIFIED] | Relevant to the `/v1` **face** (section 5.8): fabric/goose/aider speak OpenAI `/v1`, not MCP. But it is a full FastAPI app with its own config schema - heavier than the house `openai_proxy.py` it would replace. Watch, do not adopt. |
| [bartolli/mcp-llm-bridge](https://github.com/bartolli/mcp-llm-bridge) | MIT | 333 | 2025-03-28 | **archived** | Dead. Listed only so nobody re-proposes it. |
| [punkpeye/mcp-proxy](https://github.com/punkpeye/mcp-proxy) | MIT | 285 | 2026-08-26 | TS stdio<->HTTP bridge | **Already the adopted transport** in `tools/mcp/mcp-http-host` (README, RESCOPE.md). Section 4 uses it. |
| [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) | MIT | 2734 | 2026-07-20 | **Python** stdio<->SSE/HTTP bridge | The no-Node alternative to punkpeye's; **10x the stars**, `uv`-installable. Worth naming because the house `-Bridge stdlib` fallback exists precisely for "npx was failing on this box" days. [Tier A metadata; feature set UNVERIFIED this run] |
| [huggingface/hf-mcp-server](https://github.com/huggingface/hf-mcp-server) (redirect from `evalstate/hf-mcp-server`) | MIT | 289 | **2026-09-01** | TS; the source of the official `https://huggingface.co/mcp` server already registered as `huggingface` in `agents.json` | Control plane (search, papers, Spaces). Its Gradio-Space-as-tool mounting is the one *native* path to "a Space's chat model as an MCP tool" without new code - but it is per-Space and Gradio-shaped, not OpenAI-`/v1`-shaped, so it does not replace the generic layer. [Tier A metadata; tool list UNVERIFIED this run] |
| [PrefectHQ/fastmcp](https://github.com/PrefectHQ/fastmcp) (redirect from `jlowin/fastmcp`) | Apache-2.0 | 27,481 | 2026-09-02 | Python MCP framework | Would give the house server `ctx.sample()` plus a **sampling fallback handler** - but see section 3: sampling is now deprecated, so the framework buys little here, and the house style is stdlib. Not adopted; named so its `sampling_handler` idea is on record. [Tier A metadata; fallback-handler feature Tier C, UNVERIFIED] |

### 2.3 Security posture summary of the class (what to copy, what to avoid)

- **Secrets:** all seven direct competitors take the API key from an environment variable - the same
  pattern `.agents/agents.json` uses (`"env": {"HUGGINGFACE_TOKEN": "${HUGGINGFACE_TOKEN}"}`). None logs
  the key. any-chat-completions-mcp additionally calls `dotenv.config()`, which reads a `.env` from the
  *current working directory* - a footgun when the same process is launched from many session cwds.
  [FACT, Tier A for any-chat-completions-mcp; Tier C for the rest]
- **Input validation:** any-chat-completions-mcp does `String(request.params.arguments?.content)` and then
  `if (!content) throw` - `String(undefined)` is the truthy string `"undefined"`, so a missing argument is
  sent to the model as the literal prompt "undefined". [FACT, Tier A, code read this run] Copy the
  intent, not the check.
- **Egress:** none pins the base URL to an allowlist; the URL is whatever the env says. For this estate
  the base URL must come from the **registry**, never from a tool argument (section 5.2), or an injected
  prompt can exfiltrate a transcript to an attacker's `/v1`.
- **Transport:** all are stdio-only at the version pinned; none ships Streamable HTTP natively, which is
  why the shared-host doctrine (section 4) has to wrap them - or the house server should speak Streamable
  HTTP itself.

---

## 3. Alternative: the MCP sampling primitive - and why it cannot be the answer here

**What sampling is.** `sampling/createMessage` lets a *server* ask the *client's* model for a completion,
"with no server API keys necessary"; the client keeps model selection and must offer human-in-the-loop
review. Revision 2025-11-25 added tool use inside sampling (`sampling.tools` capability, `toolChoice`,
strict tool_use/tool_result balancing) and model preference hints. [FACT, Tier A,
https://modelcontextprotocol.io/specification/2025-11-25/client/sampling, read this run]

**Why it looked attractive for this lens.** A sampling-based server would need zero credentials and zero
registry: the *host's* model answers. That is exactly the "use my Cursor/Claude quota" wish that produced
auth2api.

**Three facts that close the door:**

1. **The primitive is deprecated.** Protocol revision **2026-07-28** marks Sampling *deprecated* under
   SEP-2577: "New implementations SHOULD NOT adopt it; existing implementations SHOULD migrate to
   integrating directly with LLM provider APIs." It stays in the spec for at least twelve months before it
   is eligible for removal. `includeContext` values are separately deprecated (SEP-2596). [FACT, Tier A,
   https://modelcontextprotocol.io/specification/2026-07-28/client/sampling, read this run]
2. **The estate's main client never implemented it.** anthropics/claude-code issue
   [#1785](https://github.com/anthropics/claude-code/issues/1785) ("Support for MCP Sampling") is open
   (last updated 2026-05-20) and the spec-compliance tracker
   [#31893](https://github.com/anthropics/claude-code/issues/31893) lists sampling as **"not
   implemented"**. [FACT, Tier A, both issues read this run] Cursor's and Codex's sampling support was
   **not verified** this run; given (1) it no longer matters.
3. **It cannot do the job even where it works.** Sampling routes to *the client's* model. The purpose of
   this tool is to reach models the client does *not* have - GLM on the HF router, a Space, Ollama on the
   4050, Foundry. Sampling is by construction the wrong direction. [INFERENCE]

**[RECOMMENDATION]** Do not build on sampling. Do not add a FastMCP dependency for `ctx.sample()`. The
replacement is a **tool** whose server holds the credentials (by name, from `.agents/local.json`) and calls
provider HTTP directly - which is precisely what the 2026-07-28 spec now tells implementers to do.

**One thing worth keeping from the sampling spec** (as design input, not as protocol): its
tool-loop rules - "every assistant `tool_use` MUST be followed by a user message of only `tool_result`s,
one per `toolUseId`", "implement iteration limits" - are a clean statement of the invariants the harness
side of `hosted-model-agents/tool-loop.md` already enforces informally. Section 5.4 adopts them as
validation rules for the messages the tool accepts.

---

## 4. Hosting: one shared instance under the `mcp-http-host` doctrine, never one per session

### 4.1 What the doctrine already says (in-repo, Tier A)

- The estate's measured RAM failure is **per-session stdio duplication**: `S` sessions x `H` stdio servers;
  6 concurrent `search-hub` copies were caught live; the cure named is "shared HTTP MCP". [FACT,
  `tools/mcp/mcp-http-host/README.md` "The problem it cures"]
- The adopted transport is `mcp-proxy` npm (pinned `--host 127.0.0.1`, `--shell`), the house value is the
  **supervisor** `run_host.ps1` (port-scoped children-first reap, `-Status` spawn-count invariant,
  `-InstallTask` logon task `McpHttpHost-<Port>`), and `mcp_http_host.py` is the no-Node fallback.
  [FACT, README + RESCOPE.md]
- **"A strongly stateful server should instead expose its own native streamable-HTTP mode (like
  agent-mail / basic-memory) and be run once - don't share a stateful stdio child."** and "Single pipe =>
  serialized round-trips ... a throughput-bound server wants native HTTP concurrency." [FACT, README
  "Scope & honest caveats"]
- Claude Code registers an HTTP server as `{"type": "http", "url": "http://127.0.0.1:<port>/mcp"}`;
  `type` is mandatory. [FACT, README citing code.claude.com/docs/en/mcp]
- The 2025-11-25 spec requires Streamable-HTTP servers to answer **HTTP 403 for invalid `Origin`
  headers**, and lets stdio servers log freely on stderr. [FACT, Tier A,
  https://modelcontextprotocol.io/specification/2025-11-25/changelog, minor changes 1 and 3]

### 4.2 Decision: native Streamable HTTP, not "stdio behind mcp-proxy"

**[RECOMMENDATION]** The replacement - call it **`inference-hub`** to match `search-hub` / `social-hub` /
`cloud-hub` - should be written as a **native Streamable-HTTP server** (stdlib `http.server` +
`ThreadingHTTPServer`, the same toolbox `mcp_http_host.py` already uses) rather than a stdio server wrapped
by mcp-proxy. Reasons, each traceable to a fact above:

| Concern | stdio child behind mcp-proxy | Native HTTP `inference-hub` |
|---------|------------------------------|-----------------------------|
| Concurrency | one pipe, lock-serialized: a 60 s GLM call blocks every other session's call | thread-per-request, bounded by a semaphore (proposed default **4** in-flight provider calls) so a slow provider never head-of-line-blocks Ollama |
| Runtime | needs Node/npx on the box (README: "npx spawns were failing on this box earlier") | Python only; same interpreter family as every other hub |
| Second face (`/v1`) | impossible through mcp-proxy | same process serves `/mcp` **and** `/v1/chat/completions` (section 5.8) |
| Supervision | `run_host.ps1 -Bridge mcp-proxy` | `run_host.ps1` gains a third mode or the hub ships its own `-InstallTask` (the supervisor's reap/status logic is port-scoped and reusable as-is) |

Trade-off stated, per the "never remove a feature" lock: writing Streamable HTTP by hand means owning
session-id handling and SSE framing (~200 lines; the repo already has a working reference in
`_fake_streamable_http_daemon.py`, which implements sessions, `-32600 Session not found`, JSON/SSE and GET
streams as a **test fixture** - [FACT, README "Files" table]). The alternative (stdio + mcp-proxy) is
zero-code on the transport but forfeits concurrency and the `/v1` face.

### 4.3 Placement, port, registry entry

- **Bind:** `127.0.0.1` only (house rule; both existing shared daemons do this).
- **Port:** the three owned ports (8765, 8812, 8317) are untouched; ports already referenced in repo config
  are 8089, 7820, 8766, 8767, 8770, 8799, 8888, 8890, 9222, 18787 (grep of `.agents/agents.json`,
  `tools/mcp/*/README.md`, `docs/plans/*.md` this run). **Proposed: `8901`**, adjacent to the `8900`
  used as the worked example in the mcp-http-host README, to be confirmed free on-box with
  `Get-NetTCPConnection -LocalPort 8901` before any apply. [INFERENCE on free-ness; UNVERIFIED on-box]
- **Registry entry** (`.agents/agents.json` -> `mcp.servers.inference-hub`), reusing existing keys only:
  `transport: "http"`, `url: "http://127.0.0.1:8901/mcp"`, `targets: ["claude","codex","cursor"]`,
  `requiredEnv: []` on the *client* side (credentials live in the hub process, not in each client),
  `maxPrivateBytes: 268435456` (256 MiB; a stdlib Python server idles far below that - [INFERENCE]),
  tags `approved, http, hosted-inference, shared-daemon`. The `glm53-space` entry is then flipped
  `enabled: false` with a `description` pointing here, and removed from `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`
  in the same change so `test_glm53_uses_locked_absolute_uv_and_is_owner_requested_default` is retired
  deliberately, not broken.
- **Cursor client caveat, inherited from basic-memory:** the repo already documents that Cursor does not
  survive a shared daemon restart (stale `mcp-session-id` -> `-32600`, `ECONNREFUSED`) and shipped a
  per-session stdio shim (`bm_cursor_http_session.py`) for `:8765`. [FACT, README "Basic Memory" section]
  **[RECOMMENDATION]** `inference-hub` should be *lenient on unknown session ids* (treat an unknown
  `Mcp-Session-Id` as a fresh implicit `initialize` instead of `-32600`) because it holds **no
  per-session state** - which sidesteps the shim entirely. Trade-off: this deviates from the strict
  reading of the spec (which says 404 for a terminated session) in exchange for restart-transparency;
  it is safe *only* because the hub is stateless per call.

### 4.4 The invariant the supervisor must be able to check

`GET /healthz` returns `{host_pid, started_at, requests_served, inflight, ledger_lines_today,
backends: {<id>: {last_ok_at, last_error_class, consecutive_failures}}}`. `run_host.ps1 -Status` checks
exactly one process owns `:8901` (the existing spawn-count invariant) and that `/healthz` answers. This is
the same shape the README specifies for the stdlib host (`host_pid`, `child_spawn_count`,
`requests_served`) minus `child_*` because there is no child. [FACT for the shape; RECOMMENDATION for
the backend block]

---

## 5. Tool surface specification

### 5.1 Catalogue size: three tools, one of them optional

`mcp-fleet-curation` pressure and hosted-model-agents rule 2 both say: do not let the model catalogue leak
into the tool catalogue. So the *models* are data, the *tools* are fixed:

| Tool | Purpose | Read-only? |
|------|---------|-----------|
| `inference_models` | list registry entries the caller may use, with capability manifest, health, and today's spend | yes |
| `inference_chat` | one model round: messages (+ optional tools/schemas) in, assistant message (+ optional tool_calls / structured object) out | no (spends money) |
| `inference_fetch` | fetch the remainder of a result that exceeded `max_result_chars` (chunked mode, 5.5) | yes |

Tool names follow the 2025-11-25 tool-name guidance (SEP-986: lowercase, `_`-separated, stable).
[FACT, Tier A, changelog item 4; exact guidance text UNVERIFIED this run]

### 5.2 `inference_chat` input schema (JSON Schema 2020-12, the spec default per SEP-1613)

```json
{
  "type": "object",
  "required": ["model", "messages"],
  "additionalProperties": false,
  "properties": {
    "model":     {"type": "string", "description": "Registry id from inference_models (e.g. 'hf/glm-5.3', 'ollama/qwen2.5-7b'). NOT a URL. NOT a provider model name."},
    "messages":  {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/message"}},
    "profile":   {"type": "string", "description": "Optional system-prompt profile = a path under .agents/skills (e.g. 'hosted-model-agents/profiles.md#red-team-reporter'). Resolved server-side; the file text becomes messages[0]. Mutually exclusive with a leading system message."},
    "tools":     {"type": "array", "items": {"$ref": "#/$defs/openai_function_tool"}, "description": "Schemas the MODEL may propose calls to. The hub NEVER executes them (hosted-model-agents rule 3)."},
    "tool_choice": {"enum": ["auto", "none", "required"], "default": "auto"},
    "response_schema": {"type": "object", "description": "JSON Schema the assistant content must satisfy. See 5.4 for native vs prompted mode."},
    "max_tokens": {"type": "integer", "minimum": 1},
    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
    "reasoning_effort": {"enum": ["none", "low", "medium", "high", "max"]},
    "content_class": {"enum": ["public", "internal", "private"], "default": "internal", "description": "Data classification of the messages. 'private' is refused for third-party backends unless the registry entry says private_ok."},
    "allow_redacted_send": {"type": "boolean", "default": false, "description": "If a secret is detected, send with masking instead of refusing."},
    "max_result_chars": {"type": "integer", "default": 20000, "description": "Chunk threshold; overflow is spooled and returned via inference_fetch."},
    "timeout_s": {"type": "integer", "default": 120, "maximum": 600},
    "idempotency_key": {"type": "string", "description": "Optional; identical key within 10 min returns the ledger'd result instead of re-spending."}
  }
}
```

**Deliberately absent:** `base_url`, `api_key`, `provider`, `headers`. Every network destination comes
from the registry entry named by `model`. This is the single most important security property (section
2.3: a base URL in a tool argument is a transcript-exfiltration primitive under prompt injection).
[RECOMMENDATION, grounded in the llm-security AGENTS.md rules on SSRF/allow-listing]

### 5.3 The model registry (`.agents/models.json`, new file, house-owned)

One entry per *routable model*, not per endpoint:

```json
{
  "hf/glm-5.3": {
    "backend": {"kind": "openai-compatible", "base_url": "https://router.huggingface.co/v1",
                "auth": {"header": "Authorization", "scheme": "Bearer", "credentialName": "HUGGINGFACE_TOKEN"},
                "extra_headers": {}},
    "provider_model": "zai-org/GLM-5.3",
    "capabilities": {"tools": true, "tool_choice": true, "json_schema": "unknown", "vision_base64": false,
                     "vision_url": false, "streaming": true, "usage": true, "reasoning_effort": false,
                     "max_context": null},
    "data_class": "third_party", "private_ok": false,
    "limits": {"daily_usd_cap": 0.50, "max_tokens_default": 2048, "timeout_s": 120, "max_inflight": 2},
    "pricing": {"input_per_mtok_usd": null, "output_per_mtok_usd": null,
                "source": "https://huggingface.co/docs/inference-providers/pricing", "as_of": "2026-09-02",
                "note": "HF passes provider prices through with no markup; per-model price must be filled from the provider page."},
    "tags": ["hosted", "replaces:glm53_chat"]
  },
  "ollama/qwen2.5-7b": {
    "backend": {"kind": "openai-compatible", "base_url": "http://127.0.0.1:11434/v1", "auth": null},
    "provider_model": "qwen2.5:7b",
    "capabilities": {"tools": true, "tool_choice": false, "json_schema": true, "vision_base64": true,
                     "vision_url": false, "streaming": true, "usage": true, "reasoning_effort": true,
                     "max_context": "modelfile:num_ctx"},
    "data_class": "local", "private_ok": true, "fits_local_vram": true,
    "limits": {"daily_usd_cap": 0, "timeout_s": 300, "max_inflight": 1},
    "pricing": {"input_per_mtok_usd": 0, "output_per_mtok_usd": 0, "source": "local", "as_of": "2026-09-02"}
  }
}
```

The Ollama capability row is **sourced**, not guessed: Ollama's OpenAI-compatibility page lists
`/v1/chat/completions` as supporting streaming, JSON mode, vision (base64 only, *not* image URL), tools,
`response_format`, `stream_options`/`include_usage`, `reasoning_effort` (`none|low|medium|high|max`) -
and **not** `tool_choice`, `logprobs`, `logit_bias`, `n`; context size cannot be set over the OpenAI
API and needs a Modelfile `num_ctx`. [FACT, Tier A, https://docs.ollama.com/api/openai-compatibility,
read this run] The HF row's `json_schema: "unknown"` is honest: it was not verified this run and is
provider-dependent behind the router. Registry values are what the **capability evals** (section 7)
exist to turn from `"unknown"` into `true|false`.

Secrets are **by name only** (`credentialName`), resolved from the process environment that
`.agents/local.json` populates - the same mechanism as every other `agents.json` entry. Never rotated,
never written to the ledger. **Lock check:** an `openrouter/*` entry is allowed *only* with
`deny_callers: ["cursor", "claude-code"]` and a hard `daily_usd_cap`, which keeps OpenRouter a CLI/Codex
sidecar; a `cursor/*` entry pointing at `http://127.0.0.1:8317/v1` is allowed *only* with
`deny_callers: ["cursor"]` and `enabled: false` by default (the hub is then a *client* of auth2api, not a
second bridge; when auth2api retires, the entries retire with it). Both are presented as trade-offs, not
defaults.

### 5.4 Tools passthrough: schemas in, proposals out, execution never

- `tools` are forwarded verbatim to backends whose manifest says `tools: true`; for others the hub returns
  `error.class = "UNSUPPORTED_CAPABILITY"` with `detail: "tools"` (section 6) rather than silently dropping
  them.
- The hub performs **exactly one model round**. If the model answers with `tool_calls`, they are returned
  as `structuredContent.tool_calls` (ids, names, JSON-parsed arguments, plus `arguments_raw` when parsing
  fails) and the caller - Claude/Cursor/Codex - executes locally after its own allowlist and re-invokes
  `inference_chat` with the `role: tool` messages appended. No loop lives in the hub. This is
  hosted-model-agents rule 3 made structural, and it keeps the hub out of "second orchestration runtime"
  territory.
- Input validation borrowed from the (now deprecated, still correct) sampling spec: every assistant
  `tool_calls` message must be followed by `role: tool` messages covering each `tool_call_id` before any
  other content; violations are returned as **tool-execution errors, not protocol errors**, so the model can
  self-correct (SEP-1303). [FACT for SEP-1303, Tier A changelog; RECOMMENDATION for applying it here]

### 5.5 Structured output: three truthfully-labelled modes

| `structured_mode` in result | When | What the hub does |
|-----------------------------|------|-------------------|
| `native` | manifest `json_schema: true` | sends `response_format: {type: json_schema, json_schema: {...strict}}`; validates the reply anyway |
| `prompted` | manifest `json_schema: false` or `"unknown"` | appends a schema instruction to the system message, extracts the first JSON object, validates; on failure returns the raw text **and** `structured.valid: false` with validator errors |
| `unsupported` | caller asked for `response_schema` and `allow_prompted_fallback: false` | error `UNSUPPORTED_CAPABILITY` |

The result always says which mode ran. Reporting `prompted` as if it were `native` would be the
truthfulness failure the error taxonomy exists to prevent.

### 5.6 Streaming vs chunked results

- **Facts that decide it:** an MCP tool call returns one result; progress is a separate notification that
  Claude Code **ignores** ("no progress display for long-running tools", issue #31893 table) [FACT, Tier A];
  durable "tasks" with polling are **experimental** in 2025-11-25 (SEP-1686) [FACT, Tier A changelog].
- **Design:** the hub *always* consumes the provider's SSE stream internally (`stream: true`,
  `stream_options.include_usage`) so it can (a) record `ttfb_ms`, (b) enforce `timeout_s` with a
  **partial result** instead of nothing (`finish_reason: "timeout_partial"`, `partial: true`), and (c)
  stop at `max_result_chars`. It returns **one** result. If the text exceeds `max_result_chars`, the
  remainder is spooled to `<run-dir>/inference-hub/results/<result_id>.txt` (0600, TTL 24 h) and the
  result carries `truncated: true, result_id, remaining_chars`; `inference_fetch(result_id, offset)` pages
  it. MCP Tasks are the future replacement for this once Claude Code implements them; the registry gets a
  `tasks: false` client note until then. [RECOMMENDATION]

### 5.7 Cost ledger: one JSONL line per call, never the text

Precedent: `tools/mcp/_shared/hardening.py` writes `shadow/confirm-gate.jsonl`, bounded at 256 KiB with
rotate-once. [FACT, Tier A, lines 373 and 424] Same shape here, `inference-hub/ledger.jsonl`, daily
rotation:

```json
{"ts":"2026-09-02T04:11:02Z","call_id":"c_01J...","caller":"claude-code/2.1.x","model":"hf/glm-5.3",
 "provider_model":"zai-org/GLM-5.3","prompt_tokens":812,"completion_tokens":233,"cached_tokens":0,
 "usage_source":"provider","ttfb_ms":1490,"latency_ms":6120,"cost_usd":null,
 "cost_basis":"unknown_price","status":"ok","finish_reason":"stop","structured_mode":"prompted",
 "redaction":{"secrets_masked":0,"refused":false},"content_class":"internal","idempotent_replay":false}
```

`cost_basis` is one of `provider_reported | table_estimate | unknown_price | local_zero`. **Fact that
forces this field:** Hugging Face documents pass-through pricing, monthly credits ($0.10 free /
$2.00 PRO, "subject to change"), a usage breakdown page, and an `X-HF-Bill-To` header - but the pricing
page does not document any per-response cost field, so cost must be *estimated from a table* or marked
unknown. [FACT for the documented items, Tier A, https://huggingface.co/docs/inference-providers/pricing;
absence of a cost field is INFERENCE from that page only, UNVERIFIED against the router's actual
response headers.] `usage_source` is `provider` when the backend returned `usage`, else
`estimated_chars/4`. `caller` comes from the MCP `initialize` `clientInfo`, never from a tool argument.
`inference_models` surfaces `spent_today_usd` per model from this ledger, and `BUDGET_EXCEEDED` (section 6)
is computed from it.

### 5.8 Redaction of secrets and private transcripts

- **Secrets, pre-send:** every string in `messages` is scanned with the estate's existing
  `tools/mcp/proxy-mcp/redaction.py` primitives (`_is_sensitive_key`, `redact_obj`, `redact_text` -
  [FACT, Tier A, file read this run]) extended with the token shapes the llm-security rule lists
  (`AKIA...`, `sk-...`, `ghp_...`, `hf_...`, `-----BEGIN ... PRIVATE KEY-----`, `Bearer <20+ chars>`).
  **Default is refuse, not mask:** `error.class = "REFUSED_SECRET_IN_PROMPT"` with the *kind* and
  *message index* of each hit, never the value. `allow_redacted_send: true` switches to masking and the
  ledger records `secrets_masked: n`. Rationale: silently sending a masked transcript to a third party
  still leaks its shape; the caller should decide knowingly.
- **Private transcripts:** `content_class: "private"` is refused for any model whose registry
  `data_class` is `third_party` unless `private_ok: true` (`REFUSED_PRIVATE_TO_THIRD_PARTY`). `local`
  backends (Ollama, LM Studio) accept everything. This turns the `glm53-space` description sentence
  "never send raw private transcripts" into a check.
- **Post-receive:** the assistant text is scanned too; a secret *echoed back* by the model is masked in
  the returned result and flagged `redaction.echo_masked: n` (models do regurgitate what they were sent).
- **Never in the ledger, never in logs:** prompt text, completion text, headers. stderr logging is allowed
  by the spec for stdio servers; the hub is HTTP, so it logs to a file with the same rule.

### 5.9 The second face: OpenAI-compatible `/v1` on the same process

Installed consumers that cannot speak MCP but speak OpenAI `/v1`: fabric 1.4.470, goose 1.47 (already
configured against `:8317`), aider 0.86, opencode, gemini CLI (for local models). [FACT for the install
list, brief; protocol support per tool UNVERIFIED this run] `openai_proxy.py` in glm53-space exists for
exactly this. **[RECOMMENDATION]** keep the face, move it in-process: `POST /v1/chat/completions` and
`GET /v1/models` on `:8901`, where `model` is the **registry id** and everything else (redaction,
ledger, caps, capability errors mapped to OpenAI `error.code`) is the same code path. This is what the
brief calls the "general integration layer": one process, two faces, one registry, one ledger.
Lock check: this face must never be configured as a Cursor BYOK base URL or a Claude `ANTHROPIC_BASE_URL`;
`deny_callers` cannot be enforced on an anonymous `/v1` client, so the `/v1` face **omits** any
`cursor/*` and `openrouter/*` entries entirely (they are MCP-face only, where `clientInfo` is known).
