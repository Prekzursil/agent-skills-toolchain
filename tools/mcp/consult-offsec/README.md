# consult-offsec MCP server

Mid-task consult MCP to uncensored/abliterated offensive-security models.
One tool (`consult_offsec`), one purpose: a scoped offsec oracle with an
audited, rate-capped, verbatim-relay contract. Zero-dependency stdio
JSON-RPC 2.0 (newline-delimited) — needs only CPython, no pip installs.

## Where the copies live (deploy vs repo)

| Copy | Path | Role |
|---|---|---|
| **Repo SSOT** | `tools/mcp/consult-offsec/server.py` (this directory, branch stacked on PR #314) | Source of truth. Changes land here first. |
| **Deployed** | `D:\MCP\consult-offsec\server.py` | The live fork the agent sessions actually launch (registered in `.agents/agents.json`). Hotfixes made here MUST be back-ported to the repo before they rot (grill G-14). |

`D:\MCP\consult-offsec\GRILL-QUEUE.md` (deployed side) holds the 18 grill
decisions G-1..G-18 that shaped v1; the e2e-wave decisions (Q1-Q6, dollar
metering, registry split) live in the wave's grill decision log and
`docs/gem-hunt/2026-09-02-hosted-models/` lane docs.

## Smoke test

```bash
python tools/mcp/consult-offsec/server.py --selftest   # repo copy
python D:\MCP\consult-offsec\server.py --selftest      # deployed copy
```

Offline; covers allowlist, char caps, model allowlist, the G-6 fence-escape
regression, sanitize, log-path confinement, budget counter, audit write, and
(since v1.2) the dollar meter.

## Environment contract

| Var | Required | Default | Meaning |
|---|---|---|---|
| `HF_TOKEN` | YES | — | Hugging Face inference token for the cloud route. Env passthrough only; never hardcoded, never logged (G-9). |
| `CONSULT_USD_CEILING` | no | `2.0` | Daily USD ceiling for cloud consults (grill Q3). The HF-router family cap (hf-router 1.0 + hf-router-featherless 1.0 = 2.0) documented in `.agents/models.json` as shared/registry-unenforceable — this meter is the enforcement. |
| `CONSULT_PRICE_IN_M` | no | `0.5` | Conservative table-estimate price, USD per 1M input tokens. |
| `CONSULT_PRICE_OUT_M` | no | `4.0` | Conservative table-estimate price, USD per 1M output tokens. |
| `CONSULT_DAILY_CAP` | no | `50` | Max consults/day (G-15), fail closed. |
| `CONSULT_MIN_INTERVAL` | no | `10` | Minimum seconds between outbound calls (G-15). |
| `CONSULT_ROUTE` | no | `auto` | Default route: `auto` (cloud-first, local fallback), `cloud`, `local`. |
| `CONSULT_MODEL` | no | `huihui-ai/Huihui-CyberStrike-OffSec-35B-abliterated` | Default cloud model. |
| `CONSULT_LOCAL_MODEL` | no | `wrn-coder-7b` | Default local model (Ollama). |
| `CONSULT_EXTRA_MODELS` | no | — | Comma-separated extra cloud model ids added to the G-10 allowlist. |
| `CONSULT_CLOUD_TIMEOUT` | no | `120` | Cloud route timeout seconds (G-13; under the client's 240s). |
| `CONSULT_LOCAL_TIMEOUT` | no | `210` | Local route timeout seconds (G-13). |
| `CONSULT_MAX_OUT` | no | `4096` | max_tokens sent to the model. |

## Dollar metering (v1.2, grill Q3)

- `daily_usd()` sums **today's cloud consult entries** from the audit log,
  recomputing each entry's `usage` tokens against the price table
  (per-model rows may be added to `PRICE_TABLE` in the server; everything
  without an explicit row meters at the `CONSULT_PRICE_IN_M`/`_OUT_M`
  defaults — the meter never assumes a model is free).
- The gate runs **before every outbound cloud call** (and before the
  credential check). At/over the ceiling: `route=cloud` fails closed with a
  loud error naming `CONSULT_USD_CEILING`; `route=auto` skips the cloud leg
  with the reason recorded and falls to the free local leg
  (provenance-tagged `route: local`, G-12).
- Every consult audit entry carries `computed_usd` (0.0 for local calls).

## Audit log (G-16)

Append-only JSONL at `logs/consult-YYYYMM.jsonl` **beside whichever copy is
running** (monthly rotation; paths charset-validated and confined — no
dynamic joins). One line per consult: ts, route, model, purpose, question,
answer, context digest, latency, finish_reason, usage, computed_usd; error
lines on failures. The deployed copy's `D:\MCP\consult-offsec\logs\` is the
live audit trail and is **never committed** — the repo copy's logs dir does
not exist in the tree.

## Grill decision references

- G-1..G-18 (v1 hardening): `D:\MCP\consult-offsec\GRILL-QUEUE.md` —
  advisory-only contract (G-1), verbatim relay + UNVERIFIED frame (G-2/G-6),
  no second raw-chat tool (G-3), stateless (G-4), egress guidance (G-8),
  env token (G-9), model allowlist (G-10), repo-vs-deploy split (G-14),
  rate caps (G-15), audit log (G-16), selftest (G-17), single-flight (G-18).
- Q1-Q6 (e2e wave): dollar metering + family cap split (Q3), unprobed-then-
  probe-during-review registry rows (Q4), redacted stanza artifact (Q6) —
  see the wave's `GRILL-DECISION-LOG-consult-offsec-e2e.md` and
  `.provenance/.agents/models.json.md`.
