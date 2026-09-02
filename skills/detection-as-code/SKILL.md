---
name: detection-as-code
description: "Use when authoring, linting, and backtesting Sigma detections against Zircolite/Hayabusa oracles on lab logs, converting them to a SIEM/EDR backend, and measuring ATT&CK coverage with an expected-hit manifest."
---

# detection-as-code — Sigma authoring, backtest, and ATT&CK coverage

Treat detections like code: write them, lint them, prove they fire on labelled samples and
stay quiet on benign ones, convert them to your backend, and track ATT&CK coverage as a
ledger. This is the blue-team loop — no attacking, no always-on SIEM. It runs against lab /
owner-authorized logs only.

## When to use

- Authoring or reviewing **Sigma** rules and validating them (`rsigma` / `sigma-cli`).
- Backtesting rules against a **test oracle** (Zircolite or Hayabusa) over labelled sample
  logs (EvidenceForge synthetic logs, EVTX-ATTACK-SAMPLES, Security-Datasets/attack_data).
- **Converting** a validated rule to a backend query (Splunk, Elastic, Sentinel, ...).
- Measuring **ATT&CK coverage** and emitting a DeTT&CT / Navigator layer.

If the artifact is a memory image use `volatility-3`; a disk image, `offline-linux-disk-surgery`;
broad host/EVTX triage (not authoring), `dfir-triage`; validating that a detection fires under
emulated attacker behaviour, `purple-emulation`.

## Workflow: write -> lint -> test -> convert -> cover

1. **Write Sigma.** One rule per behaviour. Keep `title`, `id`, `logsource`, `detection`,
   `level`, and `tags` (`attack.tXXXX[.YYY]`) accurate — the `tags` are what the coverage
   ledger reads.
2. **Lint / validate.** `rsigma` (single Rust binary) or `sigma-cli` + pySigma validators.
   Fix schema, field-name, and logsource findings before testing. See `references/upstream.md`.
3. **Test against an oracle with an expected-hit manifest.** Run Zircolite or Hayabusa over
   each labelled sample, normalize its JSON, then reconcile against a manifest that declares
   which rules MUST fire per sample and which must NOT. This is the gate (below). Never skip
   the "must NOT fire" half — a rule that fires on everything measures nothing.
4. **Convert.** Once green, convert with `sigma convert` (pySigma backend) to the target SIEM
   query language. Keep the source Sigma as the SSOT; the backend query is generated.
5. **Coverage ledger.** Emit an ATT&CK Navigator layer of the techniques whose detections
   passed, and diff against your target set with DeTT&CT for the "what's still uncovered" list.

## The expected-hit gate (`scripts/detection_backtest.py`)

Stdlib-only, offline, `python3`. It never runs an oracle or parses raw EVTX — it reconciles
JSON an oracle already produced, so it is safe to run in CI. Run from the skill directory:

```
# 1. Run your oracle per sample (host-gated tools; examples in references/upstream.md), e.g.
#    zircolite ... --outfile out/cred_dump.json     (Zircolite writes a JSON array)
#    hayabusa json-timeline -d evtx/ -J -o out/host.json

# 2. Normalize each oracle run into a results ledger (upserts by sample name):
python3 scripts/detection_backtest.py normalize \
    --oracle zircolite --sample cred_dump.evtx \
    --append-to out/results.json out/cred_dump.json

# 3. Reconcile against the expected-hit manifest; exit 1 on a miss or a forbidden hit:
python3 scripts/detection_backtest.py reconcile \
    --manifest manifest.json --results out/results.json --json \
    --layer-out out/coverage.layer.json

# 4. (or) build a Navigator layer straight from technique IDs:
python3 scripts/detection_backtest.py navigator \
    --name "cred access" --technique T1003.001 --out out/nav.json
```

Expected-hit manifest (JSON; YAML also accepted if PyYAML is installed):

```json
{
  "name": "credential-access backtest",
  "samples": [
    {
      "name": "cred_dump.evtx",
      "expect_fire": ["Mimikatz LSASS Access"],
      "expect_no_fire": ["Benign Service Install"],
      "attack": ["T1003.001"]
    }
  ]
}
```

- `reconcile` fails closed (exit 1) on a missed `expect_fire` or a fired `expect_no_fire`;
  `--strict` also fails on an unexpected hit. Matching is case-insensitive on the rule title.
- A technique is only credited as **covered** when its sample passes, so the Navigator layer
  never overstates coverage.
- `normalize` adapters exist for `zircolite` (detection array) and `hayabusa` (json-timeline).

Tests: `python3 -m pytest tests/ -v` (fakes shaped like real oracle output; no EVTX, no
network, no binaries required).

## MCP: `rsigma mcp serve` (parent-registered, host-gated)

Sigma authoring/lint/convert can be driven by the `rsigma` MCP once the **parent** registers
it in `.agents/agents.json`. It is host-gated: `enabled: false` until the `rsigma` binary is
present on the host. Do **not** register it yourself and do **not** edit `agents.json` — the
proposed block is in this wave's receipt (`docs/plans/cyber-receipts/W-blue.md`) under
`PARENT MERGE`. Until it is live, use the `rsigma`/`sigma-cli` CLI directly.

## Stop rules

- **No always-on SIEM/EDR daemon.** This skill is author-lint-test-convert, run on demand. No
  persistent collector, no streaming pipeline.
- **Lab logs only.** Backtest against synthetic/sample/owner-authorized logs. Do not pull logs
  from third-party or production estates without explicit owner authorization.
- **No live exploitation and no attack tooling.** Generating attacker behaviour to test a
  detection is the `purple-emulation` wave's job, on a lab/owned range only. This skill does
  not produce malware, exploits, or C2.
- **Wrap, don't vendor.** Several oracles/tools are GPL/AGPL (see `references/upstream.md`);
  install and invoke them, do not copy their source into this repo.

## Reference map

`references/upstream.md` — tools (rsigma, sigma-cli/pySigma, Zircolite, Hayabusa), labelled
log corpora (EvidenceForge, EVTX-ATTACK-SAMPLES, Security-Datasets), coverage tooling
(DeTT&CT, ATT&CK Navigator), install one-liners, licenses, and the manifest schema.
