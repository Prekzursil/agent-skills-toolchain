# harness/ast-integrate — capture ledger (02.09.2026)

Captured from the live tree `C:\Users\Prekzursil\source\ast-integrate` by
`scripts/sync-from-live.ps1 -Only ast-integrate` (the `ast-integrate` `$Map` area). The live tree is
FROZEN as the capture source from 02.09 02:30 EEST; from this capture on, `harness/ast-integrate`
is canonical for the P2 (G-1) repair, so a cloud Linux worker can run the 2007-unit measurement
straight from the repo instead of through the WSL bottleneck on the RAM-starved Windows box.

## Measured result (`-Report json`, run 05:40–05:53 EEST, rc=0, 0 errors)

| metric | value |
|---|---|
| files walked | 96,949 |
| captured (NEW) | 45,668 — 802 MB |
| excluded | 51,281 |
| files > 1 MB kept | 97 (all ≤ 5 MB, or on the KeepOversized list) |
| by top-level dir | command-center 709 MB · tools 27 MB · harness-sota-2026-07-18-corpus 23 MB · platform 17 MB · skills 11 MB · hooks 5 MB · docs 5 MB |
| by extension | .json 350 MB · .py 117 MB · .html 86 MB · .bin 60 MB · .body 59 MB · .md 56 MB · .raw 17 MB · .pdf 14 MB |

Before the exclusions the tree measured 84,000 files / 7.9 GB raw (89,352 files / 8.2 GB when
`node_modules`, `.pytest_cache`, `__pycache__`, `.venv` and `_chaos-scratch` are already left out).

## Exclusion rules and why each exists

Every rule below lives in the `ast-integrate` `$Map` entry of `scripts/sync-from-live.ps1`; this
file only explains it so a cloud agent can attribute a failing probe to a missing input.

| rule | value | reason |
|---|---|---|
| `MaxFileBytes` | 5 MB | anything larger is a blob fixture, a vendored binary or a pull, not probe input. Printed as TOO-LARGE. |
| `KeepOversized` | `command-center/WORK-UNIT-CATALOG.json`, `command-center/audit/AUD-0083-script-interpreter-audit.json`, `command-center/confirmation/CNF-0072-option-id-namespaces.json`, `command-center/receipts/CC-0019.json` | the work-unit catalog the regen tool loads directly, plus three 5–7 MB unit deliverables. |
| `ExtraExcludeDirs` | `deps`, `.bin`, `toolchains`, `wheels`, `_work`, `work`, `_scratch`, `scratch`, `_tmp`, `tmp`, `.cache` | vendored toolchains (semgrep/ruff/pwsh/trufflehog/gitleaks) and scratch/work dirs inside probe units. Measured: no directory of these names exists outside `probes/`. |
| `ExcludeRelPrefixes` | `Python/`, `_chaos-scratch/`, `command-center/p2-wave/ovh-monitor/error-pull/{extracted,extracted-delta,harvest,harvest-delta}/`, `command-center/p2-wave/probes/CNF-0021/tools/` | the bundled Python interpreter, chaos scratch, 3.7 GB of OVH fleet pulls, and one unit's 373 MB pwsh/ruff drop. |
| `KeepDirs` | `build`, `dist` | REAL SOURCE here (`command-center/build` holds the BLD-phase probes); the global junk-dir names must not fire. |
| `KeepFilePatterns` | `*.log` | the append-only repair log and the wave logs ARE the P2 audit trail. `.gitignore` carries the matching `!harness/ast-integrate/**/*.log` negation. |
| global | `node_modules`, `.pytest_cache`, `__pycache__`, `.venv`, Windows reserved device names (`NUL`, `CON`, …) | standard junk; a stray file literally named `NUL` exists in the live root and cannot be tracked on Windows. |

## What a cloud worker must know

- Probe measurement expects a Unix Python; the bundled Windows `Python/` interpreter is excluded on
  purpose. Use the repo's `pyproject`/`uv` environment.
- `.log` files under this tree are audit data, not noise: never delete or regenerate them.
- If a unit fails for a missing input, check the four `ExcludeRelPrefixes` first, then the 5 MB cap.
  The live tree still holds every excluded byte; the owner can add a `KeepOversized` entry and
  re-run `sync-from-live.ps1 -Only ast-integrate`.
- P2 state of record: `P2-REPAIR-PROGRESS_2026-08-27.md` and `HANDOFF-CLOUD-AGENT_2026-09-02.md`
  in the live `~/.agents` (captured on branch `live-capture/2026-09-02`).
