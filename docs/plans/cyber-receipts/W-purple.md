# W-purple receipt

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: all sections MEASURED (0 UNKNOWN remaining).

Wave: **W-purple** — skill `purple-emulation` (adversary emulation + detection validation, lab/owned only).
Branch: `cursor/cyber-suite-full-program`.
Owned paths (ONLY): `.agents/skills/purple-emulation/**`, `skills/purple-emulation/**`, `docs/plans/cyber-receipts/W-purple.md`.

## Deliverables

| item | status |
|---|---|
| Canonical `.agents/skills/purple-emulation/SKILL.md` | DONE — frontmatter `name`+`description`+`license` only; scope-first gate; the 6-step loop; checker usage; stop rules |
| `agents/openai.yaml` (quoted display_name/short_description/default_prompt) | DONE — dual-written, quoted strings |
| ART / Invoke-Atomic runner docs (range VM / owner lab only) | DONE — `references/atomic-red-team.md`; reference-by-technique/GUID, snapshot+isolate+cleanup, no reproduced payloads |
| Detection assertion via `claim-verify-gate` (did the detection fire?) | DONE — `references/detection-assertion.md`; source=emulation, verify=SIEM/EDR (mechanically different) |
| Expected-hit manifest pattern | DONE — JSON schema in `references/detection-assertion.md`; consumed by `detection_coverage.py` |
| ATT&CK Navigator / DeTT&CT coverage ledger | DONE — `references/coverage-ledger.md`; `--navigator` emits v4.5 layer; DeTT&CT input mapping documented |
| Stratus Red Team (owner cloud only) | DONE — `references/cloud-and-caldera.md`; owner-account only, `${AWS_PROFILE}` env-name only, detonate→revert |
| CALDERA framed as range REST (NOT fleet MCP / always-on daemon) | DONE — `references/cloud-and-caldera.md`; explicit "NOT registered in `.agents/agents.json`", on-demand REST |
| Stop rules (H1 no third-party; H2 no C2/stealer/ransomware/exploit PoC; HexStrike = execution plane) | DONE — `references/stop-rules.md` + SKILL.md stop-rules section |
| Dual-write under `skills/purple-emulation/**` | DONE — `diff -r` byte-identical (9 files each side; 18 files total) |
| Ruff 0.15.17 check + format on any Python | DONE — `ruff check` all passed; `ruff format --check` clean on both trees |
| Script + offline tests (if any code shipped) | DONE — `scripts/detection_coverage.py` + `scripts/test_detection_coverage.py`, 10/10 pass |
| Frontmatter = only `name`+`description` (+ optional `license`) | DONE — matches `capa-triage`/`gtfobins-lookup` license convention |

## Measured verification (2026-09-02, cloud VM, python3 + ruff 0.15.17)

- `detection_coverage.py --self-test` → PASS on all 7 checks ("checker discriminates"): a fired
  detection yields DETECTED/gate-PASS, a silent one yields MISSED/gate-GAP, and the two differ
  (both-states discipline — a checker silent in both states measures nothing).
- `test_detection_coverage.py` → **All 10 tests passed** (verdict matrix DETECTED/PARTIAL/MISSED/
  UNVERIFIED; technique worst-case rollup; 3 result-file formats; invalid-manifest ValueError;
  Navigator layer colours/scores; ledger shape; CLI exit codes 0/1/2).
- **Cross-skill chain confirmed:** the ledger emitted by `--ledger` is accepted by the sibling
  `claim-verify-gate/scripts/claim_gate.py` → `violations=0 gate=PASS` (integration test in the
  suite runs it and asserts exit 0; guarded to SKIP if claim_gate is absent).
- Exit codes: `0` no gap · `1` MISSED/PARTIAL gap exists · `2` unusable input (all exercised).

## Safeguard status

No Claude cyber safeguard blocked this wave. The deliverable is defensive by construction —
an **emulation catalog + detection-validation harness** on owner-owned infrastructure. It ships
NO payload generators, NO C2 setup, NO exploit code; atomic commands are referenced by ATT&CK
technique id / Atomic GUID rather than reproduced. The full requested subset was delivered.

## Files created (18)

Canonical `.agents/skills/purple-emulation/` (9) + dual-write `skills/purple-emulation/` (9):

```
SKILL.md
agents/openai.yaml
references/atomic-red-team.md
references/detection-assertion.md
references/coverage-ledger.md
references/cloud-and-caldera.md
references/stop-rules.md
scripts/detection_coverage.py
scripts/test_detection_coverage.py
```

## Commit

Implementation commit (skill, canonical + dual-write, 18 files):
`d2fe1f749585924bf1185e817d7ecf9b10b8ec9d` on `cursor/cyber-suite-full-program`.
This receipt lands in a follow-up path-scoped commit on the same branch.

## PARENT MERGE

**None required.** This wave ships a Markdown skill + a stdlib checker only. There is no
`.agents/agents.json` registration for this wave: CALDERA is documented as an **on-demand range
REST endpoint**, explicitly NOT a fleet MCP and NOT an always-on daemon, so nothing is added to
the MCP SSOT. Stratus/CALDERA/ART are referenced (not vendored); secrets are env-NAME only
(`${AWS_PROFILE}`, `${CALDERA_API_KEY}`). Detection gaps found by this skill route to the
`detection-as-code` wave (W-blue), not to the registry.
