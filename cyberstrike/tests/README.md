# tests/ — G-13 conformance battery (A+B+C stacked)

Owner-approved roadmap (grill decisions 2026-09-20, G-13): full T-1..T-13
battery + the 4-critical fast lane + garak-style JSONL verdict records.
Provenance: audit `wf_9356f9f5-6ff` defect registry + GRILL-DECISIONS_2026-09-20.md.
Repos: HEAD `b7ab510` (Phase-1 fixes), baseline `2c0f3c6` (pre-change).

## How to run

```powershell
cd C:\Users\Prekzursil\.config\cyberstrike

# 4-critical fast lane (T-1, T-3, T-4, T-6)
python tests\phase_battery\run_battery.py --lane critical

# everything runnable without the owner
python tests\phase_battery\run_battery.py --lane runnable

# whole battery (owner-protocol halves record PENDING-OWNER honestly)
python tests\phase_battery\run_battery.py --lane full

# single tests (each writes its own run dir)
python tests\phase_battery\t04_provider_truth.py
python tests\phase_battery\t02_budget.py --target drafts
```

Exit code 0 = no FAILED verdicts (PENDING-OWNER does not fail a run; it is
the honest state for owner-gated halves — never a silent pass).

Output goes to `D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase2-5\battery\<run_id>\`
(override with `CS_BATTERY_OUT`):
- `verdicts.jsonl` — one line per test attempt (garak-style), immutable
  vocabulary `SUCCESS | FAILED | INTERRUPTED | PENDING-OWNER`
- `hits.jsonl` — separate detector findings (dead servers, drift lines,
  stuck-call counts...): a finding is data, not a verdict
- `run_summary.json` — seal: per-status counts + sha256 of both files

`scripts/verdict_recorder.py` is the only writer (self-test:
`python scripts\verdict_recorder.py`). Anchors are re-read from disk at
record time; a SUCCESS whose promised artifact is missing is downgraded to
FAILED (fail-closed completion doctrine).

## The battery

| ID | Critical | What | State at build (2026-09-20) |
|----|----------|------|------------------------------|
| T-1 | YES | injection-count: AGENTS.md loads EXACTLY once | control PASS now (git-show: baseline 2 load sites → live 1); runtime half = owner at next TUI start (`--t1-prompt-dump`) |
| T-2 | | budget: pair ≤ 7500 B + zero stale tokens | runnable (drafts pre-switch, live post-switch; auto) |
| T-3 | YES | boundary determinism: 5 fixed probes × 5 fresh sessions | owner-executed protocol (`t03_boundary_determinism.md`), ingest `--ingest-t03` |
| T-4 | YES | provider-truth regression (Phase-1 detector wired in) | runnable, both-states via git-show |
| T-5 | | MCP preflight: t=0 dead-list + firing control port | runnable (localhost connect-only) |
| T-6 | YES | manifest id-correction vs p3 writer output | NOT-RUNNABLE-needs-manifest → PENDING-OWNER until Phase-3 wires `plugin/manifest-writer.ts`; script verifies shards once they exist |
| T-7 | | dead-end decline-and-cite | owner-executed protocol, ingest `--ingest-t07` |
| T-8 | | singleton attach via manifest liveness (G-12: lockfile cut) | PENDING-OWNER pre-manifest; process table observed read-only as single-signal context |
| T-9 | | terminal-state sweep (stuck `running` calls) | runnable (bounded census + self-test control) |
| T-10 | | orphan both-states (CS-2 present pre-patch / zero post-patch) | state A measured now; state B PENDING G-10 patch deployment |
| T-11 | | git drift gate (unstaged live edits vs SSOT) | runnable; control = planted drift in scratch clone |
| T-12 | | per-line deletion audit of AGENTS.new.md | owner-executed prompt template, ingest `--ingest-t12` |
| T-13 | | redundancy regression (NEVER-ROTATE==1 etc.) | runnable (drafts now; auto-switches to live pair) |

## Both-states doctrine (why controls are wired into everything)

A probe silent in both the broken and fixed state measures nothing
(single-signal-verification). Each runnable test carries its control:
T-1 git-show baseline (2x), T-4 baseline findings ≥2, T-5 control port
31198 must report dead, T-9 census `--self-test`, T-11 planted drift in a
scratch clone. T-10 IS the both-states gate for the orphan class.

## Notes / honest scope

- T-5 dead-at-t0 servers are HIT findings, not gate failures (a dead server
  is a preflight result; the gate is that the preflight works).
- T-13 research-surface: spec says ==1, drafts measure 0 (fully delegated to
  the HOME pointer). Threshold enforced is ≤1; deviation disclosed in the
  verdict details, not silently re-scored.
- T-2's assert target pre-switch is the DRAFT pair; the live pre-switch
  payload (37,171 B across the 5-file instruction set) is recorded as
  baseline context only.
- The running TUI (PID 19684 at build time) is never touched by any test.
