---
title: cursor-cli-bridges
type: note
permalink: dqverify-repo-20261013/docs/cursor-cli-bridges
---

# Cursor CLI Bridges (Windows-native, token-auth)

**Updated:** 26.08.2026 · **Status:** live, verified e2e

Run **Claude Code CLI**, **Codex CLI**, and **Grok CLI** on Windows against the
**Cursor** model backend, authenticated with the existing Cursor desktop session
token — no OAuth, no new credentials, no WSL, fully reversible.

**Remember one command:** `ai-mode` (alias `grok-mode`) — on PATH via `~/.local/bin`.

| Command | What it does |
|---|---|
| `ai-mode` / `ai-mode status` | which backend each CLI is on + whether auth2api `:8317` is up |
| `ai-mode native` | strip Cursor overrides from global grok config + User env; `grok`→grok.com, `claude`→Anthropic, `codex`→OpenAI |
| `ai-mode cursor` | does **not** rewrite globals; prints `grok-cursor` / `claude-cursor` / `codex-cursor` |
| `grok-cursor` / `claude-cursor` / `codex-cursor` | opt-in Cursor quota (env-only wrappers) |

Native binaries **always** talk to their real vendors unless you explicitly launch `*-cursor`.
`ai-mode native` is the revert — not hand-editing `~/.grok/config.toml`.

| Bridge | Status | How |
|---|---|---|
| **Claude Code CLI** | ✅ e2e | `claude-cursor` → `ANTHROPIC_BASE_URL=http://127.0.0.1:8317` → auth2api `/v1/messages` → Cursor |
| **Codex CLI** | ✅ text/reasoning | `codex-cursor` (`--profile cursor`, `~/.codex/cursor.config.toml`, `wire_api="responses"`) → `/v1/responses` |
| **Grok CLI** | ✅ opt-in wrapper | `grok` = grok.com; `grok-cursor` sets `GROK_MODELS_BASE_URL=http://127.0.0.1:8317/v1` in-process only |

## The proxy

- **auth2api** (`AmazingAng/auth2api` + local patches), Node/TypeScript, at
  `C:\Users\Prekzursil\Cowork\tools\auth2api`, listening on `http://127.0.0.1:8317`
  (localhost only). Start/restart: `start-proxy.ps1`; idempotent: `ensure-proxy.ps1`.
- **Auth:** the existing desktop `cursorAuth/accessToken`+`refreshToken` imported into the
  proxy's local token store. `"cursor-local-key"` is the proxy's **local** gate key the CLIs
  send — not a Cursor credential.
- Endpoints: `/v1/messages` (Anthropic), `/v1/chat/completions` + `/v1/responses` (OpenAI),
  `/v1/models` (advertises the Cursor catalog).

## Model map & selection (SSOT: `src/upstream/cursor-api.ts` → `normaliseModel`)

Cursor's chat backend accepts only the exact SKU ids `cursor-agent models` prints —
every SKU carries an effort suffix, Claude SKUs have **no** `cursor-` prefix, only Grok is
`cursor-grok-*`. Bare family names are rejected (`claude-fable-5` → `ERROR_BAD_MODEL_NAME`;
`claude-fable-5-thinking-high` works). The proxy resolves, in order:

1. **Regular Claude effort-families** (`fable`/`fable-5`/`claude-fable-5`, `opus`/`opus-5`,
   `sonnet`/`sonnet-5`, `claude-opus-4-8`, `claude-opus-4-7`) → synthesised
   `<base>[-thinking]-<level>` from the request's `thinking.budget_tokens` /
   `reasoning_effort` (no hint → `-thinking-high`; thinking disabled → plain `-high`).
2. **Grok family** (`grok`, `grok-4.6`, `grok-4.5`) → `cursor-grok-<ver>-<level>` from the
   same effort hint, `xhigh` honored on 4.6, clamped to `high` on 4.5; no hint → `high`.
3. **Dated/irregular public names** → exact SKUs (`claude-sonnet-4-5-20250929` →
   `claude-4.5-sonnet`, `claude-sonnet-4-6` → `claude-4.6-sonnet-medium`, `gpt-5.5` →
   `gpt-5.5-medium`, `gemini` → `gemini-3.1-pro`, …).
4. **Already-valid SKUs pass verbatim** (incl. bracket-parameterised forms and the
   `cursor-`-prefixed ids `/v1/models` advertises; `cursor-grok-*` is never stripped).
5. Env override `CURSOR_MODEL_ALIASES="name=sku,…"`.

`src/upstream/translator.ts` → `resolveModel` is provider **routing** + cosmetic echo only
(strips `anthropic.`/`openai.` vendor prefixes, maps short aliases); it never reaches the
Cursor upstream.

## Claude Code CLI

```powershell
C:\Users\Prekzursil\Cowork\tools\auth2api\claude-cursor.ps1 -p "hello"
C:\Users\Prekzursil\Cowork\tools\auth2api\claude-cursor.ps1 -Model fable -p "..."   # any alias/SKU
```
Env is process-local; plain `claude` elsewhere is untouched. Verified e2e:
`-Model fable` → `claude-fable-5-thinking-high` → correct reply.

## Codex CLI

```powershell
$env:CURSOR_PROXY_KEY = "cursor-local-key"
codex exec --profile cursor --skip-git-repo-check -s read-only "hello"
```
Profile: `~/.codex/cursor.config.toml` (`base_url=http://127.0.0.1:8317/v1`,
`wire_api="responses"`). Revert: delete that file.

## Grok CLI — seamless native ⇄ Cursor switch

Native stays 100% intact; Cursor is opt-in per session (no global config override).

- **`grok`** → native grok.com — full agentic tool loop + web_search.
- **`grok-cursor.ps1`** → Cursor catalog + quota via Grok's documented custom-models-endpoint
  mode (`GROK_MODELS_BASE_URL=http://127.0.0.1:8317/v1`, `XAI_API_KEY=cursor-local-key`).
  `grok-cursor models` lists the whole Cursor catalog; bare `cursor-grok-4.6` is auto-lifted
  to `cursor-grok-4.6-high` (`-xhigh` with effort). Env is process-local.

### Tool-calling through Cursor — attempted, gated OFF

Two independent techniques were built and tested to carry tool-calls over Cursor; **both are
blocked**:
1. **Native protobuf tools** — `MCPTool` (field 34) + `supported_tools` (29) + per-message
   agentic markers; response `ClientSideToolV2Call` decode → `tool_use`/`function_call`. Cursor
   activates agent mode but exposes only its built-in `ask_question`; external tools are ignored.
   Gated behind `CURSOR_EXPERIMENTAL_TOOLS=1` (default off) so tool-sending clients degrade to a
   clean chat answer instead of refusals.
2. **ReAct text-shim** — inject tool schemas into the prompt, parse `TOOL_CALL {...}` back into
   structured calls (needs nothing from Cursor). Cursor's server-injected agent prompt overrides
   it and intercepts tool intents ("Tool <x> not found").

**Root cause:** Cursor serves models **only inside its own IDE-agent frame** — its built-in
tools need the editor's workspace context an API bridge lacks, so it exposes only `ask_question`
and overrides any client tool protocol (native or prompt-based). Chat/reasoning works; the
agentic loop + web_search are architecturally impossible from the bridge. For the Grok/Codex/
Claude interface *with* tools, use a real tool-calling API (native grok.com / xAI `api.x.ai` /
Anthropic / OpenAI). `cursor-agent` gives a Cursor-model agent with tools on the Cursor sub, via
Cursor's own UI.

## Grok CLI (legacy global override — superseded by the switch above)

Grok CLI officially supports overriding **built-in** models
(`~/.grok/README.md` → *Custom Models → Overriding Built-in Models*): only the specified
fields change, everything else (name, picker, effort knob) stays native. In
`~/.grok/config.toml` (TOML note: dotted names **must be quoted** or the key nests at the dot):

```toml
[model."grok-4.6"]
base_url = "http://127.0.0.1:8317/v1"
api_key = "cursor-local-key"

[model."grok-4.5"]
base_url = "http://127.0.0.1:8317/v1"
api_key = "cursor-local-key"
```

`grok models` still lists exactly `grok-4.6` (default) and `grok-4.5`; `grok -m grok-4.6`
and normal TUI sessions now bill the Cursor subscription instead of grok.com quota. The
proxy maps `grok-4.6` + the CLI's `reasoning.effort` (e.g. the configured `xhigh`) →
`cursor-grok-4.6-xhigh`. No foreign/unsupported models are injected into the Grok CLI.

Grok's built-in models speak the **Responses API** and grok-shell's serde parser hard-fails
on missing fields (`serialization error: missing field 'object'`), so the proxy's Responses
SSE emitter was hardened to the spec-complete envelope (`object`/`status`/`error`/`usage` on
every response snapshot, `sequence_number` on every event) — Codex remains compatible.
Verified e2e: `grok -m grok-4.6 -p "…"` → correct reply, proxy stats show
`grok-shell → POST /v1/responses → provider cursor`.

- **Revert:** `ai-mode native` (strips any leftover `cursor-bridge` / `:8317` model table
  from `~/.grok/config.toml` and clears User-level Cursor env). Footnote: manual restore
  from `config.toml.bak-cursor-models-*` is emergency-only, and only if that bak is
  actually native — the 2026-08-26 file named `bak-cursor-models-*` was the *override*
  snapshot, not the vendor default.

### Feature-parity (tested 2026-08-26)

| Feature | Through Cursor | |
|---|---|---|
| Chat / reasoning / code-as-text | ✅ | e2e verified; `xhigh` → `cursor-grok-4.6-xhigh` |
| `grok models` picker (clean, native) | ✅ | only `grok-4.6`/`grok-4.5` |
| `/model` switching, `/config`, TUI | ✅ | only `base_url`/`api_key` changed |
| Agentic tools (`write_file`, bash, MCP) | ❌ | tested: *"Tool write_file not found … only `ask_question`"*; no file created |
| `web_search` / `web_fetch` | ❌ | tool call the main model never emits through Cursor |

**Root cause (code-confirmed):** the Cursor wire encoder omits client tool declarations and
the decoder emits only text + reasoning (no `ClientSideToolV2Call` frames). This is the
standing boundary for **all three** CLIs. Routing Grok's models through Cursor makes Grok a
chat/reasoning client on Cursor quota; the agentic loop and web search require native
grok.com. Same conclusion applies to Codex's tool loops and Claude Code MCP/tool use.

## Known limitations

- **Agentic tool-calling does not flow through the Cursor upstream** (text + reasoning only):
  Codex/Grok tool loops degrade to text answers; Claude Code Q&A/code-drafting works e2e.
- Chain-of-thought is only surfaced when Cursor returns it; trivial prompts often show none
  even on `-thinking-high`.

## Tests / verification

- Proxy suite: `npm test` → **200/200** (model-map change also repaired 20 pre-existing
  routing failures). Live-verified 2026-08-26: fable/opus/sonnet aliases, bare
  `claude-fable-5`, effort variants, `grok`, `cursor-grok-4.6-xhigh` — all resolve.
- Full report: `Cowork\output\cli-bridges-windows_2026-08-25.md` (private machine SSOT).