# Migrating to longhaul

longhaul folds four predecessors into one tool. This page maps each one to its
replacement, says what was dropped on purpose, and covers moving existing state.

## 1. `tools/account-hopper` (merged in #396 and #397; retired in this PR)

| account-hopper | longhaul |
|---|---|
| `--config` / `ACCOUNT_HOPPER_CONFIG` | `--config` / `LONGHAUL_CONFIG` |
| `--ledger` / `ACCOUNT_HOPPER_LEDGER` (default `spend.jsonl` beside the config) | `--state-dir` / `LONGHAUL_STATE_DIR` (default: the config's directory). The ledger keeps the name and format, `spend.jsonl`. |
| config keys `accounts[].profile/cap_usd/funded/note`, `global_ceiling_usd`, `min_headroom_usd` | Unchanged. An account-hopper config loads as is. New keys, all optional: `pause_margin_usd` (config or account), `accounts[].closed`, `accounts[].meter`, `spend_source`, `meter`, `cycle`. |
| `status` | `status`. It now also shows each account's line and any pause. |
| `record` | `record`; use `--profile` where you used `--account`. |
| `select [--strategy order\|most-remaining]` | **Removed.** `check --profile P [--projected-usd X]` answers for the account you chose: it prints P on yes, or gives exit 3 and a reason. |
| `hop`, `hopper_launch.ps1`, `-MaxHops` | **Removed by design.** There is no automatic hop on drain and no free-credit rotation. Run `check` or `run --profile` on the account you choose next. |
| `MODAL_TOKEN_*` unsetting (#397) | Kept, in `run` and `watch`: the child (or the watch process) gets `MODAL_PROFILE=P`, with `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` removed. |
| ceiling fix: `effective_remaining_usd = min(account room, ceiling room)` | Kept, now measured to the pause lines: `min(line - spent, global line - total)`. The $60 / $58 / $8 regression test is ported. |
| `MIN_TESTS` floor in the test runner | Kept in both longhaul runners. |
| exit codes 0 / 2 / 3 | Same meaning. 3 now also covers a pause during `watch`. |

**Moving your state.**
1. Copy `config.json` and `spend.jsonl` into one directory.
2. Optionally add `"pause_margin_usd"` to the config.
3. Point `LONGHAUL_CONFIG` at the config. Nothing else changes.

## 1b. The hop loop, restored caller-side (`modal_hopper_launch.ps1`)

Owner directive 2026-10-30: the phenibut-grade automatic hop comes back as a
THIN wrapper over `run`, not as core behavior. `tools/longhaul/modal_hopper_launch.ps1`
loops the config's funded accounts through `longhaul run --profile P`, so
budgeting/pausing/recording still flows through the core; exit 0 stops the
loop, exit 3 hops to the next funded account. It is Modal-specific (hence
the name, per the same directive): it pre-flights every enrolled profile
against `~/.modal.toml` and refuses to hop blind on a name mismatch. The
core budget/checkpoint/config layer stays provider-general.

## 2. modal-budget-ledger PR 2, the measured layer (never merged)

The patch is `pr2-measured-layer.patch`, with `modal_spend.py` beside it, in the
steward's work directory.

| PR 2 | longhaul |
|---|---|
| `modal_spend.py` (`fetch_spend`, `fetch_spend_cached`, `parse_summary`, `child_env`, `validate_profile`) | `longhaul_measure.py`, same functions. It adds `cycle_key` and the high-water store (`read_highwater`, `raise_highwater`, `measure_accounts`). |
| `spend_source` / `meter` / `cycle` config keys, per-account `meter` | Unchanged. |
| `--no-measure`, `--cache`, `--cache-ttl` | `--no-measure` and `--cache-ttl`. The cache file is `spend-cache.json` in the state dir. |
| measured figure used as-is | **Changed.** The decision figure is the maximum ever read for that account in that month (`highwater.json`), because readings fall as well as rise. |
| `select --projected-usd` | `check --projected-usd` and `run --projected-usd`. |

## 3. durable-checkpoint (closed PR #398, branch `feat/durable-checkpoint`)

- **Module.** `durable_checkpoint.py` becomes `longhaul_checkpoint.py`. Change the
  import; the public API is identical:
  - `DurableCheckpoint`, `has_checkpoint`, `latest_verified`, `resume_into`,
    `verify`, `verify_generation`;
  - `generations`, `gen_dir`, `gen_name`, `manifest_path`, `clear_work_dir`,
    `CheckpointError`.
- **Durable directories.** The manifest name and format are unchanged
  (`MANIFEST.durable-checkpoint.json`, version 2), so a directory written by
  durable-checkpoint resumes under longhaul as is.
- **Behaviour changes.** These are the seven rows of
  `spec_longhaul_checkpoint.py`, which moved here from the branch:
  1. Retention counts only loadable generations. Torn ones older than the newest
     are deleted.
  2. Links come only from generations this process read back in full. A
     read-back failure on a linked file distrusts the link base and recopies.
     `MirrorResult.repaired` counts the recopied files.
  3. A signal waits at most `SIGNAL_LOCK_BUDGET_S` (0.25 s) for the mirror lock.
     Otherwise it skips the final and counts it in `skipped_finals`.
  4. A malformed manifest or unreadable file refuses that generation, never
     raises. Unsafe manifest paths (`..`, absolute) are refused too.
  5. One signal writes one final. Neither the signal path nor `stop()` prunes.
  6. `stop()` restores exactly the handlers `start()` installed.
  7. `resume_into` restores recorded mtimes and re-hashes every hydrated file.
- **Tests.** The branch's 41 tests are ported unchanged in
  `test_longhaul_checkpoint.py`, plus 10 new ones.

## 4. The fractal-compute steward's scripts

These are `profiles.py`, `budget_guard.py`, `watchdog.py` and `lanes.py`, in the
steward's Modal work area.

| steward | longhaul |
|---|---|
| `THRESHOLD_USD[p] - MARGIN_USD` (42.50 - 3.00 = 39.50) | `accounts[].cap_usd` + `pause_margin_usd` give `line_usd`. |
| `budget_guard.py PAUSE_AT PERIOD`; total pause at $123 | `global_ceiling_usd` and `watch`. The total pauses at ceiling − margin, so keep the $123 pause with `global_ceiling_usd: 126` and a $3 margin. |
| `spend_highwater.json` (max metered ever read) | `highwater.json`, keyed by month and `profile/meter`. |
| `CLOSED = {...}` | `accounts[].closed: true`. |
| `pick_account()` router | **Removed.** The profile is always the caller's explicit `--profile`. |
| `watchdog.py`: respawn only finished errors, same account, at most N, leave `FAILURE`-while-pending alone | `watch`, with the same rules. Respawning is opt-in per call through `max_respawn` and a recorded `spawn` recipe. |
| `client_for()` token resolution | **Removed.** longhaul handles no tokens. It scopes a process with `MODAL_PROFILE` and strips `MODAL_TOKEN_*`. |
| `calls.jsonl` with `stopped` markers | The same idea: `watch` reads and appends the call ledger. |

The steward's durable budget state now lives outside the repo, in the user's
state directory. That directory holds the high-water marks, the call ledger,
and a longhaul config naming the funded accounts. Account names are not
committed here.
