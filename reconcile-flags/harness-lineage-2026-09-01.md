---
title: harness-lineage-2026-09-01
type: note
permalink: dqverify-repo-20261013/reconcile-flags/harness-lineage-2026-09-01
---

# FLAG: two diverged harness lineages, and no Cursor provider in either

> **RESOLVED 2026-09-02 (decision 1), kept rather than deleted:** the reunion landed in
> `harness-lineage-reunion-2026-09-02.md` — every file classified against a three-way
> base, the live tree's fixes ported into `agent-self/harness` with tests (834 -> 926
> passing), `.agents/harness` refreshed to the reunited result (926 passing, was 1
> collection error + 19 failures), and a repo->live deploy plan with a timestamped
> backup step. Decision 2 (Cursor adapter) is NOT built; it is filed as
> `cursor-provider-followup-2026-09-02.md`. One number below is superseded by that
> measurement: the fresh 2026-09-02 capture ran **767** passed against its own tests
> (not 485 — the 08-28 capture had also missed three suites), with the same 1 error +
> 19 failures.

Filed 2026-09-01. **Nothing was mashed.** Both trees are left exactly as they are;
this records what was measured so the owner can decide the reconcile direction.
Same discipline as `import-2026-08-28/` — flag genuine conflicts, never merge them
blind.

## 1. The two trees

| | `agent-self/harness` | `.agents/harness` |
|---|---|---|
| role | maintained source; the ONLY one CI runs (`.github/workflows/quality.yml`, `python -m pytest agent-self/harness/tests`) | live capture folded in by `15905d35` (2026-08-28) |
| suite (measured 2026-09-01, py3.12) | **834 passed, 1 skipped** | **1 collection error + 19 failed**, 485 passed, 1 skipped |
| `ruff format --check` | 36/36 clean | was 2 files dirty (formatted in this change) |
| `adapters.py` | 244 lines | 299 lines |
| `dispatcher.py` | 585 lines | 683 lines |
| `ledger.py` | 1327 lines | 1542 lines |
| `modules.py` | 3691 lines | 3653 lines |

The live estate executes the `.agents/harness` lineage: `~/CLAUDE.md` and the
Cursor customize audit both name `C:/Users/Prekzursil/.agents/harness/dispatcher.py`
as the hook dispatcher every lifecycle event routes through.

## 2. The captured tree pairs NEW tests with OLD code

The 20 failures are not flaky and not platform artifacts — they are API mismatches
in one direction, which identifies the lineage:

| symbol | `agent-self/harness` | `.agents/harness` | consequence |
|---|---|---|---|
| `RegisterGateModule` (in `modules.py`) | present | **absent** | `.agents/harness/tests/test_register_gate.py` dies at COLLECTION: `ImportError: cannot import name 'RegisterGateModule'` |
| `deploy(..., skill_surface_roots=...)` (in `install.py`) | present (4 refs) | **absent** | 15 `test_surface_reconciler.py` failures, all `TypeError: deploy() got an unexpected keyword argument 'skill_surface_roots'` |

Remaining 4 failures: 3 in `test_cov_ledger.py`, 1 in `test_cov_final.py`.

Test trees are also different sets: 8 files byte-identical, 11 differing;
`test_cov_install_small.py`, `test_deploy_command_center.py`, `test_modules.py`,
`test_security_regressions.py` exist only under `agent-self`, while
`test_dispatcher_degraded_health.py`, `test_fix_n_session_flags.py`,
`test_ledger_process_recovery.py` exist only under `.agents`.

**Reading:** the live harness is BEHIND the maintained one on at least the register
gate and the skill-surface-roots deploy path, while carrying live-only work of its
own (the three extra suites). Neither side is a superset, so this is a real
reconcile, not a copy.

## 3. Reproduce

```bash
python -m pytest agent-self/harness/tests -q                 # 834 passed, 1 skipped
python -m pytest .agents/harness/tests -q                    # 1 collection error
python -m pytest .agents/harness/tests -q \
  --ignore=.agents/harness/tests/test_register_gate.py       # 19 failed, 485 passed
```

## 4. No Cursor provider exists in EITHER tree

Measured: `rg -i cursor` over both harness trees, code and tests, returns **zero
matches**. Provider strings present:

- `agent-self/harness/adapters.py` → `claude`, `codex`
- `.agents/harness/adapters.py` → `claude`, `codex`, `grok`

So the shared harness is genuinely not inter-tool for Cursor. What Cursor actually
has (Wave B, 2026-08-27) is `~/.cursor/hooks.json` calling two standalone
PowerShell scripts — `.agents/scripts/cursor-hooks/shell-guard.ps1` and
`cursor-hook-log.ps1` — both observe-only, `failClosed: false`, and neither routes
into `harness/dispatcher.py`. The repo already says as much in other words:
`CONSOLIDATED-GEM-DECISIONS_2026-08-27.md` ("~40 Claude hook families and **zero**
on the Cursor side"), `CROSS-RUNTIME-SCORECARD_2026-08-27.md` (Cursor parity is
"transitive through the Claude materialization" — i.e. skills only).

**What IS shared across Cursor / Claude / Codex today:** the skills vault
(`.agents/skills`), the behaviour contract (`AGENTS.md` / `CLAUDE.md`), and the MCP
registry (`agents.json`, rendered per target). **What is NOT:** the hook/event
harness — ledger, goal re-injection, recall gate, register gate. A Cursor session
therefore gets the same tools and rules but none of the lifecycle enforcement.

## 5. Decision needed (owner)

1. **Reconcile direction** for the two harness lineages — fold `.agents/harness`'s
   three live-only suites into `agent-self/harness`, then redeploy `agent-self`
   (CI-green, and it carries the register gate + skill-surface-roots deploy) to
   live? That is the only direction that ends with one tested tree.
2. **Cursor adapter** — is a `cursor` provider in `adapters.py` + a dispatcher entry
   point wanted, replacing the two observe-only PowerShell hooks? The council
   gated the enforce/`failClosed` flip on ~1 week of
   `cursor-shell-guard.jsonl` latency evidence; a read-only adapter is not gated by
   that and would close the asymmetry on its own.

Neither is done here: both change what runs on every live session, and the measured
guard-hook latency on this box was already 4806 ms under RAM pressure against a 2 s
Cursor hook timeout.