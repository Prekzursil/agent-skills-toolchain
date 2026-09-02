# Gem-hunt 2026-09-02 / hosted models / lens 09: security and governance of hosted and local model integration

- Lens id: `09-security-governance-hosted-models`
- Kind: discovery (research + findings). No code changed. No PR.
- Branch: `gemhunt/hosted-models-09-security-governance-hosted-models` (cut from `origin/main` at `5fa34fda1`)
- Author: Cursor cloud agent, 2026-09-02
- Status: SKELETON - sections are filled in below in the order listed; each section is committed and pushed as it lands.

## How to read this file

Every claim carries a tag in square brackets:

- `[FACT A|B|C, corroborated|UNVERIFIED, YYYY-MM-DD]` - sourced fact. Tier A = primary source (vendor policy page, standard, source code in this repo); B = reputable secondary (vendor blog, major security-research writeup, well-known press); C = community/forum/single-party claim. `corroborated` = at least two independent sources agree; `UNVERIFIED` = one source or a page I could not fetch live. The date is the date of the source or the date I read it.
- `[INFERENCE]` - my reasoning from sourced facts.
- `[RECOMMENDATION]` - what I think this estate should do.
- `[ESTATE-LOCK]` - a hard constraint from the brief; cited as a constraint, never proposed against.

Sections:

1. Scope, dedup-set and estate locks (what already exists; what this lens must not re-propose)
2. Assets and trust boundaries (what a generic inference tool touches)
3. Threat model (STRIDE-ish, per path: HF providers, HF Spaces run by strangers, OpenRouter providers, local runtimes, Cursor bridge)
4. Provider data-retention and training-use policies (one row per provider, each cited)
5. Token scoping (HF fine-grained tokens, OpenRouter per-key limits, Azure/Modal/RunPod/Lightning)
6. Licensing (model weights, models.dev registry data, Space code)
7. OWASP LLM Top 10 (2025) mapped onto the generic inference tool
8. Minimal control set the registry and tool must enforce (allowlists, redaction, ledger, kill switch)
9. Finds - per-find rubric table
10. Ten-line summary

---

## 1. Scope, dedup-set and estate locks

### 1.1 What this lens covers

The generic inference tool the owner intends to build (the replacement for `glm53-space`) will let local agents (Claude Code, Codex, Cursor, goose, Fabric, aider, opencode) send prompts to third-party inference: Hugging Face Inference Providers and Spaces, OpenRouter (sidecar only), rented GPUs (Modal/RunPod/Lightning), Azure AI Foundry, local llama.cpp/Ollama/LM Studio, and the Cursor quota bridge `auth2api`. This lens asks: what can go wrong when an agent that holds local shell, files and credentials talks to a model it does not control, and what is the smallest set of controls the registry (`.agents/agents.json`) and the tool must enforce.

### 1.2 Dedup-set (exists; not re-proposed here)

| Item | Where I verified it | What it means for this lens |
|---|---|---|
| Skill `hosted-model-agents` | `origin/live-capture/2026-09-02:skills/hosted-model-agents/{SKILL.md,environments.md,profiles.md,tool-loop.md,evals.md,recipes/hf-space-openai.md}` `[FACT A, corroborated, 2026-09-02]` | Already states hard rule 3, "the hosted model proposes; the harness executes ... Shell, files, HexStrike, browsers stay local after allowlist + JSON-schema checks." This lens builds the threat model that justifies that rule and names the controls it is missing (redaction, ledger, kill switch, provider allowlist). |
| `tools/mcp/glm53-space` | **Not present on `origin/main` at `5fa34fda1`** (`git ls-tree -r origin/main | grep glm53` is empty; no fetched branch carries it) `[FACT A, UNVERIFIED as to where the code lives, 2026-09-02]`. It **is** registered in `.agents/agents.json` as server `glm53-space` (stdio, `uv run --locked --directory C:\...\tools\mcp\glm53-space python mcp_server.py`, `env.HUGGINGFACE_TOKEN`, tags `approved, claude-only, hosted-inference, owner-requested, stdio`) `[FACT A, 2026-09-02]`. | The registry already points at a path that the SSOT checkout does not carry - a governance finding in itself (S-08 below). The entry's description carries the estate rule verbatim: "Never send secrets or raw private transcripts." `[FACT A]` |
| `auth2api` on `127.0.0.1:8317` | Brief; `hosted-model-agents` hard rule 5 ("G-32 = ai-mode / *-cursor stay process-local to auth2api :8317; no persistent global Cursor-bridge env"; "G-36 = at most one cursor-agent process") `[FACT A, 2026-09-02]` | Treated as an in-scope trust boundary (section 3.5) but its existence and port are locked. |
| Registry `.agents/agents.json` + `.agents/local.json` | `mcp.servers` = 42 entries; `mcp.policy.toolAllowlist = ["*"]`, `approvalMode = "native"`, `maxPrivateBytes = 512 MiB`; `mcp.supervision = {failureThreshold: 3, failureWindowSeconds: 600, quarantineScope: "session", totalIdlePrivateBytes: 6 GiB}`; secrets referenced only by `credentialNames` / `requiredEnv` / `${VAR}` (18 distinct names, incl. `HUGGINGFACE_TOKEN`) `[FACT A, 2026-09-02]` | The registry already has (a) a wildcard tool allowlist, (b) a process-level quarantine that is a proto-kill-switch, (c) a secrets-by-name convention. The control set in section 8 extends these rather than inventing a new file. |
| Installed runtimes on the Windows 11 box | Brief only (31.6 GB RAM, no GPU assumed) `[FACT C, UNVERIFIED from this VM, 2026-09-02]` | Local runtimes (Ollama, LM Studio, llama.cpp) are in scope for the "local listener exposed" threat (3.4). |

`[INFERENCE]` The `HUGGINGFACE_TOKEN` name is shared by the Hub MCP (`huggingface`, a write-capable control plane: push, Spaces CRUD) and by `glm53-space` (inference only). One credential, two blast radii. This is the single most concrete token-scoping gap I found (S-01).

### 1.3 Estate locks (hard; cited as constraints)

- `[ESTATE-LOCK]` OpenRouter is a spend-capped CLI/Codex sidecar only - never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- `[ESTATE-LOCK]` No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory. Consequence for this lens: **no gateway product** (LiteLLM proxy, Portkey, Helicone self-host, etc.) may be the enforcement point. Controls must live in the registry schema, in the one generic tool's process, or in provider-native features (OpenRouter Guardrails, HF fine-grained tokens, Azure content filters).
- `[ESTATE-LOCK]` `auth2api :8317` stays the only Cursor bridge and retires within 7 days of an official Cursor `/v1` GA. Ports 8765/8812/8317 are owned.
- `[ESTATE-LOCK]` `.agents/skills` is the one prompt SSOT (Fabric/Goose consume it). Consequence: any "system prompt hardening" text proposed below is a skill/prompt-pack edit, not a new file elsewhere.
- `[ESTATE-LOCK]` Never rotate credentials. Consequence: the classic incident response to a leaked token (rotate) is off the table by rule, which **raises** the value of prevention (scoped tokens, redaction, ledger) and of provider-side revocation-free controls (per-key spend caps, allowlists). Tradeoff stated in 8.6.
- `[ESTATE-LOCK]` Never remove a feature to buy reliability; present tradeoffs instead.

## 2. Assets and trust boundaries

### 2.1 Assets the generic inference tool can expose or damage

| # | Asset | Where it lives | How a hosted-model call can touch it |
|---|---|---|---|
| A1 | Provider credentials (`HUGGINGFACE_TOKEN`, OpenRouter key, Azure key, Modal/RunPod tokens) | `.agents/local.json`, process env, `~/.local/bin` wrappers | Sent as bearer to the correct host (intended); leaked if the model or a Space redirects the base URL, or if the agent pastes env into a prompt. |
| A2 | 17 other registry credentials (`GH_TOKEN`, `GITHUB_MCP_PAT`, `DIGITALOCEAN_API_TOKEN`, `LINKEDIN_*`, `SENTRY_*`, ...) `[FACT A, 2026-09-02]` | same | Exfiltrated if an injected instruction makes the agent read env/`local.json` and include it in the next prompt. |
| A3 | Private transcripts, repo contents, `basic-memory` notes (:8765), `agent-mail` messages (:8812) | local services + files | Sent to a third party as "context" by a helpful agent; the estate rule forbids raw private transcripts. |
| A4 | Local execution (shell, files, browser-bridge :8770, HexStrike, Cheat Engine bridge) | the harness | Driven by `tool_calls` proposed by a remote model - the "hosted model proposes; harness executes" boundary. |
| A5 | Money / quota | HF PAYG credits, OpenRouter credits, Azure subscription, Cursor plan quota via auth2api | Unbounded consumption (OWASP LLM10) by a runaway loop or a model that emits enormous outputs. |
| A6 | Reputation / ToS standing | Cursor account, HF account | A bridge that violates a vendor's terms, or a Space that violates HF content rules, can cost an account. |
| A7 | Integrity of the SSOT | `.agents/skills`, `agents.json` | A model-suggested edit to a skill file is a supply-chain write into every consumer (Fabric, Goose). |

### 2.2 Trust boundaries (numbered; referenced by the threat table)

```
[Local agent process]--TB1-->[generic inference tool]--TB2-->[HF router / OpenRouter / Space / Endpoint / Azure / auth2api]--TB3-->[actual GPU provider or Space owner]
        ^                                                             |
        |<---------------------- TB4 (model output / tool_calls) -----+
[Local runtimes: Ollama, LM Studio, llama-server]--TB5 (loopback vs 0.0.0.0)-->[LAN / internet]
```

- TB1: the agent decides what context goes into the prompt. This is where redaction and the "never send secrets or raw private transcripts" rule must be enforced mechanically, because the model cannot enforce it.
- TB2: the tool decides which base URL and which model id it will call. This is where the allowlist lives.
- TB3: the router decides which downstream provider serves the request. HF says it does not store bodies but defers to each provider's policy `[FACT A, 2026-09-02]` (section 4); OpenRouter exposes per-provider policy as data and lets you filter on it `[FACT A, 2026-09-02]` (section 4). A Space is different: the Space owner is the provider, and there is no policy at all unless they publish one.
- TB4: everything that comes back is untrusted input. Tool-call arguments are attacker-influenced strings until validated against the tool's JSON schema and the local allowlist.
- TB5: local runtimes are only "private" if they listen on loopback.

`[INFERENCE]` The dedup skill's hard rule 3 covers TB4. Nothing in the dedup-set covers TB1 (redaction), TB2 (base-URL/model allowlist) or TB3 (provider policy filter) mechanically; they are covered only by prose ("Never send secrets or raw private transcripts").

## 3. Threat model

Format: `T-nn | path | threat | attacker + precondition | asset | boundary | likelihood x impact (H/M/L) | evidence`. "Likelihood" is for **this** estate (single operator, agents with shell, memory-starved box, credentials as env vars), not the industry in general.

### 3.1 Path: HF Inference Providers (`router.huggingface.co/v1`, what `glm53-space` uses today)

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-01 | **Indirect prompt injection via model output.** The model (or the provider serving it) returns text or `tool_calls` that instruct the local agent to read `local.json`/env and send it back in the next turn, or to run a shell command. | Any party that can influence the model's weights or the provider's serving stack; or, more realistically, any web page / file the agent summarised earlier whose text reached the model. Precondition: agent auto-executes tool calls or follows "instructions" in output. | A1, A2, A4 | TB4 | M x H | OWASP LLM01:2025 `[FACT A, 2025]` https://genai.owasp.org/llm-top-10/ ; dedup skill hard rule 3 is the existing mitigation `[FACT A]`. |
| T-02 | **Downstream provider retention/training.** HF says it does not store bodies and keeps 30-day logs without user data, but explicitly defers to "the Data Security Policies of each provider". The request lands on Novita / Nebius / Together / Fireworks / SambaNova / Cerebras / Groq / Z.ai etc. depending on routing. | Passive: the provider's own retention and training terms. Precondition: `provider="auto"` (default) or an unchecked provider. | A3 | TB3 | H x M | HF Inference Providers Security page `[FACT A, corroborated by HF Endpoints security page, 2026-09-02]` https://huggingface.co/docs/inference-providers/main/en/security ; per-provider policies in section 4. |
| T-03 | **Over-scoped token.** `HUGGINGFACE_TOKEN` is used both by the write-capable Hub MCP and by the inference tool. A leak from the inference path (log, crash dump, pasted transcript) gives write on every repo/Space the account can write. | Anyone who obtains the token. Precondition: a `read`/`write` role token rather than a fine-grained "Make calls to Inference Providers"-only token. | A1, A7 | TB1/TB2 | M x H | HF token roles doc: fine-grained tokens exist and HF "recommend[s] using only fine-grained tokens for production usage" `[FACT A, 2026-09-02]` https://huggingface.co/docs/hub/security-tokens ; inference permission name "Make calls to Inference Providers" `[FACT A, corroborated, 2026-09-02]` https://huggingface.co/docs/inference-providers/en/index ; registry shows one shared name `[FACT A]`. |
| T-04 | **Unbounded consumption.** PAYG credits burn from a runaway agent loop or a 100k-token completion; free-tier credits are tiny (HF publishes $0.10/month free, $2 PRO `[FACT B, UNVERIFIED against HF pricing page, 2026-09-02]` https://convly.ai/hugging-face-token/). | Bug or injected loop. Precondition: no per-call `max_tokens`, no per-session budget. | A5 | TB2 | M x M | OWASP LLM10:2025 `[FACT A]`; HF Enterprise page lists "Usage & billing control" as a paid-plan feature only `[FACT A, 2026-09-02]` https://huggingface.co/docs/hub/enterprise. |
| T-05 | **Model/route substitution.** A model id like `zai-org/GLM-5.3` may be served by several providers with different quantisation and different data policies; the caller cannot tell which unless it pins `:provider`. | Passive. Precondition: unpinned provider. | A3, A6 | TB3 | H x L | HF router supports `model:provider` suffix (documented in the HF Inference Providers index page I fetched) `[FACT A, 2026-09-02]`. |

### 3.2 Path: HF Spaces run by strangers (e.g. `akhaliq/GLM-5.3`, any Space exposing `/v1` or Gradio)

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-06 | **Space owner reads everything.** The Space is the owner's web server; the code can log, persist to a dataset repo, or forward every prompt. No policy exists unless the owner writes one; a private duplicate only hides it from third parties, not from the owner of the original. | The Space author (or anyone who compromised the Space). Precondition: you send anything you would not post publicly. | A3, A1 | TB3 | H x H | HF forum answer (community, consistent with HF docs) `[FACT C, corroborated by arXiv study, 2026]` https://discuss.huggingface.co/t/streamlit-spaces-safe-to-upload-data/174242 ; Spaces overview: duplicated Spaces are private by default; secrets vs variables `[FACT A, 2026-09-02]` https://huggingface.co/docs/hub/spaces-overview. |
| T-07 | **World-readable runtime logs on public Spaces.** Any HF user can mint a JWT for any public Space and read its runtime logs; logs contain prompts and printed secrets; HF masks only `hf_` tokens. Measured over 972,546 apps (Sep 2024-Dec 2025): 936 apps leaking credentials via logs, 1,442 input-injection candidates, 139,475 on outdated Gradio with known RCE, 27 backdoored. Bug bounties paid by HF ($2,369) indicate HF accepted at least some reports. | Any HF account holder. Precondition: the Space `print`s requests (common in demo code) and is public. | A3, A2 | TB3 | M x H | arXiv 2606.30373 "Your Space is My Zone", published 2026-06-29 `[FACT B, UNVERIFIED whether HF has since fixed log ACLs, 2026-06-29]` https://arxiv.org/html/2606.30373 ; HF forum thread on per-user isolation `[FACT C, 2023]` https://discuss.huggingface.co/t/per-user-isolation-in-spaces/43369. |
| T-08 | **Shared container state across users.** One Space container serves all users; files written by one request are readable by the next. | Other users of the same Space. Precondition: the Space writes request-derived files. | A3 | TB3 | M x M | HF forum demonstration (`echo "secret" > testfile` / `cat testfile` across users) `[FACT C, 2023]` https://discuss.huggingface.co/t/per-user-isolation-in-spaces/43369. |
| T-09 | **Supply-chain via duplication.** Duplicating a Space copies its code (variables are copied, secrets are not). A backdoored Space propagates through cloning; 27 such Spaces were found, some persisting >1 year. | Malicious Space author. Precondition: owner duplicates a stranger's Space to "make it private". | A1, A4 | TB3 | L x H | arXiv 2606.30373 `[FACT B, 2026-06-29]`; Spaces overview on what duplication copies `[FACT A]`. |
| T-10 | **Space `/v1` is an unauthenticated public endpoint.** A stranger's Space is `Public` (no auth). The agent's `Authorization: Bearer hf_...` header, if the OpenAI SDK is pointed at the Space with `api_key=HF_TOKEN`, is delivered to the Space owner's server in plaintext. | The Space owner. Precondition: reusing `HUGGINGFACE_TOKEN` as the `api_key` for a Space base URL (a natural mistake when swapping base URLs). | A1 | TB2 | M x H | `[INFERENCE]` from HF Endpoint types (Public = no auth) https://huggingface.co/docs/inference-endpoints/security `[FACT A]` and OpenAI-SDK behaviour (always sends the bearer). |

### 3.3 Path: OpenRouter (sidecar only, `[ESTATE-LOCK]`)

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-11 | **Provider training/retention behind the router.** 83 providers as of today; four are flagged "may train" (DeepSeek, Liquid, Thinking Machines, NVIDIA) and ~35 retain prompts (30-55 days or unspecified). OpenRouter says it "reflect[s] those policies in structured data on each AI endpoint" and routes to trainers unless you opt out. | Passive. Precondition: account default allows training providers; no `data_collection: deny` / `zdr: true`. | A3 | TB3 | H x M | OpenRouter provider-logging doc `[FACT A, 2026-09-02]` https://openrouter.ai/docs/guides/privacy/provider-logging.md ; live feed `https://openrouter.ai/api/frontend/v1/all-providers` fetched 2026-09-02 (83 rows; counts above are from that fetch) `[FACT A, 2026-09-02]`. |
| T-12 | **Key over-spend / key theft.** An OpenRouter key without a credit `limit` spends the whole balance. | Anyone with the key; runaway loop. | A5 | TB2 | M x M | OpenRouter Limits: per-key `limit`, `limit_reset`, `limit_remaining`, `include_byok_in_limit` via `GET /api/v1/key` `[FACT A, 2026-09-02]` https://openrouter.ai/docs/api_reference/limits.md. |
| T-13 | **Lock erosion.** Convenience pressure to make OpenRouter the Cursor BYOK key, a Claude `ANTHROPIC_BASE_URL`, or a new MCP. | Internal. | A6 | - | M x M | `[ESTATE-LOCK]` - cited as a constraint. The `openrouter-routing` skill already encodes it (dedup skill text) `[FACT A]`. |

### 3.4 Path: local runtimes (Ollama, LM Studio `lms`, llama-server) on the Windows 11 box

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-14 | **Listener exposed beyond loopback.** Ollama's default is `127.0.0.1:11434`, but `OLLAMA_HOST=0.0.0.0` (a common copy-paste for Docker/WSL access) exposes an unauthenticated API to the LAN/Internet; Ollama has had RCE/path-traversal CVEs and internet-exposed instances are routinely indexed. | LAN neighbour or Internet scanner. Precondition: bind to 0.0.0.0 or Windows firewall exception. | A4, A5 | TB5 | L x H | See section 7 (LLM03/LLM06) for sources `[FACT B, corroborated, 2024-2025]`. |
| T-15 | **Memory-starvation as a safety failure.** A 31.6 GB box running Cursor + Claude Code + an 8-14B local model + browsers swaps; watchdogs and supervisors (`mcp.supervision.totalIdlePrivateBytes = 6 GiB`) start killing processes, and "kill the wrong process" or "quarantine the safety hook" becomes possible. | None (self-inflicted). | A4 | - | H x M | Registry supervision values `[FACT A, 2026-09-02]`; box size from brief `[FACT C]`. `[INFERENCE]`: any kill switch designed in section 8 must not itself depend on a process that the OOM path kills first. |
| T-16 | **Weights supply chain.** GGUF/safetensors pulled from arbitrary Hub repos; pickled `.pt/.bin` can execute code on load. | Malicious repo author. Precondition: loading non-safetensors formats. | A4 | TB2 | L x H | OWASP LLM03:2025 `[FACT A]`; the repo's own `.agents/skills/llm-security/AGENTS.md` section 3 (safetensors vs pickle) `[FACT A, in-repo]`. |

### 3.5 Path: Cursor quota bridge `auth2api :8317` (`[ESTATE-LOCK]`: stays; retires <=7 days after official Cursor `/v1` GA)

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-17 | **Local unauthenticated loopback API with a paid quota behind it.** Any local process (including a compromised npm package inside any of the 42 MCP servers' `npx -y ...@latest` launches) can call `127.0.0.1:8317` and burn Cursor quota or use the frontier models as an exfil oracle. | Local malicious code. Precondition: bridge accepts unauthenticated loopback calls (typical for such bridges - **UNVERIFIED** for auth2api specifically; the code is not in this repo). | A5, A3 | TB2 | M x M | Registry: at least 8 servers launch via `npx -y <pkg>@latest` `[FACT A, 2026-09-02]` (`chrome-devtools-mcp@latest`, `@steipete/claude-code-mcp@latest`, ...). `[INFERENCE]`. |
| T-18 | **Terms-of-service exposure.** Wrapping a subscription's model access behind an OpenAI-compatible proxy for third-party tools (goose, fabric, aider) is the kind of use vendors restrict. This is a governance risk to A6, not a technical one; the lock says keep it, so the deliverable is a tradeoff statement (8.6), not a removal. | Vendor enforcement. | A6 | - | L x H | `[INFERENCE, UNVERIFIED]` - I did not fetch Cursor's current Terms in this run; flagged for the owner to read the "Acceptable use" section before relying on the bridge for anything that is not personal use. |

### 3.6 Cross-cutting: the "lethal trifecta"

`[INFERENCE, grounded in OWASP LLM01/LLM02/LLM06]` Every path above becomes an exfiltration channel when three things coincide in one agent turn: (1) access to private data (A1-A3), (2) exposure to untrusted content (a web page, a Space's reply, a model's output), (3) a way to send data out (the next inference call itself is an outbound channel - no browser needed). The generic inference tool is, by construction, ingredient (3). The minimal control set in section 8 therefore concentrates on breaking (1) at TB1 (redaction, never-send list) and gating (2)->(4) at TB4 (schema + allowlist + human approval for high-impact tools), rather than trying to detect injection text, which OpenRouter itself implements only as regex `[FACT A, 2026-09-02]` https://openrouter.ai/docs/guides/features/guardrails.
