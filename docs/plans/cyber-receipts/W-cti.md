# W-cti receipt

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: ALL sections UNKNOWN - not yet measured

Wave: **W-cti** — deliver skill `cti-lookup` (borrow cti-expert defang/refang +
STIX 2.1 export + report skeleton; route to osint `vt_*`, cve-mcp, and the
darknet-mcp-server full 66-tool surface). Do NOT install a 67-command orchestrator.

Owned paths (ONLY these):
- `.agents/skills/cti-lookup/**`
- `skills/cti-lookup/**`
- `docs/plans/cyber-receipts/W-cti.md`

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Receipt skeleton written | DONE 2026-09-02 |
| 2 | Tests-first (no network) authored | DONE 2026-09-02 |
| 3 | defang/refang + STIX export implemented, tests green | DONE 2026-09-02 |
| 4 | SKILL.md + references (routes, report skeleton) | UNKNOWN - not yet measured |
| 5 | agents/openai.yaml | UNKNOWN - not yet measured |
| 6 | ruff 0.15.17 check + format clean | UNKNOWN - not yet measured |
| 7 | Dual-write `skills/cti-lookup/` verified identical | UNKNOWN - not yet measured |
| 8 | Path-scoped commit + push | UNKNOWN - not yet measured |

## Test results

`python3 -m pytest .agents/skills/cti-lookup/tests/ -q` -> **40 passed** (~0.10s),
stdlib-only, no network. Suites:
- `test_ioc_defang.py` — defang/refang + roundtrip property; offline IOC extraction
  (IPv4/URL/email/domain/MD5/SHA-1/SHA-256/CVE), domain-in-URL/email de-dup, CLI.
- `test_stix_export.py` — STIX 2.1 patterns, quote-escaping, deterministic
  indicator/vulnerability ids (uuid5 over type:value), bundle assembly + ordering, CLI.

## Ruff

`ruff 0.15.17` on `.agents/skills/cti-lookup/`: `ruff check` -> All checks passed;
`ruff format` applied, `ruff format --check` -> 4 files already formatted.

## Routes documented (real tool names)

UNKNOWN - not yet measured

## Commit SHA

UNKNOWN - not yet measured

## PARENT MERGE

Parent owns `darknet-mcp-server` registration in `.agents/agents.json` (already
enabled per G6, full 66-tool search). This wave only documents the route; it adds
no registry blocks. UNKNOWN - not yet measured whether any parent action remains.
