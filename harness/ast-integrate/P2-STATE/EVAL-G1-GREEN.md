# EVAL DEFINITION: P2 (G-1) loop-to-green — defined 02.09.2026 before repairs began

Eval-driven form of the owner's fail-closed definition of green (29.08 standing order +
02.09 cloud mandate). Written so the gate is a code grader, not a judgement call.

## Unit of evaluation
One work unit `<ID>` (2007 in `command-center/WORK-UNIT-CATALOG.json`). Grader:
`python3 command-center/p2-wave/_measure_one_delivered.py <ID>` executed in the mirror
(`~/p2-g1`, outside any git repo) → last line `SUCCESS:delivered <ID>`. Code grader, deterministic
except for load-sensitive probes (see regression eval R3).

## Capability evals (must become true)
- **C1 census:** one wave file `ovh-monitor/repair-claude/w0902-NN-census-*.jsonl` with 2007 rows,
  2007 unique ids, every row `ok: true`, produced by ONE run
  (`_g1_regen_par.py ALL <wave> --no-regen --placeholder=strict`) — never an overlay of waves.
- **C2 STRICT:** the census in C1 ran with `G1_PLACEHOLDER_MODE=strict` (row field `mode: strict`),
  so no passing unit loaded a generated `_NS` module directly or transitively.
- **C3 marker gate:** `grep -rl "# g1-surface: generated" --include=*.py` over every import root
  (repo root, tools/, platform/lib, tools/agentspec) returns 0 files that Python can resolve
  (dead never-resolvable files are deleted, not tolerated).
- **C4 independent recount:** `_g1_recount_native.py` re-reads the C1 file only (no overlay) and
  reports catalog_n = jsonl_unique = ok = 2007, fail = 0, missing = extra = 0, and the file's sha256.
- **C5 spot-check:** 12 ids re-measured serially, fresh, from the committed tree synced into a
  fresh mirror: 4 that were in the 27.08 fail set, 4 whose module was rewritten in this run, 4
  named by the false-green lens as the most permissive probes (ADV-0025, AUD-0037, ADV-0096 + one
  drawn at random); all 12 `SUCCESS:delivered`, STRICT on.
- **C6 pass^2:** C1 repeated once more from the same commit (fresh mirror sync) with an identical
  pass set (2007 = 2007). Two consecutive green censuses, not one.

## Regression evals (must stay true through every wave)
- **R1 no false regression:** a unit that was OK before a module repair and FAILS after it is a
  regression ONLY if it fails for a reason other than losing the permissive `_NS` (the STRICT
  trace of the module's importers is the regression set; a new failure whose tail names the
  rewritten module is a contract to satisfy, logged as such, not silently accepted).
- **R2 audit trail intact:** no `*.log` / `*.jsonl` under `ovh-monitor/` is deleted, truncated or
  rewritten; every wave appends rows and log lines (`git diff --stat` on those paths only adds).
- **R3 flake handling labelled:** every `probe-exit:124` row is re-run serially; the re-run row is
  labelled (`rerun: serial`) and both rows stay in the file. A serial pass after a parallel
  timeout is a pass; a serial timeout is a fail.
- **R4 no laundering:** `_g1_refresh_unit_sha.py` is never run; a manifest sha changes only in a
  commit that also regenerates the artifact via the unit's own `write_receipts.py` and re-measures
  the unit STRICT.
- **R5 tree = commit:** the final census, recount and spot-check run from a mirror synced from the
  committed tree (`git status --short` empty for `harness/ast-integrate` except ledgers being
  appended); no in-tree execution.

## Success metrics
- Capability: C1–C6 all PASS (pass^2 on C1).
- Regression: R1–R5 hold for every wave in the run history (`P2-REPAIR-PROGRESS_2026-08-27.md`).
- Run history: one row per wave in the ledger — wave name, ids, ok/fail, seconds, regressions,
  keep/revert decision, commit sha.

## Report (filled at the end)
_EVAL REPORT: pending — see the final ledger section._
