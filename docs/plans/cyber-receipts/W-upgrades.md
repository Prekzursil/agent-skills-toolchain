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

Measured with `diff -rq .agents/skills/<name>/ skills/<name>/` before editing.

- security-review dual-write present on this branch: YES (identical pre-edit)
- malware-analysis-triage dual-write present on this branch: YES (identical pre-edit)
- security-threat-model dual-write present on this branch: YES (identical pre-edit)
- Gaps (files not on this branch, edit-skipped): NONE — all three dual-writes exist; native-fuzz is net-new in both roots

## Deliverables

### 1. Trail of Bits scanner-driven review loop -> `security-review`

- Additive section added (no existing text gutted): YES — new `## Scanner-Driven Review Loop` section inserted before `## Resources`; all prior checklist content preserved
- Four techniques covered (static-analysis / differential / variant / mutation): YES — one Stage each, in order, each feeding the next
- CC-BY-SA attribution to Trail of Bits present, summarized not vendored: YES — attribution block cites Testing Handbook (appsec.guide), CC-BY-SA 4.0, original summary only
- Dual-write parity (`.agents/` == `skills/`): YES — `diff -rq` returns PARITY OK

### 2. YARA rules-as-code CI (yara-forge / yaraQA) -> `malware-analysis-triage`

- Additive section added (no existing text gutted): YES — new `## YARA Rules-as-Code CI` section before `## Related`; prior content (capa/FLOSS/ghidriff, Defensive Pairing, Gotchas, Workflow) preserved; only added a `$capa-triage` bullet to Related
- yara-forge + yaraQA + engine + expected-hit test corpora covered: YES — YARA-X engine, yaraQA linter, yara-forge tiers, expected-hit/expected-miss manifest, fail-closed CI pipeline
- License posture (wrap-don't-vendor; per-rule upstream licenses noted): YES — dedicated License posture subsection: no vendored rule bodies, per-rule upstream licenses in yara-forge packages, confirm tool repo licenses
- Dual-write parity: YES — `diff -rq` returns PARITY OK

### 3. Anthropic defending-code-reference-harness -> `security-threat-model`

- Additive section added (no existing text gutted): YES — new `## Defending-Code Review Flow` section before `## References`; the full 8-step workflow + risk-prioritization + references preserved
- `/threat-model` -> `/vuln-scan` -> `/triage` -> `/patch` flow points at existing skills (no new daemons): YES — stages wire to this skill, `$semgrep`/`$code-security`/`$security-review`, `$claim-verify-gate`; explicit "no new daemon/MCP/slash-command runtime" note
- Anthropic attribution present: YES — attribution block + References bullet cite claude-code-security-review; original summary, not vendored
- Dual-write parity: YES — `diff -rq` returns PARITY OK

### 4. NEW `native-fuzz` skill

- `SKILL.md` frontmatter is name+description only: YES — PyYAML parse confirms keys == {name, description}, name == `native-fuzz`
- `agents/openai.yaml` with quoted `display_name` / `short_description` / `default_prompt`: YES — all three present under `interface:`, quoted strings, PyYAML-valid
- `go test -fuzz` discipline promoted from `.agents/library/skills/golang-testing`: YES — FuzzXxx seed/property example, testdata/fuzz regression discipline, -race, replay; Related cites the library source
- ASan/UBSan/MSan build discipline promoted from `.agents/library/skills/cpp-testing`: YES — sanitizer table (ASan/UBSan/MSan/TSan), ASan+UBSan combined vs MSan/TSan separate builds, symbolizer/`*_OPTIONS` discipline; Related cites the library source
- libFuzzer/LibAFL preferred over AFL++ v5 (AGPL) with wrap-don't-vendor note: YES — Engine choice section: libFuzzer/LibAFL/honggfuzz permissive defaults; AFL++ v5 AGPL flagged, external-tool-only, wrap-don't-vendor, ties to G17
- Dual-write parity (`.agents/skills/native-fuzz` == `skills/native-fuzz`): YES — `diff -rq` PARITY OK; both roots have `SKILL.md` + `agents/openai.yaml`
- Markdown-only skill (no scripts) → no ruff/pytest required per wave rule "otherwise the skill is the artifact": YES

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
