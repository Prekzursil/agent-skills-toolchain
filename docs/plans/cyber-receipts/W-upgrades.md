# W-upgrades receipt

**Wave:** W-upgrades (upgrades to existing skills + new `native-fuzz` skill)
**Branch:** `cursor/cyber-suite-full-program`
**Status:** UNKNOWN - not yet measured

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

## Scope (ONLY these paths)

- `.agents/skills/security-review/**` + `skills/security-review/**` (additive only)
- `.agents/skills/malware-analysis-triage/**` + `skills/malware-analysis-triage/**` (additive)
- `.agents/skills/security-threat-model/**` + `skills/security-threat-model/**` (additive)
- `.agents/skills/native-fuzz/**` + `skills/native-fuzz/**` (NEW)
- `docs/plans/cyber-receipts/W-upgrades.md` (this file)

## Dual-write parity precheck

- security-review dual-write present on this branch: UNKNOWN - not yet measured
- malware-analysis-triage dual-write present on this branch: UNKNOWN - not yet measured
- security-threat-model dual-write present on this branch: UNKNOWN - not yet measured
- Gaps (files not on this branch, edit-skipped): UNKNOWN - not yet measured

## Deliverables

### 1. Trail of Bits scanner-driven review loop -> `security-review`

- Additive section added (no existing text gutted): UNKNOWN - not yet measured
- Four techniques covered (static-analysis / differential / variant / mutation): UNKNOWN - not yet measured
- CC-BY-SA attribution to Trail of Bits present, summarized not vendored: UNKNOWN - not yet measured
- Dual-write parity (`.agents/` == `skills/`): UNKNOWN - not yet measured

### 2. YARA rules-as-code CI (yara-forge / yaraQA) -> `malware-analysis-triage`

- Additive section added (no existing text gutted): UNKNOWN - not yet measured
- yara-forge + yaraQA + engine + expected-hit test corpora covered: UNKNOWN - not yet measured
- License posture (wrap-don't-vendor; per-rule upstream licenses noted): UNKNOWN - not yet measured
- Dual-write parity: UNKNOWN - not yet measured

### 3. Anthropic defending-code-reference-harness -> `security-threat-model`

- Additive section added (no existing text gutted): UNKNOWN - not yet measured
- `/threat-model` -> `/vuln-scan` -> `/triage` -> `/patch` flow points at existing skills (no new daemons): UNKNOWN - not yet measured
- Anthropic attribution present: UNKNOWN - not yet measured
- Dual-write parity: UNKNOWN - not yet measured

### 4. NEW `native-fuzz` skill

- `SKILL.md` frontmatter is name+description only: UNKNOWN - not yet measured
- `agents/openai.yaml` with quoted `display_name` / `short_description` / `default_prompt`: UNKNOWN - not yet measured
- `go test -fuzz` discipline promoted from `.agents/library/skills/golang-testing`: UNKNOWN - not yet measured
- ASan/UBSan/MSan build discipline promoted from `.agents/library/skills/cpp-testing`: UNKNOWN - not yet measured
- libFuzzer/LibAFL preferred over AFL++ v5 (AGPL) with wrap-don't-vendor note: UNKNOWN - not yet measured
- Dual-write parity (`.agents/skills/native-fuzz` == `skills/native-fuzz`): UNKNOWN - not yet measured

## Validation

- `ruff` (only if Python scripts ship): UNKNOWN - not yet measured
- `pwsh validate-all-skills.ps1`: UNKNOWN - not yet measured (pwsh not installed in cloud per AGENTS.md)
- Frontmatter YAML sanity: UNKNOWN - not yet measured

## Safety posture

- No exploit code / PoCs authored: UNKNOWN - not yet measured
- No edits to `.agents/agents.json` or any other wave's files: UNKNOWN - not yet measured
- Existing skill text preserved (additive only): UNKNOWN - not yet measured

## Git

- Commit SHA(s): UNKNOWN - not yet measured
- Files changed: UNKNOWN - not yet measured

## PARENT MERGE

None required for this wave (no shared-file edits; no MCP registrations).
