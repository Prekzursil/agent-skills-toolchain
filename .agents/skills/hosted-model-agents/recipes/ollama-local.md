# Recipe: Ollama local offsec models (64K context, cred-laden consults)

**SSOT = `.agents/models.json` endpoint `ollama`** (127.0.0.1:11434/v1) **+
`inference-hub`** — this recipe is operational guidance, not a second registry.

## What this recipe is

The four local offsec/coder checkpoints from the ZCode "Ollama Local" provider
stanza, served by the box's Ollama (weights on `D:\ai-models\ollama`, RTX 4050
6 GB):

| Model row | remoteId | Tier | ctx/out | RAM est. (quant-based) | State |
|---|---|---|---|---|---|
| `wrn-coder-7b` | `wrn-coder-7b` | M | 65536/8192 | ~5.4 GB | enabled, unprobed |
| `qwythos-9b` | `qwythos-9b` | M | 65536/16384 | ~6.6 GB | enabled, unprobed |
| `huihui-offsec` | `huihui-offsec` | L | 65536/16384 | ~22 GB | **disabled** (RAM-gated) |
| `gptoss-20b-abliterated` | `gptoss-20b-abliterated` | L | 65536/16384 | ~13.5 GB | **disabled** (RAM-gated) |

The two L rows are registered `enabled: false`: their working sets exceed the
8 GiB `policy.localRamBudgetBytes` warning line; enable only after RAM
planning (pr-lane-plan §5.5). `ramBytes` are parameter-count estimates —
owner-verify with `ollama show <id>` before relying on them.

`wrn-coder-7b` is the consult-offsec default LOCAL model (alias
`offsec-local`); `huihui-offsec` is its 35B-class sibling for
`route=local` consults once enabled.

## What this recipe is not

- Not a new MCP server (SKILL.md rule 2): the Ollama URL is a runtime already
  registered as endpoint `ollama`.
- Not probed: all four rows are `status: unprobed` (grill Q4); probe receipts
  flip them during PR review.

## Traps

- **Estate context cap vs registry context.** The registry rows record the
  declared 64K; actual serving is capped by the user env
  `OLLAMA_CONTEXT_LENGTH` — bumped 8192 → **65536** on 2026-09-03 (grill Q2;
  bench receipts: 64K held under full desktop load, 21 GB mapped, stable,
  8-12 tok/s). If the env ever regresses, the registry rows overstate what
  the server will give you — check `x_ollama.contextLength` first.
- **Residency discipline** (user env, OWNER-CLICKS.md): `OLLAMA_KEEP_ALIVE=2m`,
  `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, KV `q8_0`. One model
  resident at a time; loading a second evicts the first (cold reload next
  call). Keep-alive bumps so a warm 20 GB model stays resident are a
  service-level decision, not a registry one.
- **Cold-load latency:** first local consult after idle pays the model load
  (~2 min for the 20 GB class on this box). consult-offsec's local timeout is
  210 s — under the client's 240 s kill, but tight; warm the model before
  timing-sensitive loops.
- **RAM honesty:** the 20B/35B-class rows exceed the 6 GB GPU working set and
  run CPU-offloaded (8-12 tok/s under load, per the Q2 bench). Do not plan
  interactive fan-out on them.
- consult-offsec `route=local` is the egress-safe path for cred-laden
  contexts (G-8): local never leaves the machine.

## Tests

- Endpoint health: `GET http://127.0.0.1:11434/api/version` (health.kind
  `http`); discovery via `/api/show` capabilities, never assumed.
- Probe pass (flips rows `unprobed → live`): one `inference-hub` `chat` per
  enabled row with receipts attached to the PR (grill Q4).
