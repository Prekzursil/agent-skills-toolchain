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
