# 14. ZCode v2 `provider{}` stanzas — documented artifact (redacted)

**Status: DOCUMENTED ARTIFACT, not a renderer output.** ZCode is NOT one of the
ten registry runtimes (codex, grok, goose, opencode, aider, fabric, cursor,
claude, agy, gemini — `models_control_plane.RUNTIMES`), so the ZCode v2 config
cannot be generated from `.agents/models.json`. This page records what the live
`C:\Users\Prekzursil\.zcode\v2\config.json` `provider{}` block contains, with
every `options.apiKey` REDACTED to an env-var placeholder (grill Q6; lock L6 —
secrets by NAME only, `gate-secrets` scans full history). The live file carries
literal 37-char keys — never copy it wholesale into the repo.

Measured 2026-09-03 (consult-offsec wave, pr-lane-plan §1e). Model ids,
context/maxOutput numbers, and baseURLs are transcribed exactly; keys are
placeholders by construction.

## The three custom stanzas (redacted)

### `HuggingFaces` (plain router route)

```jsonc
{
  "id": "8bcb6f49…",               // ZCode-internal id, truncated here
  "kind": "openai",
  "enabled": true,
  "baseURL": "https://router.huggingface.co/v1",
  "options": { "apiKey": "${HF_TOKEN}" },   // REDACTED (grill Q6)
  "models": {
    "Qwen/Qwen3.6-35B-A3B":                  { "context": 32768, "maxOutput": 32768 },
    "NousResearch/Hermes-3-Llama-3.1-70B":   { "context": 32768, "maxOutput": 8192 }
  }
}
```

Registry mapping: endpoint **`hf-router`** — models `qwen3.6-35b-a3b`,
`hermes-3-70b`. No separate endpoint: the baseURL is byte-identical to
`hf-router` (pr-lane-plan §3.4(b)).

### `Ollama Local`

```jsonc
{
  "id": "3176c0f9…",
  "kind": "openai-compatible",
  "enabled": true,
  "baseURL": "http://localhost:11434/v1",
  "options": { "apiKey": "${OLLAMA_LOCAL_KEY_UNSET}" },  // REDACTED; local needs no key (placeholder shown for shape only)
  "models": {
    "huihui-offsec":            { "context": 65536, "maxOutput": 16384 },
    "wrn-coder-7b":             { "context": 65536, "maxOutput": 8192 },
    "qwythos-9b":               { "context": 65536, "maxOutput": 16384 },
    "gptoss-20b-abliterated":   { "context": 65536, "maxOutput": 16384 }
  }
}
```

Registry mapping: endpoint **`ollama`** — models `huihui-offsec` (disabled,
RAM-gated), `wrn-coder-7b`, `qwythos-9b`, `gptoss-20b-abliterated` (disabled,
RAM-gated). The 64K stanza contexts are now matched by the estate env
(`OLLAMA_CONTEXT_LENGTH=65536`, grill Q2 — bench receipts 2026-09-03: 64K held
under full desktop load, 21 GB mapped, stable, 8-12 tok/s).

### `HF Featherless` (provider-pinned route)

```jsonc
{
  "id": "a9afcbd5…",
  "kind": "openai-compatible",
  "enabled": true,
  "baseURL": "https://router.huggingface.co/featherless-ai/v1",
  "options": { "apiKey": "${HF_TOKEN}" },   // REDACTED (grill Q6)
  "models": {
    "huihui-ai/Huihui-CyberStrike-OffSec-35B-abliterated":  { "context": 32768, "maxOutput": 16384 },
    "WhiteRabbitNeo/WhiteRabbitNeo-2.5-Qwen-2.5-Coder-7B":  { "context": 32768, "maxOutput": 8192 },
    "huihui-ai/Huihui-Qwen3.8-27B-abliterated":             { "context": 32768, "maxOutput": 16384 }
  }
}
```

Registry mapping: endpoint **`hf-router-featherless`** — models
`huihui-cyberstrike-35b`, `wrn-2.5-coder-7b`, `huihui-qwen3.8-27b-abliterated`.

### Builtin context

The fourth provider entry is the builtin `zai-coding-plan` (the ZCode Coding
Plan GLM models, not user-defined); it has no registry counterpart and is out
of scope here.

## Env-var mapping table (grill Q6)

| Consumer | Env var (NAME only) | Where it is set | Notes |
|---|---|---|---|
| ZCode `HuggingFaces` stanza | `HF_TOKEN` | user-level Windows env | The stanza's redacted `apiKey` resolves to the same token consult-offsec receives via `env_vars` passthrough. |
| ZCode `HF Featherless` stanza | `HF_TOKEN` | user-level Windows env | Same token, same account/billing as the plain route — the family cap (2.0 USD/day) is shared (grill Q3). |
| ZCode `Ollama Local` stanza | — (no auth) | n/a | Loopback Ollama; the registry `ollama` endpoint has `auth: null`. |
| consult-offsec MCP (cloud route) | `HF_TOKEN` | user-level Windows env, injected by the harness `env_vars: ["HF_TOKEN"]` passthrough (agents.json row) | Never hardcoded, never logged (G-9). |
| Registry `hf-router` / `hf-router-featherless` (`auth.env`) | `HUGGINGFACE_TOKEN_INFERENCE` (primary), `HF_TOKEN` (`altEnv` on featherless) | user-level Windows env | D7: fine-grained inference-scoped token NAME; `altEnv` records that the consult-offsec `HF_TOKEN` also authenticates against the same issuer hosts (V19 binding unchanged). |

## Security posture

- Every `options.apiKey` above is an env-var placeholder; the committed file
  contains no credential material (L6 + `gate-secrets` over full history).
- The live `v2/config.json` and its siblings (`config.json.bak-20260903-preollama`,
  `config.json.snapshot-20260903-full`) stay OUT of the repo — this prose page
  is the only in-repo record.
- Abliterated checkpoints pair only with the authorized-scope reporter persona
  (`profiles.md`); consult-offsec enforces the verbatim UNVERIFIED relay.
