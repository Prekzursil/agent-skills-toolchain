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
| T-14 | **Listener exposed beyond loopback.** Ollama's default is `127.0.0.1:11434`, but binding to `0.0.0.0` (a common copy-paste for Docker/WSL access) exposes an unauthenticated API. SentinelLABS + Censys measured **175,000 exposed Ollama hosts in 130 countries**, ~48% advertising tool-calling, with a criminal resale market ("Operation Bizarre Bazaar"). CVE-2024-37032 "Probllama" (path traversal -> RCE, fixed 0.1.34) and CVE-2026-7482 "Bleeding Llama" (heap OOB read via `/api/create`, <0.17.1, leaks API keys/env/system prompts from memory; `/api/push` exfiltrates) are unauthenticated in default config. LM Studio's server has the same shape. | LAN neighbour or Internet scanner. Precondition: bind to 0.0.0.0 or a Windows firewall exception. | A4, A5, A1 | TB5 | L x H | SentinelLABS/Censys "Silent Brothers", 2026-01-29 `[FACT B, corroborated by The Hacker News 2026-01 and CSA research note 2026, 2026-01-29]` https://www.sentinelone.com/labs/silent-brothers-ollama-hosts-form-anonymous-ai-network-beyond-platform-guardrails/ ; https://thehackernews.com/2026/01/researchers-find-175000-publicly.html ; CVE-2026-7482 details in CSA note `[FACT B, 2026]` https://labs.cloudsecurityalliance.org/research/csa-research-note-llmjacking-evolved-offensive-agentic-20260/. |
| T-15 | **Memory-starvation as a safety failure.** A 31.6 GB box running Cursor + Claude Code + an 8-14B local model + browsers swaps; watchdogs and supervisors (`mcp.supervision.totalIdlePrivateBytes = 6 GiB`) start killing processes, and "kill the wrong process" or "quarantine the safety hook" becomes possible. | None (self-inflicted). | A4 | - | H x M | Registry supervision values `[FACT A, 2026-09-02]`; box size from brief `[FACT C]`. `[INFERENCE]`: any kill switch designed in section 8 must not itself depend on a process that the OOM path kills first. |
| T-16 | **Weights supply chain.** GGUF/safetensors pulled from arbitrary Hub repos; pickled `.pt/.bin` can execute code on load. | Malicious repo author. Precondition: loading non-safetensors formats. | A4 | TB2 | L x H | OWASP LLM03:2025 `[FACT A]`; the repo's own `.agents/skills/llm-security/AGENTS.md` section 3 (safetensors vs pickle) `[FACT A, in-repo]`. |

### 3.5 Path: Cursor quota bridge `auth2api :8317` (`[ESTATE-LOCK]`: stays; retires <=7 days after official Cursor `/v1` GA)

| id | threat | attacker + precondition | asset | TB | L x I | evidence |
|---|---|---|---|---|---|---|
| T-17 | **Local unauthenticated loopback API with a paid quota behind it.** Any local process (including a compromised npm package inside any of the 42 MCP servers' `npx -y ...@latest` launches) can call `127.0.0.1:8317` and burn Cursor quota or use the frontier models as an exfil oracle. | Local malicious code. Precondition: bridge accepts unauthenticated loopback calls (typical for such bridges - **UNVERIFIED** for auth2api specifically; the code is not in this repo). | A5, A3 | TB2 | M x M | Registry: 13 of 42 servers launch via `npx`, 6 of them pinned to `@latest` (`chrome-devtools-mcp@latest`, `@steipete/claude-code-mcp@latest`, ...) - i.e. whatever the registry publishes next is what runs `[FACT A, measured 2026-09-02]`. `[INFERENCE]`. |
| T-18 | **Terms-of-service exposure.** Wrapping a subscription's model access behind an OpenAI-compatible proxy for third-party tools (goose, fabric, aider) is the kind of use vendors restrict. This is a governance risk to A6, not a technical one; the lock says keep it, so the deliverable is a tradeoff statement (8.6), not a removal. | Vendor enforcement. | A6 | - | L x H | `[INFERENCE, UNVERIFIED]` - I did not fetch Cursor's current Terms in this run; flagged for the owner to read the "Acceptable use" section before relying on the bridge for anything that is not personal use. |

### 3.6 Cross-cutting: the "lethal trifecta"

Simon Willison's framing (2025-06-16): an agent that combines (1) access to private data, (2) exposure to untrusted content and (3) the ability to communicate externally can be made to steal the data by content it merely reads; he explicitly lists "make an HTTP request - to an API" as a sufficient exfiltration channel `[FACT B, corroborated by Beurer-Kellner et al. arXiv:2506.08837, 2025-06-16]` https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/. 

`[INFERENCE]` Every path above is ingredient (3) by construction: **the next inference call is itself the outbound channel** - no browser or webhook needed. The agent holds (1) (A1-A3) and consumes (2) (the model's reply, any web page it summarised, any Space output). The minimal control set in section 8 therefore concentrates on breaking (1) at TB1 (redaction + never-send list) and gating (2)->(4) at TB4 (schema + allowlist + human approval for high-impact tools), rather than on detecting injection text - which even OpenRouter ships only as regex matching `[FACT A, 2026-09-02]` https://openrouter.ai/docs/guides/features/guardrails. The pattern-catalogue restatement ("tools missing capability tags must be treated as carrying all three"; "the check is performed by the host, not by guardrail prompts") is the design rule I adopt for the registry in 8.1 `[FACT C, 2025-2026]` https://www.agentpatternscatalog.org/patterns/lethal-trifecta-threat-model/.

## 4. Provider data-retention and training-use policies

Reading rule: "HF: no" means Hugging Face's routing layer; the **downstream provider's** policy still applies. All rows dated 2026-09-02 unless noted. Tier: A = the vendor's own policy/security page; B = OpenRouter's structured reflection of the provider's terms (a second party summarising the first party - useful, not authoritative).

| Provider / path | Stores prompt+completion? | Trains on your data? | Retention window | Controls you get | Source, tier |
|---|---|---|---|---|---|
| **Hugging Face Inference Providers (router)** | No ("We do not store the request body or response when routing requests through Hugging Face") | No ("does not store any user data for training purposes") | Debug logs <=30 days, "no user data or tokens" | Pin provider with `model:provider`; TLS; SOC2 Type 2 Hub; **defers to each provider's policy** | https://huggingface.co/docs/inference-providers/main/en/security `[FACT A, corroborated]` |
| **HF Inference Endpoints (dedicated)** | No payloads/tokens stored | No | Logs 30 days (your own `print`s in custom handlers are logged) | Public / Protected (HF token) / Private (PrivateLink); GDPR DPA on Enterprise | https://huggingface.co/docs/inference-endpoints/security `[FACT A]`; forum clarification by HF staff `[FACT B, 2023]` https://discuss.huggingface.co/t/inference-endpoint-data-privacy/36783 |
| **HF Space run by a stranger** (e.g. `akhaliq/GLM-5.3`) | **Whatever the owner's code does.** Ephemeral disk by default, but the app can push to a dataset repo; public-Space runtime logs are world-readable to any HF user | Owner's choice | Unbounded if persisted | None. Only mitigation: duplicate into your own private Space (copies code + variables, not secrets) and review the code | HF Spaces overview `[FACT A]` https://huggingface.co/docs/hub/spaces-overview ; arXiv 2606.30373 `[FACT B, 2026-06-29]` ; forum `[FACT C]` |
| **Z.ai** (GLM maker, as an OpenRouter provider) | retainsPrompts=false | training=false | - | - | OpenRouter feed, terms https://chat.z.ai/legal-agreement/terms-of-service `[FACT B, UNVERIFIED against Z.ai's own text, 2026-09-02]` |
| **Novita, Nebius Token Factory, Together, Fireworks, SambaNova, Cerebras, Groq, DeepInfra, Baseten, Parasail** (common HF-router and OpenRouter backends) | retainsPrompts=false (all ten) | training=false (all ten) | - | Provider-side ToS links in feed | OpenRouter feed `[FACT B, 2026-09-02]` https://openrouter.ai/api/frontend/v1/all-providers |
| **DeepSeek, Liquid, Thinking Machines (free research tier), NVIDIA (API trial)** | retainsPrompts=true | **training=true** | unspecified | Exclude via `data_collection: "deny"` | OpenRouter feed `[FACT B, 2026-09-02]` |
| **Anthropic, Mistral, Cohere, Meta, SpaceXAI(xAI), Xiaomi, AionLabs, Sourceful, Black Forest Labs, Nex AGI** | retainsPrompts=true | training=false | 30 days | ZDR per model group on OpenRouter for Anthropic | OpenRouter feed `[FACT B]` |
| **Google AI Studio** | retainsPrompts=true | training=false | 55 days | Use Vertex (retainsPrompts=false) instead | OpenRouter feed `[FACT B]` |
| **OpenAI (via OpenRouter)** | retainsPrompts=true | training=false | unspecified in feed (OpenAI's own default is 30 days abuse retention; ZDR is enterprise-approved) | `zdr: true` | OpenRouter feed `[FACT B]`; ZDR summary repo `[FACT C]` https://github.com/abubakarsiddik31/zdr |
| **OpenRouter itself** | Input/output logging **off by default**; if enabled, stored privately, not for training | No | Account setting | `provider.data_collection`, `provider.zdr`, `provider.only/order/allow_fallbacks`, Guardrails, `GET /endpoints/zdr` | https://openrouter.ai/docs/guides/privacy/provider-logging.md `[FACT A]`; https://openrouter.ai/docs/guides/features/guardrails `[FACT A]`; sovereign-AI page `[FACT A]` https://openrouter.ai/docs/guides/features/sovereign-ai |
| **Azure AI Foundry ("Models sold by Azure")** | Stateless inference; abuse-monitoring store may hold **flagged** prompts for human review, per-resource isolated, in-geo | No ("not used to train the AI models or other systems") | Historically "up to 30 days"; the fixed day-count was removed from the doc around 2024-11-18 per Microsoft Q&A | **Modified Abuse Monitoring** (gated application via account team) disables the store; verify `ContentLogging` via `az cognitiveservices account show` | https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy `[FACT A, 2026]`; MS Q&A `[FACT B, 2026]` https://learn.microsoft.com/en-in/answers/questions/5941618/ and https://learn.microsoft.com/en-au/answers/questions/5954113/ |
| **Modal** (as an inference provider) | retainsPrompts=false | training=false | - | For your **own** Modal function, you are the provider: nothing leaves your app unless your code sends it | OpenRouter feed `[FACT B]`; https://modal.com/legal/privacy-policy (not fetched) `[UNVERIFIED]` |
| **RunPod, Lightning AI** (rented GPU you run yourself) | You are the provider | - | - | Same as Modal: your container, your logs; the platform's own privacy policy governs metadata | `[UNVERIFIED - not fetched in this run]`; treat as "self-hosted with a cloud landlord" |
| **Local: Ollama / LM Studio / llama-server** | Nothing leaves the box **if bound to loopback** | - | - | Bind `127.0.0.1`; patch (>=0.17.1 for CVE-2026-7482) | Section 3.4 sources `[FACT B]` |
| **Cursor via auth2api** | Governed by Cursor's privacy mode/terms for the underlying account; the bridge adds a local hop | Per Cursor account settings | Per Cursor | `[ESTATE-LOCK]` | `[UNVERIFIED - Cursor policy not fetched in this run]` |

`[INFERENCE]` The estate's rule "never send secrets or raw private transcripts" is the right default precisely because the retention answer is **route-dependent and changes without notice** (OpenRouter's table is generated live from a JSON feed; HF's page defers to 15+ providers). A control that depends on knowing today's policy is brittle; a control that never sends the sensitive thing is not.

`[RECOMMENDATION]` The generic tool should record, per call, the resolved provider (HF returns it; OpenRouter returns it in `openrouter_metadata` when the opt-in header is set) so the ledger (8.4) can answer "where did this prompt go?" after the fact.

## 5. Token scoping

| Credential | Today (registry) | Tightest native scope available | Gap |
|---|---|---|---|
| `HUGGINGFACE_TOKEN` | One name shared by Hub MCP (write control plane) and `glm53-space` (inference) `[FACT A]` | HF **fine-grained** token with only "Make calls to Inference Providers" (`inference.serverless.write` in HF's token-creation URL) and no repo permissions; HF: "create one access token per app or usage", "using only fine-grained tokens for production usage" | Two tokens needed: `HUGGINGFACE_TOKEN_HUB` (Hub MCP; whatever repo scope the owner needs) and `HUGGINGFACE_TOKEN_INFERENCE` (inference-only). The registry's `credentialNames` convention already supports distinct names; `[ESTATE-LOCK]` never rotate = **add** the second token, do not revoke the first. Source: https://huggingface.co/docs/hub/security-tokens `[FACT A]`; https://huggingface.co/docs/inference-providers/en/index `[FACT A]` |
| HF leaked-token handling | - | `POST https://huggingface.co/api/credentials/revoke` invalidates any token value, no ownership needed, always 202 | Only usable if the owner accepts the lock exception for a **confirmed** leak; otherwise prevention only. `[FACT A]` same page |
| HF billing | Personal PAYG | `X-HF-Bill-To: <org>` header routes billing to an org (Team/Enterprise) - separates spend from identity | Not applicable on a Free plan `[FACT B]` https://convly.ai/hugging-face-token/ |
| OpenRouter key | Sidecar key, spend-capped (`[ESTATE-LOCK]`) | Per-key `limit` + `limit_reset` (daily/weekly/monthly) + `include_byok_in_limit`; readable via `GET /api/v1/key` -> `limit_remaining`; **Guardrail** assigned to the key: provider allowlist, model allowlist, ZDR per group, Secrets preset (redacts `hf_`, `ghp_`, `github_pat_`, `dop_v1_`, `sk-or-v1-`, `sk-ant-`, PEM blocks, JWTs ... with `[SECRET:<format>]`), custom regex redact/block | Verify the sidecar key actually has `limit` set (the lock says spend-capped; `GET /api/v1/key` is the proof). https://openrouter.ai/docs/api_reference/limits.md `[FACT A]`; https://openrouter.ai/docs/guides/features/guardrails/secret-formats.md `[FACT A]` |
| Azure Foundry key | Subscription key | Entra ID RBAC (`Cognitive Services OpenAI User`) instead of key; per-deployment TPM quota; content filter per deployment | `[FACT B, general Azure knowledge, UNVERIFIED in this run]` |
| Modal / RunPod / Lightning tokens | Full-account tokens | Modal: per-environment tokens; RunPod: API key per account; Lightning: user API key | `[UNVERIFIED in this run]` - low priority: these are "you run it" paths where the token controls **compute spend**, not data |
| Cursor session (auth2api) | Whatever the bridge holds | None exposed to the estate; the bridge is the scope | `[ESTATE-LOCK]` - no change; record in ledger only |

`[RECOMMENDATION]` Encode scope in the registry, not in prose: add to each `mcp.servers[*]` / inference-profile entry a `credentialScope` field (e.g. `"HUGGINGFACE_TOKEN_INFERENCE": {"issuer": "huggingface", "permissions": ["inference.serverless.write"]}`) that a check script can compare against the live token (`GET https://huggingface.co/api/whoami-v2` returns `auth.accessToken.role` and fine-grained scopes `[FACT B, UNVERIFIED field names, 2026-09-02]`). Fail closed if the token is `write`-role where the entry declares inference-only.

## 6. Licensing

| Artifact | License | What it permits / requires for this estate | Source |
|---|---|---|---|
| `zai-org/GLM-5.3` weights (the model `glm53-space` is hardcoded to) | Model card: `license: other`, `license_name: glm-5.3`. Text tracks MIT (use/copy/modify/sell/fine-tune) plus clause 2: Model-as-a-Service operators with >US$10B revenue over any 12 months must pass Z.AI security review before commercial use. "AS IS", no warranty. Weights published 2026-08-28 after a two-week hold "once safety evaluation and hardening are complete" (cyber capability "developed faster than we expected"). | A single operator is far below the revenue gate; the practical consequence is only that a registry license check must accept `other/glm-5.3`, and that a red-team persona (dedup skill profiles) runs on a model whose maker flagged offensive-cyber capability. | https://huggingface.co/zai-org/GLM-5.3/raw/main/LICENSE `[FACT A, 2026-08-28]`; README frontmatter `[FACT A]` https://huggingface.co/zai-org/GLM-5.3/blob/main/README.md ; digitalapplied analysis `[FACT C, 2026-08]` https://www.digitalapplied.com/blog/glm-5-3-weights-bespoke-license-not-mit |
| `zai-org/GLM-5.3-Flash` weights | MIT (plain), published 2026-08-26, natively multimodal, 1M context | Drop-in alternative if the license check wants a pure OSI license | `[FACT C, corroborated by two blogs, UNVERIFIED against the model card in this run, 2026-08-26]` https://www.eigent.ai/blog/glm-5-3-flash-multimodal-model |
| `models.dev` registry data + code (`anomalyco/models.dev`, default branch `dev`, MIT, pushed 2026-09-02, 6,679 stars) | MIT for the repo (LICENSE file: "Copyright (c) 2025 models.dev") | The estate may vendor/cache the `api.json` and redistribute it; attribution + license notice required. **Not a policy source**: models.dev carries pricing/context/modalities, not retention/training policy - do not conflate. | GitHub API + raw LICENSE fetched 2026-09-02 `[FACT A]` https://github.com/sst/models.dev (redirects to anomalyco) |
| OpenRouter provider-policy feed (`/api/frontend/v1/all-providers`) | No license stated on the endpoint; it is an internal frontend API | Cache for internal decisions; do not redistribute; treat field names as unstable | `[FACT A that it exists and is unlicensed as of fetch, 2026-09-02]` |
| HF Spaces code you duplicate | Whatever the Space repo declares (often none) | A Space with no LICENSE file is all-rights-reserved by default; duplicating for private use is tolerated by HF's ToS but redistributing is not clearly permitted | `[INFERENCE from copyright default; UNVERIFIED against HF ToS text]` |
| Model outputs | Provider-specific: e.g. GLM-5.3 license disclaims warranty on "OUTPUT AND RESULTS"; Anthropic/OpenAI commercial terms assign output to the customer | Log the model id + provider per call (ledger) so provenance of generated code is recoverable | GLM LICENSE `[FACT A]`; others `[UNVERIFIED in this run]` |
