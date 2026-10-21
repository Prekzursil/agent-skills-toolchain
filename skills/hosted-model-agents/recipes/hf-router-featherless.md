# Recipe: HF router featherless route (abliterated/WRN offsec checkpoints)

**SSOT = `.agents/models.json` endpoint `hf-router-featherless`** (baseUrl
`https://router.huggingface.co/featherless-ai/v1`) **+ `inference-hub`** —
this recipe is operational guidance, not a second registry.

## What this recipe is

The HF Inference Providers router **pinned to the featherless-ai provider
path** (`/featherless-ai/v1` instead of the plain `/v1`): the route that
serves the abliterated/WRN offensive-security checkpoints —
`huihui-ai/Huihui-CyberStrike-OffSec-35B-abliterated` (model
`huihui-cyberstrike-35b`, the consult-offsec default cloud expert),
`WhiteRabbitNeo/WhiteRabbitNeo-2.5-Qwen-2.5-Coder-7B` (`wrn-2.5-coder-7b`),
`huihui-ai/Huihui-Qwen3.8-27B-abliterated` (`huihui-qwen3.8-27b-abliterated`).
Same account, token NAME, and billing as the plain `hf-router` route.

Use it through: `inference-hub` `chat model="offsec-cloud"` (alias), or the
`consult-offsec` MCP (its cloud route hits exactly this URL).

## What this recipe is not

- **Not a new MCP server.** SKILL.md rule 2: an inference URL is a runtime.
  Endpoints and models live in `.agents/models.json`; the ONE inference MCP
  row is `inference-hub`. Never add a featherless MCP row to `agents.json`.
- Not a general uncensored oracle. The abliterated checkpoints pair ONLY with
  the authorized-scope reporter persona ([../profiles.md](../profiles.md)) —
  no attack playbooks into hosted models.
- Not probed yet. All three model rows are `status: unprobed` with
  wire/features `declared` (grill Q4) — receipts flip them during PR review.

## Traps (checkpoint- and route-specific)

- **32K context cap** on all three rows (per the ZCode provider stanza). Do
  not paste whole files; consult-style single questions only.
- **`response_format` needs a probe**: like the plain router, pinned routes
  only carry `response_format` reliably after a probe writes
  `probed{at,version}`; until then structured output is `declared`, and
  renderers floor on `probed`.
- **The budget cap is shared with `hf-router`** — 1.0 + 1.0 = 2.0 USD/day on
  the same HF account, registry-documented as shared and
  registry-unenforceable (grill Q3). The enforcement is the consult-offsec
  server's v1.2 dollar meter (`CONSULT_USD_CEILING`, default 1.0 — the
  server's own lane share of the family split; raise to 2.0 only if you
  accept starving the plain `hf-router` lane; fail-closed before every
  cloud call); other consumers must respect the same ceiling.
- Auth NAME: `HUGGINGFACE_TOKEN_INFERENCE` (primary) / `HF_TOKEN` (`altEnv`);
  `issuerHosts` binds both to `*.huggingface.co` (V19).

## consult-offsec pairing (the main consumer)

`consult-offsec` (agents.json row; repo SSOT
`tools/mcp/consult-offsec/server.py`, deployed `D:\MCP\consult-offsec\`)
calls exactly this route with model
`huihui-ai/Huihui-CyberStrike-OffSec-35B-abliterated`. Its contract: one
focused question, verbatim relay inside a server-stamped UNVERIFIED frame,
model allowlist (G-10), rate caps + USD meter fail-closed (G-15, Q3), JSONL
audit (G-16). The driver relays the answer verbatim and never executes it.
For cred-laden contexts use `route=local` instead (G-8).

## Tests

- Offline: `python tools/mcp/consult-offsec/server.py --selftest` (must PASS,
  includes the dollar-meter gate test since v1.2).
- Probe pass (flips the three rows `unprobed → live` and writes
  `probed{at,version}` receipts): one `chat` per model through
  `inference-hub`, receipts attached to the PR as review comments (grill Q4).
