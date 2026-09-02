# Gem-hunt lens 03 - OpenRouter as the spend-capped sidecar

Date: 2026-09-02. Lens id: `03-openrouter-sidecar`. Branch: `gemhunt/hosted-models-03-openrouter-sidecar`.
Mode: discovery only (research + findings). No code changed. No PR.

## 0. Scope, method and grading key

This lens answers one question: **what is the current OpenRouter API surface, how does each
installed runtime that is ALLOWED to use it consume it today, and what should the estate's
spend-capped sidecar policy be** - without violating any estate lock.

Grading key used on every claim:

- **Tier A** = primary vendor documentation or the vendor's own API response (e.g. `openrouter.ai/docs`,
  a runtime's official docs/README). **Tier B** = vendor blog/changelog, first-party GitHub issues,
  or well-known secondary references. **Tier C** = community posts, third-party summaries.
- **corroborated** = two or more independent sources agree; **UNVERIFIED** = single source or not
  re-checked live in this session.
- Every claim is dated with the date the source was read (all read 2026-09-02 unless stated).
- Labels: `[FACT]` sourced fact, `[INFER]` inference from facts, `[REC]` recommendation.

Estate locks are quoted as constraints in section 1 and are never proposed to be violated.

Sections below are appended incrementally; each push is a checkpoint (runs die at ~12 min).

## 1. Estate constraints this lens must respect (from the task brief and the repo)

These are quoted as hard constraints. Nothing below proposes violating them.

| # | Lock (verbatim intent from the brief) | Where it already lives in the repo | Status |
| --- | --- | --- | --- |
| L1 | OpenRouter is a **spend-capped CLI/Codex sidecar only** - never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | `.agents/skills/openrouter-routing/SKILL.md` ("Never Cursor BYOK", "Claude Code footgun", "Do not add an OpenRouter MCP") | `[FACT]` in-repo, Tier A (repo file), read 2026-09-02 |
| L2 | No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | same skill: "Do not install LiteLLM"; `openrouter-complete-surface_2026-08-27.md` SKIP rows for LiteLLM, Agent SDK, Hermes Agent | `[FACT]` in-repo |
| L3 | `auth2api :8317` stays the ONLY Cursor bridge, retires within 7 days of an official Cursor `/v1` GA | brief (DEDUP-SET item 3) | constraint, not re-examined here |
| L4 | Ports 8765 / 8812 / 8317 are owned (basic-memory, agent-mail, auth2api) | brief | constraint: this lens proposes **no** new listener on any port |
| L5 | `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it) | `.agents/AGENTS.md` "Universal harness share (HARD)" | `[FACT]` in-repo |
| L6 | Never rotate credentials; never mint new secrets from an agent session | `openrouter-routing/SKILL.md` "Do not mint new secrets from an agent session"; brief | `[FACT]` in-repo |
| L7 | Never remove a feature to buy reliability - present trade-offs | brief | method rule for section 4 |

### 1.1 What already exists (so this lens does not re-propose it)

`[FACT]` The repo already carries a full OpenRouter doctrine, all dated 2026-08-27 (Tier A repo files):

- `.agents/skills/openrouter-routing/SKILL.md` - key location by name only (`OPENROUTER_API_KEY` env + `.agents/local.json` pointer), T0/T1/T2 one-way escalation, suffix table (`:floor`, `:nitro`, `:exacto`, `:online` deprecated), Batch API note, Claude footgun, Codex **named non-default** provider (`wire_api = "responses"`), spend-cap checklist (per-key `limit` XOR `limit_reset`, workspace budgets = Enterprise), free/test slugs, Hermes low-refusal lane, probe commands.
- `.agents/skills/openrouter-routing/openrouter-complete-surface_2026-08-27.md` - 38-source audit: OpenAPI 77 paths / 101 ops, live catalog 417 models / 17 `:free` / 348 tool-capable / 103 providers, error-code table, NATIVE-vs-BUILD-vs-SKIP for every official integration, "we would have missed X" list.
- `.agents/skills/openrouter-routing/openrouter-free-models_2026-08-27.md` and `openrouter-apps-hermes-uncensored_2026-08-27.md` - free-slug snapshot and Hermes evidence.
- `.agents/scripts/openrouter-complete.py` / `.ps1` - the thin T0 chat-completions probe with `--show-limits` and generation-id cost readback.
- Live account facts recorded there (2026-08-27): inference key `limit=null` (uncapped), `is_free_tier=false`, credits ~$319.4 purchased vs ~$319.79 used (**slightly overdrawn**, paid T0 returned 402).

`[INFER]` Therefore the gap this lens fills is **not** "what is OpenRouter"; it is (a) what changed in the six days since 2026-08-27 and which of those claims re-verify live today, (b) how the **other allowed runtimes** (Fabric, Aider, OpenCode, Goose, Grok CLI, Gemini CLI) actually bind to OpenRouter per their current docs - the 08-27 audit only covered Codex and one Aider line, and (c) a **per-runtime key-scoping and cap** design that the 08-27 audit deferred to "user clicks".

## 2. OpenRouter API surface as of 2026-09 (sourced)

All items below were re-read live on 2026-09-02 (Tier A: `openrouter.ai/docs` pages fetched by curl, and the
**public, unauthenticated** `GET https://openrouter.ai/api/v1/models`). Where a rendered number was stripped
by the page's HTML tags, the value from the 2026-08-27 in-repo audit is quoted and marked UNVERIFIED-live.

### 2.1 Models endpoint and metadata - what changed since 2026-08-27

`[FACT]` Live `GET /api/v1/models` (no key needed) on 2026-09-02: **420** models (08-27: 417), **18** `:free`
ids (08-27: 17), **21** zero-priced rows, **354** with `tools` in `supported_parameters` (08-27: 348), **336**
`structured_outputs`, **361** `response_format`. Source: https://openrouter.ai/api/v1/models - Tier A live,
corroborated against the 08-27 in-repo snapshot for direction of drift.

`[FACT]` Each model row now carries these top-level keys: `architecture`, **`benchmarks`**, `canonical_slug`,
`context_length`, `created`, `default_parameters`, `description`, **`expiration_date`**, `hugging_face_id`, `id`,
**`knowledge_cutoff`**, `links.details` (per-model `/endpoints` URL), `name`, `per_request_limits`, `pricing`
(incl. `input_cache_read`, `input_cache_write`, `web_search`), `reasoning`, `supported_parameters`,
`supported_voices`, `top_provider` (`context_length`, `max_completion_tokens`, `is_moderated`). Tier A live.

`[FACT]` **`benchmarks.artificial_analysis`** = `{intelligence_index, coding_index, agentic_index}` is populated
for **161 of 420** models. Example: `anthropic/claude-fable-5.1` -> `65.7 / 81.6 / 61.3`. Tier A live (single
source: the API itself; the field is not yet documented on a page this session could fetch - UNVERIFIED in docs).
`[INFER]` This is a **native price/perf signal inside the catalog** - the estate no longer needs a hand-curated
"is this cheap model any good" table; a T0/T1 shortlist can be computed as `index / blended $` from one public GET.
Section 5 does exactly that.

`[FACT]` **Price drift in six days on the pinned T0 slug.** `deepseek/deepseek-v4-flash-0731` was $0.06 / $0.12
per M (in/out) on 2026-08-27 (in-repo skill) and is **$0.065 / $0.18** live today; the `~deepseek/deepseek-v4-flash-latest`
alias moved from $0.03 / $0.075 to **$0.05 / $0.16**. Tier A live vs Tier A repo, corroborated (two dated readings).
`[INFER]` Hardcoded USD figures in `openrouter-routing/SKILL.md` go stale within a week; the skill should quote
**slugs + the live GET**, never prices.

`[FACT]` A **`:batch` model-variant suffix** now appears in `/models` (30 ids, e.g. `deepseek/deepseek-v4-flash-0731:batch`,
`z-ai/glm-5.3-flash:batch`, `openai/gpt-5.6-luna:batch`, `anthropic/claude-sonnet-5:batch`). The only suffixes present
in the live id set are `batch` and `free` (`:floor`/`:nitro`/`:exacto`/`:online` are request-time shortcuts, not
catalog rows). Tier A live; the docs page for a batch variant (`/docs/guides/routing/model-variants/batch`) returned
**404** this session - UNVERIFIED in docs.
`[INFER]` `:batch` list price is ~50% of the **first-party** price (`gpt-5.6-luna` $0.20/$1.20 -> `:batch` $0.10/$0.60)
but for open-weight models with cheap third-party hosts the `:batch` row is **dearer** than the live cheapest endpoint
(`glm-5.3-flash` $0.075/$0.25 vs `:batch` $0.15/$0.50; `deepseek-v4-flash-0731` $0.065/$0.18 vs `:batch` $0.14/$0.28).
So "batch = 50% off" is only true relative to the first-party list price; for T0 open-weight slugs `:floor` beats `:batch`.

`[FACT]` `expiration_date` is set on some rows: `nex-agi/nex-n2-mini` and `nex-n2-pro` expire **2026-09-08**;
`dots-studio/dots-3-note-preview:free` expires **2026-09-30**; several `z-ai/glm-*` rows carry a placeholder
`2098-12-31`. Tier A live. `[REC]` Any allowlist refresh should drop slugs whose `expiration_date` is inside the next
30 days.

`[FACT]` `per_request_limits` is `null` on every row today. Tier A live.

### 2.2 Provider routing and preferences

`[FACT]` The `provider` request object fields (Tier A, https://openrouter.ai/docs/guides/routing/provider-selection,
read 2026-09-02): `order` (string[]), `allow_fallbacks` (default **true**), `require_parameters` (default **false**),
`data_collection` (`"allow"` default | `"deny"`), `zdr` (bool), `enforce_distillable_text` (bool), `only`, `ignore`,
`quantizations`, `sort` (`price` | `throughput` | `latency`, or object), `preferred_max_latency` /
throughput percentile prefs, `max_price` (object). Setting `sort` disables load balancing.

`[FACT]` `:floor` = `provider.sort: "price"` **plus** admits flex service-tier endpoints (superset, not alias);
`:nitro` = `sort: "throughput"` **plus** admits priority-tier endpoints. Same page, Tier A, corroborated by the
08-27 audit. `[REC]` For T0 keep `:floor`; for T1 tool work prefer `:exacto` (quality-ranked for tool calls, per
the in-repo skill) - unchanged from current doctrine.

`[FACT]` `require_parameters: true` is the documented way to guarantee a provider honours `tools` /
`response_format` instead of silently dropping them. Tier A. `[REC]` Every sidecar call that sends `tools` or
`json_schema` should set `provider.require_parameters = true`; the in-repo T0 script does not (gap, see section 6).

### 2.3 Fallbacks

`[FACT]` Provider-level fallback is automatic (`allow_fallbacks: true`); model-level fallback is the `models[]`
array ("specify fallback models to try a different model when all providers for the first are exhausted") - Tier A,
limits page https://openrouter.ai/docs/api-reference/limits read 2026-09-02, corroborated by the 08-27 audit
("max 3, changes behaviour"). Estate doctrine already forbids `models[]` as a hidden T0->T2 uptier (L1 + skill);
this lens keeps that rule.

### 2.4 `:free` tier behaviour and limits

`[FACT]` Limits page, Tier A, 2026-09-02: "If your account has a negative credit balance, you may see errors,
including for free models." Free-variant caps are a table keyed on **credits purchased (all time)** with
requests-per-minute and requests-per-day columns whose numbers are rendered in tags this fetch stripped; the
08-27 in-repo audit recorded **20 RPM; 50 RPD if < $10 lifetime purchases, else 1000 RPD** (Tier A then,
UNVERIFIED-live today). 429 from OpenRouter carries `X-RateLimit-Limit/Remaining/Reset`; upstream 429 carries
`error.metadata.provider_code`; `Retry-After` when every provider returned a hint. Paid variants have "no
platform-level request cap".

`[FACT]` Live `:free` set (18) and its capability flags today - all but `nvidia/nemotron-3.5-content-safety:free`
advertise `tools`; only four advertise `structured_outputs` (`dots-3-note-preview:free`, `liquid/lfm-2.5-2.6b:free`,
`z-ai/glm-5.2:free`, `nvidia/nemotron-3-super-120b-a12b:free`). Strongest by Artificial Analysis index:
`z-ai/glm-5.2:free` 52.6 / coding 68.8; `minimax/minimax-m3:free` 45.4 / 58.6; `thinkingmachines/inkling:free`
42.3 / 52.1. Tier A live. `[REC]` Keep the estate rule "free = smoke/extract only, never agentic coding, may be
trained on" (privacy toggles differ for free vs paid per the in-repo skill).

### 2.5 Tool calling and structured outputs flags

`[FACT]` Capability is per-row via `supported_parameters` (`tools`, `tool_choice`, `response_format`,
`structured_outputs`, `reasoning`, `include_reasoning`, `reasoning_effort`, `verbosity`, ...). Tier A live.
`[FACT]` The `nousresearch/hermes-4-70b` / `-405b` rows still do **not** list `tools` (confirms the in-repo Hermes
lane's "no tool calling" constraint). Tier A live.

### 2.6 Usage accounting and per-key spend limits

`[FACT]` `GET /api/v1/key` returns `limit`, `limit_reset` (`daily`|`weekly`|`monthly`|null), `limit_remaining`,
`include_byok_in_limit`, `usage`, `usage_daily`, `usage_weekly`, `usage_monthly`, `byok_usage*`, `is_free_tier`
("whether the user has paid for credits before"); the older `rate_limit` object is deprecated. Tier A, limits page.
402 = account balance <= 0 **or** per-key `limit_remaining` exhausted. `[FACT]` Per the in-repo audit, changing a
key's limit needs the dashboard or a **management** key (`PATCH /api/v1/keys/{hash}`), and management keys cannot
run completions (Tier A, 08-27, not re-fetched today).

### 2.7 BYOK passthrough

`[FACT]` BYOK page (Tier A, https://openrouter.ai/docs/guides/overview/auth/byok, 2026-09-02): using your own
provider keys costs a percentage "of what the same model/provider would cost normally on OpenRouter", deducted
from credits, after a **plan-dependent free allowance measured by list-price inference cost** (PAYG monthly
allowance; Enterprise larger). Numbers rendered in tags: 08-27 audit recorded **5% after $25k/mo PAYG** -
UNVERIFIED-live. BYOK keys have a priority/fallback section model. `[INFER]` Irrelevant to this estate today:
there is no upstream provider key the owner wants to route *through* OpenRouter (Claude and Cursor are locked
native by L1). SKIP.

### 2.8 Deprecated `:online` suffix and web plugin

`[FACT]` Plugins page (Tier A, https://openrouter.ai/docs/guides/features/plugins, 2026-09-02): "**Deprecated** -
The `:online` variant and the web search plugin are deprecated. Use the `openrouter:web_search` server tool
instead." Remaining plugins: PDF Inputs, Response Healing, Pareto Router (and others). The web-search page
(https://openrouter.ai/docs/guides/features/web-search) still documents `:online` mechanics and prices the
Parallel engine at **$1 per 1,000 requests** (turbo/fast) to **$5 per 1,000** (basic/advanced), plus $1 per
1,000 extra results; `web_search_options.search_context_size` low/medium/high. Corroborated (two pages).
`[REC]` Unchanged: never `:online`; search stays on Firecrawl / Exa / native Max per estate routing decision.

## 3. Runtime-by-runtime: how each ALLOWED runtime consumes OpenRouter today

"Allowed" = the brief's list (Codex, Fabric, Aider, OpenCode, Goose, Grok CLI, Gemini CLI?). Claude Code and
Cursor are **not** in this table by lock L1. All doc reads dated 2026-09-02 unless stated.

| Runtime (installed) | Native OpenRouter path per current docs | Key/secret binding | Model id shape | Source + grade | Estate status |
| --- | --- | --- | --- | --- | --- |
| **Codex CLI** | `[model_providers.<id>]` custom provider with `base_url`, `env_key`; `wire_api` accepts **only `responses`** ("the only supported value, and it is the default when omitted"). Provider/profile keys are **ignored in project-local `.codex/config.toml`** - must be user-level. New: `model_providers.<id>.http_headers` / `env_http_headers` (static or env-sourced headers) and `auth.command` (command-backed bearer token; "do not combine with `env_key`"). | `env_key = "OPENROUTER_API_KEY"` | full OpenRouter slug via `/api/v1/responses` | https://developers.openai.com/codex/config-reference - Tier A, read 2026-09-02; corroborates in-repo skill "Codex no longer accepts chat" | **NATIVE, already wired** as non-default `[model_providers.openrouter]` + `[profiles.openrouter]` (in-repo skill). Gap: no `http_headers` for `HTTP-Referer` / `X-OpenRouter-Title` attribution -> Codex traffic is invisible in OpenRouter app rankings/activity filtering. |
| **Fabric** (1.4.470) | OpenRouter is a listed **OpenAI-compatible vendor** ("OpenAI-Compatible Providers: ... OpenRouter ..."); configured via `fabric --setup` / `fabric --listvendors`; per-pattern model pinning via env `FABRIC_MODEL_<PATTERN>=vendor\|model`. | vendor key entered at `--setup` into Fabric's `~/.config/fabric/.env` (Fabric-owned file, **not** the estate's env var by name) | `OpenRouter\|<author>/<slug>` | https://raw.githubusercontent.com/danielmiessler/Fabric/main/README.md - Tier A, read 2026-09-02 | **NATIVE, unverified-wired**: the estate has a `fabric-cursor` wrapper (auth2api) but no evidence in-repo that the OpenRouter vendor is set up. `[REC]` per-pattern env pins are the right T0 hook (e.g. `FABRIC_MODEL_SUMMARIZE=OpenRouter\|z-ai/glm-5.3-flash`). |
| **Aider** (0.86) | `aider --model openrouter/<provider>/<model>`; `aider --list-models openrouter/`; provider selection via `extra_params`/`provider` in `.aider.model.settings.yml` or by ignoring providers in the OpenRouter account; docs warn to "enable providers that may train on inputs" to see all models. | `OPENROUTER_API_KEY` env (**same name as the estate's canonical var**) | `openrouter/<author>/<slug>` (LiteLLM-style prefix internally; Aider vendors LiteLLM as a library, not a proxy - not the forbidden LiteLLM *gateway*) | https://aider.chat/docs/llms/openrouter.html - Tier B (project docs), read 2026-09-02 | **NATIVE, zero-config**: because Aider reads the same env var name, it is already OpenRouter-capable on the box. 08-27 audit marked it "BUILD-optional later"; this lens upgrades it to **NATIVE-READY, opt-in per invocation**. Caveat `[INFER]`: Aider's bundled litellm reads model metadata from its own JSON; slugs newer than the pin may need `.aider.model.metadata.json`. |
| **OpenCode** | Built-in provider: `/connect` -> OpenRouter -> paste key; `/models` lists preloaded OpenRouter models; extra models via `opencode.json` `provider.openrouter.models`. Desktop + TUI share `opencode.json` and stored credentials. | key stored by OpenCode's credential store (`/connect`), **not** env by name | `openrouter/<author>/<slug>` | https://opencode.ai/docs/providers/ and https://openrouter.ai/docs/cookbook/coding-agents/opencode-integration - Tier A x2, corroborated, read 2026-09-02 | **NATIVE, unverified-wired**. `[INFER]` Second copy of the secret inside OpenCode's store conflicts with "one env var, name-only pointer" - see section 4 key-scoping. |
| **Goose** (1.47) | Provider list includes OpenRouter (Goose docs); the estate already runs Goose against auth2api via `GOOSE_PROVIDER=goose-cursor-proxy` (brief). | `OPENROUTER_API_KEY` env (Goose convention `<PROVIDER>_API_KEY`) | `<author>/<slug>` | Goose provider page returned **404** at both URL variants this session -> **UNVERIFIED-live**; claim rests on the brief + Goose's documented provider convention (Tier C until re-fetched) | **NATIVE per docs, not wired for OR** (wired to auth2api instead). `[REC]` Keep Goose on auth2api (Cursor quota is free-at-margin); OpenRouter only as a named secondary provider for T0 bulk via `GOOSE_PROVIDER=openrouter` on a per-run basis. |
| **Grok CLI** (`grok` + `agent.exe`) | The estate's Grok CLI uses `config.toml` with `[model."cursor-grok-4.6"]` tables pointed at auth2api (brief). The open-source `superagent-ai/grok-cli` (npm) instead uses `~/.grok/user-settings.json` and env `GROK_BASE_URL` (default `https://api.x.ai/v1`) + `GROK_API_KEY`; any OpenAI-compatible base URL works, so OpenRouter is reachable by setting `GROK_BASE_URL=https://openrouter.ai/api/v1`. | `GROK_API_KEY` (would have to hold the OpenRouter secret - a **second name for the same secret**) | full OpenRouter slug | https://raw.githubusercontent.com/superagent-ai/grok-cli/main/README.md - Tier B, read 2026-09-02. Which Grok CLI the box runs is **UNVERIFIED** from this checkout (the `config.toml [model."..."]` shape does not match superagent's JSON settings) | **AMBIGUOUS**. `[REC]` Do not add an OpenRouter model table to Grok CLI until the binary's provenance is confirmed; it already has Cursor quota via auth2api. |
| **Gemini CLI** | Official docs: `/model` and `--model` select among **Gemini** models only (Auto Gemini 3 / Auto Gemini 2.5 / Manual). No OpenAI-compatible or OpenRouter provider option is documented. | n/a | n/a | https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/model.md - Tier A, read 2026-09-02 | **NOT an OpenRouter consumer**. `[REC]` SKIP; do not fork or proxy Gemini CLI onto OpenRouter (would be a second bridge, violating the spirit of L3/L4). |
| Claude Code, Cursor | cookbooks exist (`ANTHROPIC_BASE_URL`, `/api/v1/cursor`) | - | - | in-repo 08-27 audit | **FORBIDDEN by L1** - listed only so the boundary is explicit. |

`[INFER]` Net: three runtimes are **already OpenRouter-capable with zero new code** (Codex wired; Aider by shared
env var name; Fabric/OpenCode by their own setup flows). One is a documented consumer but deliberately kept on
auth2api (Goose). One is ambiguous (Grok CLI) and one is not a consumer at all (Gemini CLI). The "general
integration layer" the owner wants to replace `tools/mcp/glm53-space` with therefore **already exists as the
OpenRouter sidecar** for every allowed CLI: `z-ai/glm-5.3` ($1.40/$4.40) and `z-ai/glm-5.3-flash` ($0.075/$0.25)
are both live on OpenRouter today (Tier A live `/models`), so GLM-5.3 reachability needs no bespoke MCP or proxy.

## 4. Sidecar policy design

Everything here is `[REC]` unless marked; each rule names the lock it serves and the trade-off it carries (L7).

### 4.1 Key scoping - one inference key per runtime family, never one shared secret under many names

`[FACT]` OpenRouter caps are **per inference key** (`limit` + one `limit_reset`), and `GET /api/v1/key` reports usage
per key (section 2.6). `[FACT]` Making more keys "will not affect your rate limits" (limits page, Tier A). `[INFER]`
Therefore per-runtime keys are the only way to (a) attribute spend to Codex vs Aider vs Fabric without a proxy and
(b) give each runtime its own hard brake - a LiteLLM-style budget proxy is forbidden (L2), so the **key is the proxy**.

| Key (label on dashboard) | Runtime(s) | Binding | Cap suggestion | Why |
| --- | --- | --- | --- | --- |
| `or-codex-sidecar` | Codex `--profile openrouter` | `env_key = "OPENROUTER_API_KEY_CODEX"` in user-level `~/.codex/config.toml` (project-local is ignored by Codex - Tier A) | daily, small (single-digit USD) | agentic loops are the runaway risk |
| `or-cli-grunt` | `openrouter-complete.py`, Aider, Fabric per-pattern pins | `OPENROUTER_API_KEY` (existing canonical name - Aider reads it natively) | daily, small | T0 bulk; shared because all three are human-invoked one-shots |
| `or-ide-opencode` (only if OpenCode is ever used with OR) | OpenCode `/connect` credential store | OpenCode-owned store | daily, small | isolates the one runtime that copies the secret into its own store |

Trade-off (L7): more keys = more dashboard clicks and three `.agents/local.json` name-only pointers instead of one;
benefit = per-runtime 402 brakes and clean attribution. **Constraint L6**: the *owner* creates these in the browser;
no agent mints keys (the 08-27 audit's "do not mint" rule and the OAuth/MCP-minted-key SKIP stand).

### 4.2 Hard spend caps - what is enforceable today on PAYG

`[FACT]` One key has exactly one `limit_reset` (daily XOR weekly XOR monthly); daily+monthly together is a
**workspace budget** (Enterprise, returns 403) - in-repo 08-27 audit, Tier A then. `[REC]` Policy on PAYG:

1. Every sidecar key gets `Limit` + `limit_reset = daily` (midnight UTC hard brake).
2. Monthly is **observational**: the T0 script's `--show-limits` already prints `usage_monthly`; add a threshold
   print (not a new daemon, L2/L4) so a human sees "monthly > X" on the next run.
3. Account balance is the second brake: keep the prepaid balance small on purpose (the account was overdrawn by
   ~$0.39 on 08-27 and paid slugs 402'd - that is the system working, not a bug).
4. `include_byok_in_limit` is irrelevant (no BYOK, section 2.7).

### 4.3 Exact lock boundaries (restated as testable assertions)

- **Never Cursor BYOK**: no OpenRouter key in Cursor Settings > Models; no Override Base URL `https://openrouter.ai/api/v1/cursor`. Test: Cursor settings JSON contains no `openrouter.ai` string. (L1)
- **Never Claude base URL**: `ANTHROPIC_BASE_URL` unset or non-OpenRouter; `ANTHROPIC_AUTH_TOKEN` never an `sk-or-` value. Test: `env | grep -i anthropic_base_url` empty in every shell profile. (L1)
- **Never a new OpenRouter MCP**: `.agents/agents.json` `mcp.servers` (42 today) and `.cursor/mcp.json` contain no `mcp.openrouter.ai`. (L1)
- **No new listener**: the sidecar is outbound HTTPS only; ports 8765/8812/8317 untouched. (L4)
- **auth2api precedence**: for any model that Cursor Max already serves (Claude, Grok, GPT, Gemini frontier), runtimes go through `127.0.0.1:8317`, not OpenRouter; OpenRouter is for models Cursor does **not** serve (GLM, DeepSeek, Qwen, MiniMax, Gemma, Hermes) and for T0 bulk. (L3) `[INFER]` This is also the cheapest split: Cursor quota is sunk cost, OpenRouter is marginal cost.
- **Prompt SSOT**: Fabric per-pattern pins and Aider `--model` choose the *model*; the *prompt* still comes from `.agents/skills`. (L5)

### 4.4 Request hygiene the current T0 script lacks (gaps, not rewrites)

`[REC]` (a) `provider.require_parameters: true` whenever `tools`/`response_format` are sent (section 2.2);
(b) `provider.data_collection: "deny"` for any prompt that carries repo code (privacy toggle is account-wide
otherwise); (c) refuse slugs whose `expiration_date` is < 30 days out (section 2.1); (d) keep `HTTP-Referer` /
`X-OpenRouter-Title` (already sent) and add the same two headers to Codex via `model_providers.openrouter.http_headers`
(section 3); (e) never hardcode prices - the allowlist file stores slugs only, prices come from the public
`/models` GET at check time.

## 5. Model shortlists (T0 / T1) with price/perf evidence

_(pending)_

## 6. Per-find rubric table

_(pending)_

## 7. Ten-line summary

_(pending)_
