# W-blue receipt

COVERAGE: all claims MEASURED (skill shipped, dual-write identical, 18 tests green, ruff clean).
The death-sentence template below is retained per the receipt contract; it no longer applies —
every row is measured, not `UNKNOWN`.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

**Wave:** W-blue — new skill `detection-as-code` (Sigma authoring -> lint/validate -> oracle
backtest with expected-hit manifests -> convert -> ATT&CK coverage ledger).

**Owned paths (ONLY these):**
- `.agents/skills/detection-as-code/**`
- `skills/detection-as-code/**`
- `docs/plans/cyber-receipts/W-blue.md`

## Claims (measured 2026-09-02)

| Claim | Status |
|-------|--------|
| `.agents/skills/detection-as-code/SKILL.md` exists; frontmatter = `name` + `description` only | MEASURED - PASS |
| `agents/openai.yaml` present with quoted `display_name`/`short_description`/`default_prompt` | MEASURED - PASS |
| Helper `scripts/detection_backtest.py` is stdlib-only, offline (no oracle/EVTX/network) | MEASURED - PASS |
| Tests-first with fakes shaped like real Zircolite/Hayabusa output; no live EVTX | MEASURED - PASS |
| Helper tests pass | MEASURED - PASS: 18 passed (canonical) + 18 passed (dual-write), pytest 9.1.1 |
| `ruff check` + `ruff format --check` clean on touched Python (ruff 0.15.17) | MEASURED - PASS: all checks passed; 4 files already formatted |
| Dual-write `skills/detection-as-code/**` byte-identical to canonical | MEASURED - PASS: `diff -r` = IDENTICAL |
| Workflow covers write Sigma -> lint (rsigma/sigma-cli) -> oracle backtest (Zircolite/Hayabusa) with expected-hit manifest -> convert -> DeTT&CT/Navigator ledger | MEASURED - PASS (SKILL.md) |
| Backtest oracles + corpora documented (EvidenceForge, EVTX-ATTACK-SAMPLES, Security-Datasets) | MEASURED - PASS (references/upstream.md) |
| Stop rules present (no always-on SIEM daemon; lab logs only; no live exploitation; wrap-don't-vendor) | MEASURED - PASS |
| Did NOT edit `.agents/agents.json` or any other wave's files | MEASURED - PASS (path-scoped commits) |

## What shipped

- `SKILL.md` — when-to-use, the write->lint->test->convert->cover loop, the expected-hit gate,
  the `rsigma mcp serve` pointer, stop rules, reference map.
- `scripts/detection_backtest.py` — three subcommands, all offline/stdlib:
  - `normalize --oracle {zircolite,hayabusa} --sample NAME [--append-to LEDGER] INPUT` — turns
    one oracle's JSON output into a normalized fired-rule record (upserts into a results ledger).
  - `reconcile --manifest M --results R [--strict] [--json] [--layer-out F]` — fails closed
    (exit 1) on a missed `expect_fire` or a fired `expect_no_fire`; credits an ATT&CK technique
    as covered only when its sample passes.
  - `navigator --name N [--technique T ...] [--from-reconcile R] [--out F]` — minimal ATT&CK
    Navigator layer (v4.5).
- `tests/test_detection_backtest.py` — 18 tests, both-states (gate FIRES on a missed/forbidden
  hit AND stays SILENT on a clean set), fakes only.
- `references/upstream.md` — tools/corpora/coverage links, licenses, manifest + ledger schema.
- `agents/openai.yaml` — quoted interface fields.

## PARENT MERGE

**No action required — already merged by the parent.** The `rsigma` MCP the skill points at is
already registered in `.agents/agents.json` (`mcp.servers.rsigma`) exactly as this wave needs,
DEFAULT-OFF and host-gated on the `rsigma` binary. Recorded here for the audit trail (child did
NOT and must NOT edit `agents.json`):

```json
{
  "rsigma": {
    "label": "rsigma",
    "description": "Sigma toolchain MCP (`rsigma mcp serve`, MIT): parse/lint/validate/evaluate/convert Sigma rules. Host-gated on the rsigma binary (not on npm). Registered DEFAULT-OFF until the binary is on PATH. Detection-as-code, not exploitation.",
    "targets": ["claude"],
    "enabled": false,
    "transport": "stdio",
    "command": "rsigma",
    "args": ["mcp", "serve"],
    "credentialNames": [],
    "tags": ["approved", "claude-only", "local", "stdio", "security", "default-off"]
  }
}
```

If the parent ever needs to re-apply it, this is the exact intended block: `command` `rsigma`,
`args` `["mcp", "serve"]`, `enabled: false` until the binary is present. No secrets, no keys.

## Commits

- Skill (both trees + tests): `cbe20202a841374d8f7fdaec3e3ce637bb920dd1`
- Receipt skeleton: `985f2c99`
- This receipt (measured): appended on the next path-scoped commit to `W-blue.md`.

## Verify

```
export PATH="$HOME/.local/bin:$PATH"
ruff check .agents/skills/detection-as-code skills/detection-as-code
ruff format --check .agents/skills/detection-as-code skills/detection-as-code
python3 -m pytest .agents/skills/detection-as-code/tests/ -q
python3 -m pytest skills/detection-as-code/tests/ -q
diff -r .agents/skills/detection-as-code skills/detection-as-code
```
