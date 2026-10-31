---
title: t12_per_line_deletion_audit
type: note
permalink: dqverify-repo-20261013/cyberstrike/tests/phase-battery/t12-per-line-deletion-audit
---

# T-12 per-line deletion audit — prompt template (owner-executed)

The Phase-3 rewrite deletes ~34 KB of instruction prose (6 files → 2).
MIGRATION-TABLE.md claims 175/175 clauses mapped, 0 unmapped. This audit is
the falsification pass: EVERY load-bearing line dropped from the old payload
must be individually accounted for. Run it in a FRESH session (Claude or
Codex) with repo read access. No edits — audit only.

## Inputs (give the auditor all five)

- Old payload: `AGENTS.md`, `config.md`, `CONTEXT.md`,
  `instructions-recon.md`, `instructions-fullpower-estate.md`
  (pre-switch live files; post-switch read them from `git show b7ab510:<path>`
  or the `backups/phase3_*/` copy).
- New pair: `AGENTS.new.md`, `CONTEXT.new.md`.
- Claim map: `MIGRATION-TABLE.md` (+ `scripts/migration_map.json`).

## Prompt template (paste verbatim)

```
You are auditing a contract rewrite for SILENT CAPABILITY LOSS. The old
instruction set (files: AGENTS.md, config.md, CONTEXT.md,
instructions-recon.md, instructions-fullpower-estate.md — read each fully)
was replaced by AGENTS.new.md + CONTEXT.new.md, with MIGRATION-TABLE.md
claiming every clause is mapped.

Procedure — line-oriented, no skipping:
1. Enumerate every load-bearing directive line in the old files: every rule,
   threshold, path, standing scope, hard ban, port, credential-shape rule,
   routing decision, or verification requirement. Ignore pure prose,
   headings, and stale-session references (ses_*, FINAL-REPORT_*,
   instructions-cursor-recovery content — those are the CONTAMINATION the
   rewrite removes, list them under "intentionally dropped" instead).
2. For each directive, find its successor: the exact section/line in
   AGENTS.new.md or CONTEXT.new.md that preserves it, OR the MIGRATION-TABLE
   row that relocates it (e.g. to HOME AGENTS.md), OR mark it
   INTENTIONALLY-DROPPED with the one-line justification.
3. Output a table: | old file:line | directive (<=12 words) | disposition
   (PRESERVED @new:line / RELOCATED @table-row / DROPPED because X) |.
4. Verdict: SUCCESS only if zero directives are UNMAPPED. Any directive you
   cannot place in one of the three dispositions is UNMAPPED — say so; do
   not stretch a mapping to force green. Explicitly check these known
   tripwires: NEVER-ROTATE, third-party-victim ban, isolated-profile-only
   browser rule, no-unsolicited-send, two-signal death rule, sha8+plaintext
   SSOT rule, scoped-finds RAM budget, precedent rows PC-1..PC-3.

Do not edit any file. Cite file:line for every disposition.
```

## Acceptance

- `UNMAPPED == 0` → audit SUCCESS.
- Any UNMAPPED load-bearing directive → fix AGENTS.new.md or the table, then
  re-run. A mapping that only works by paraphrasing away a rule is a FAIL.
- Known intentional drops to expect: the dead cursor-recovery runbook, stale
  session receipts, duplicate precedence banners, the fictional Daybreak-Red
  registration claims (CS-01).

## Recording

Save the auditor's table to `t12_audit_result.md` and the verdict line to
`t12_results.json` (`{"unmapped": N, "directives_total": N, "verdict":
"SUCCESS|FAILED"}`); ingest with
`python tests/phase_battery/run_battery.py --ingest-t12 t12_results.json`.