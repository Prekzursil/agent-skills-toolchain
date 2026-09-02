# W-0day receipt — `vuln-research-loop` skill

**Wave:** W-0day (0-day / vulnerability-research harness loop).
**Branch:** `cursor/cyber-suite-full-program`.
**Owner files (ONLY these):** `.agents/skills/vuln-research-loop/**`,
`skills/vuln-research-loop/**`, `docs/plans/cyber-receipts/W-0day.md`.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: none UNKNOWN — all sections below measured 2026-09-02.

## Status

DONE — skill authored, dual-written, and validated. Markdown/YAML-only (no scripts),
so ruff and smoke tests are N/A per shared rule 3 ("the skill is the artifact").

## Deliverable checklist

| Item | Status |
|------|--------|
| Receipt skeleton written first | DONE (skeleton committed before skill body) |
| `.agents/skills/vuln-research-loop/SKILL.md` (Naptime-style loop) | DONE (169 lines) |
| `.agents/skills/vuln-research-loop/agents/openai.yaml` | DONE (`interface:` block, quoted values) |
| `.agents/skills/vuln-research-loop/references/upstream.md` | DONE (upstream links, wrap-not-vendor) |
| Dual-write `skills/vuln-research-loop/**` | DONE — `diff -r` reports IDENTICAL |
| Links to existing RE MCP skills (no duplication) | DONE — ghidra/ida/binja/angr/qiling/frida all linked via `$skill` |
| ClusterFuzzLite / Atheris / CASR / OSS-Fuzz-Gen wraps documented | DONE (wraps table + upstream.md) |
| Jackalope / TinyInst Windows-closed-source notes | DONE (owner-owned-only row) |
| Patch-diff → variant via ghidriff/bindiff | DONE (dedicated pipeline section) |
| Sanitizer discipline pointer + link to `native-fuzz` (parent-owned) | DONE — ASan/UBSan/MSan pointer; defers to `$native-fuzz`, does NOT create it |
| Frontmatter is `name`+`description` only | DONE — measured keys: `['name', 'description']` |
| No exploit / PoC / payload / C2 / attack-procedure content | DONE — see banned-word scan below |
| Stop rules (third-party binaries out of scope) present | DONE ("Scope and safety" + "Common mistakes") |

## Safety slice (Claude cyber safeguards)

NO SLICE TAKEN. The whole deliverable is defensive (find-and-fix fuzzing, crash triage,
patch-diff variant hunting on owner-owned code), which is within policy, so no
exploit-adjacent section had to be omitted. The skill was authored with the HARD ban
already baked in: it explicitly refuses to produce exploits, PoCs, payload/shellcode
generators, C2, or attack procedures, and defines "reproduce the crash" as *run the
crashing input back through the fuzzer/sanitizer*, never exploitation.

## Validation (measured 2026-09-02)

- **Frontmatter keys** (parsed): `['name', 'description']` — matches the `.agents` skill
  contract (only `name` + `description`).
- **Dual-write:** `diff -r .agents/skills/vuln-research-loop skills/vuln-research-loop`
  → IDENTICAL (3 files each: `SKILL.md`, `agents/openai.yaml`, `references/upstream.md`).
- **`agents/openai.yaml`:** parses as YAML; `interface:` block with quoted
  `display_name` / `short_description` / `default_prompt` (matches `ghidra-mcp`, `angr`).
- **Link targets:** every `$skill` reference resolves to an existing skill dir EXCEPT
  `$native-fuzz`, which is **intentionally absent** — it is parent/W-upgrades-owned and
  this wave links it rather than creating it (per the wave brief). All RE MCP links
  (`$ghidra-mcp`, `$ida-pro-mcp`, `$binary-ninja-mcp`, `$angr`, `$qiling-emulation`,
  `$frida-mcp`, `$bindiff`, `$binexport`, `$radare2`, `$re-ensure`,
  `$reverse-engineering-toolkit`, `$capa-triage`, `$malware-analysis-triage`,
  `$claim-verify-gate`, `$owner-ops-authorization`) resolve OK.
- **Banned-word scan:** `grep -niE "exploit|payload|shellcode|C2|proof-of-concept|PoC|weaponi|attack proc"`
  returns 11 hits; every one is in a prohibition/negation context ("no exploits",
  "not exploitation", "will NOT produce", "not an exploit", "never a working exploit").
  No affirmative exploit/payload/C2/attack-procedure content.
- **Scripts:** none. No `*.py`/`*.sh` in the owned paths → ruff 0.15.17 and smoke tests
  are N/A (Markdown/YAML-only skill).

## Commit

Two path-scoped commits on `cursor/cyber-suite-full-program` (no `--no-verify`, no
edits outside the owned paths):

- Commit 1 — the skill: `.agents/skills/vuln-research-loop/**` + `skills/vuln-research-loop/**`.
- Commit 2 — this receipt: `docs/plans/cyber-receipts/W-0day.md`.

SHAs are recorded in `git log` and on push to `origin/cursor/cyber-suite-full-program`.

## PARENT MERGE

NONE. This wave ships no `.agents/agents.json` change, no parked-companion change, and no
control-plane test delta. The `native-fuzz` skill is parent/W-upgrades-owned and is only
linked (`$native-fuzz`), not created here. Nothing for the parent to merge.
