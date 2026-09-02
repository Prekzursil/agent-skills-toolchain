# W-blue receipt

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: skill-exists, dual-write-identical, openai-yaml, helper-tests, ruff, parent-merge — all UNKNOWN

**Wave:** W-blue — new skill `detection-as-code` (Sigma authoring -> lint/validate -> oracle
backtest with expected-hit manifests -> convert -> ATT&CK coverage ledger).

**Owned paths (ONLY these):**
- `.agents/skills/detection-as-code/**`
- `skills/detection-as-code/**`
- `docs/plans/cyber-receipts/W-blue.md`

## Claims (rewrite at each milestone)

| Claim | Status |
|-------|--------|
| `.agents/skills/detection-as-code/SKILL.md` exists, frontmatter = name+description(+license) | UNKNOWN - not yet measured |
| `agents/openai.yaml` present, quoted display_name/short_description/default_prompt | UNKNOWN - not yet measured |
| Helper script (if shipped) has tests-first, fakes only, no live EVTX | UNKNOWN - not yet measured |
| Helper tests pass (count) | UNKNOWN - not yet measured |
| `ruff check` + `ruff format --check` clean on touched Python | UNKNOWN - not yet measured |
| Dual-write `skills/detection-as-code/**` byte-identical to canonical | UNKNOWN - not yet measured |
| Workflow covers: write Sigma -> lint -> oracle/backtest -> convert -> coverage ledger | UNKNOWN - not yet measured |
| Stop rules present (no always-on SIEM daemon; lab logs only; no live exploitation) | UNKNOWN - not yet measured |

## PARENT MERGE

Proposed `.agents/agents.json` block (parent applies; child does NOT edit agents.json).
Status: UNKNOWN - not yet measured.

## Commit

Commit SHA: UNKNOWN - not yet measured.
