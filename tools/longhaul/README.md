---
title: README
type: note
permalink: dqverify-repo-20261013/tools/longhaul/readme
---

# longhaul

Run long cloud jobs on accounts **you fund**, without losing work to a preemption
and without spending past the lines you set. One stdlib-only tool in four parts:

| Part | Module | What it does |
|---|---|---|
| budget | `longhaul_budget.py` | Per-account pause lines plus a global ceiling. Answers "may new work start on this profile, and can it fund a job this size?" and "must running work here pause now?" |
| measure | `longhaul_measure.py` | Reads real spend from `modal billing summary --json --profile P --for <month>`, and keeps the high-water mark per account and month. |
| watch | `longhaul_watch.py` | A preemption-safe watchdog for one profile. It pauses that profile's calls before the cap and respawns only calls that finished with an error, on the same profile. |
| checkpoint | `longhaul_checkpoint.py` | Mirrors a job's scratch directory into numbered generations on a durable path, and resumes from the newest one that verifies. |

`longhaul.py` is the CLI over all four. It replaces `tools/account-hopper`, the
unmerged modal-budget-ledger measured layer, the closed durable-checkpoint PR (#398)
and the fractal-compute steward's guard and watchdog scripts. See
[MIGRATION.md](MIGRATION.md).

## Scope decisions (each one deliberate)

| Decision | Why |
|---|---|
| **The profile is chosen per invocation, by you.** Every command that acts on an account takes `--profile`. | Switching accounts is a decision with consequences (volumes are per-workspace, credits differ). It belongs to the user. |
| **No automatic hop on drain, and no free-credit rotation.** When an account reaches its line the answer is exit 3 with the reason. Nothing names a different account. | Account-hopper's `hop` and `hopper_launch.ps1` did exactly this. They are retired, not ported. |
| **Measured spend, kept as a high-water mark.** | Hand-recorded spend drifts the moment a job dies unrecorded. Modal's readings are not monotone: one account read 38.31 and then 38.08. A decision on a falling reading hands back money already spent. |
| **Pause before the cap.** Each account pauses at `line = cap_usd - pause_margin_usd`. The global total pauses at `global_ceiling_usd - pause_margin_usd`. | A clean cancel at the line lets the job stop at a checkpoint. The provider's hard stop does not. |
| **Watch never cancels a call that only looks failed.** | After a preemption Modal restarts the input itself. Its status can read FAILURE for 13-20 min while `get(timeout=0)` still times out. Cancelling then kills a live restart. |
| **Checkpoints verify on read.** Resume re-hashes every file it hydrates, and links come only from fully read-back generations. | A checkpoint that loads corrupt state wastes the hours it was meant to save. |
| **No credentials.** longhaul knows profile names only. To act on a profile, it sets `MODAL_PROFILE` and strips `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` for the child (or its own process in `watch`). | Ambient `MODAL_TOKEN_*` silently override the profile, so every call meters or runs on the wrong account. |
| **No provider limits.** Every threshold comes from your config. | A budget is a number you chose. |

## Config

A JSON file you author, named by `--config PATH` or `LONGHAUL_CONFIG`. There is
no implicit default. State lives beside it unless you pass `--state-dir`:
- `spend.jsonl`: the ledger;
- `highwater.json`;
- `spend-cache.json`.

```json
{
  "spend_source": "measured",
  "meter": "metered",
  "cycle": "this month",
  "pause_margin_usd": 3.0,
  "global_ceiling_usd": 126.0,
  "min_headroom_usd": 0.0,
  "accounts": [
    {"profile": "acct-a", "cap_usd": 42.5, "funded": true, "closed": true, "note": "spent; in-flight only"},
    {"profile": "acct-b", "cap_usd": 42.5, "funded": true},
    {"profile": "acct-c", "cap_usd": 42.5, "funded": true}
  ]
}
```

- `funded` is required and must be explicit. Set it `true` only for an account
  you fund. An unfunded account is never measured and never gets work.
- `closed: true` keeps an account visible and measured, but refuses it new work.
- `pause_margin_usd` can be set per account to override the config-level value.
- `spend_source: "ledger"` (the default) uses recorded spend only.
  `"measured"` reads every funded account each time a decision needs the total,
  through a 240 s cache (`--cache-ttl`). `--no-measure` forces the ledger.
- An account-hopper config loads unchanged. With no margin, the line is the cap.

## Use

```bash
# What have I got, and must anything pause?
python longhaul.py --config ~/state/longhaul.json status

# May a ~$6 job start on acct-b? (prints the profile on yes, exit 3 + reason on no)
python longhaul.py --config ~/state/longhaul.json check --profile acct-b --projected-usd 6

# Check, then run a command scoped to acct-b (MODAL_PROFILE set, MODAL_TOKEN_* stripped)
python longhaul.py --config ~/state/longhaul.json run --profile acct-b --projected-usd 6 -- \
    modal run my_job.py

# Watch acct-b's calls: pause before the cap, respawn only finished errors
python longhaul.py --config ~/state/longhaul.json watch --profile acct-b \
    --calls ~/state/calls.jsonl --period 180

# Read real spend now and raise the high-water marks
python longhaul.py --config ~/state/longhaul.json measure

# Record a cost by hand (ledger source, or a correction note)
python longhaul.py --config ~/state/longhaul.json record --profile acct-b --usd 1.10 --job-id j3

# Checkpoints, no config needed
python longhaul.py checkpoint mirror --work /scratch/job --durable /vol/job-ckpt
python longhaul.py checkpoint verify --durable /vol/job-ckpt
python longhaul.py checkpoint resume --work /scratch/job --durable /vol/job-ckpt
```

Exit codes: `0` fine · `2` bad invocation or config · `3` refused, or paused, by
budget. A failed measurement is exit 2: it never reads as zero.

### The call ledger `watch` reads

`calls.jsonl` holds one JSON object per line, written by your launcher when it
spawns a call:

```json
{"group": "lane", "label": "shard 7", "profile": "acct-b", "call_id": "fc-...",
 "max_respawn": 2,
 "spawn": {"app": "my-app", "function": "work", "args": [7], "kwargs": {}, "options": {"cpu": 2.0}}}
```

`max_respawn` defaults to 0, so a call is never respawned unless its launcher
opted in. A call that must not resume across a preemption (a certifying checker,
say) simply leaves it at 0. `watch` appends its own rows:
- a `stopped` marker for each paused or abandoned call;
- the new call for each respawn, with `replaces`.

The ledger stays the full record.

### Checkpoints as a library

```python
from longhaul_checkpoint import DurableCheckpoint, has_checkpoint, resume_into

ckpt = DurableCheckpoint(work, durable, interval_s=600, commit=volume.commit)
if has_checkpoint(durable):
    resume_into(durable, work)   # newest generation that verifies; refuses rather than load corrupt state
with ckpt:                       # periodic mirror + one final on SIGINT/SIGTERM
    run_the_job()
```

The design, the trap it avoids, and the cost model are in the module docstring.

## Tests and acceptance

```bash
python test_longhaul.py              # budget, measure, watch, CLI: 43 tests
python test_longhaul_checkpoint.py   # checkpoint: the 41 ported tests + 10 new
python spec_longhaul_checkpoint.py   # the acceptance spec: 7 rows
```

- **The spec** comes from the durable-checkpoint review. It exits 0 only if two
  things hold at once:
  - all 7 rows pass on `longhaul_checkpoint`;
  - the frozen pre-fix module (`fixtures/`) still fails rows 1-5 and 7 and passes row 6.

  That keeps the spec two-sided in CI. `--demonstrate-fixes` prints the original
  as-is / with-fix matrix.
- **Floors.** Each runner fails below its `MIN_TESTS` floor, so a broken discovery
  cannot report 0/0 as green.
- **Mutation check.** At landing, 10 hand-made mutants each turned a suite red:
  - the ceiling clip;
  - the global pause line;
  - the high-water max;
  - cancelling unpaused calls;
  - ignoring `max_respawn`;
  - resume mtimes;
  - the unbounded signal lock;
  - retention counting torn generations;
  - a `get()` error read as a failed call on one signal;
  - a failed measurement read as zero spend in `watch`.
- **Python versions.** Everything passes on Python 3.11 (the CI version) and 3.14.

## Limitations

- **One writer per durable path, one watch per profile.** Two `watch` processes on
  one profile could each respawn the same failed call.
- **`watch` measures the whole fleet** when the source is measured. The global line
  needs every funded account's spend, so each tick may run `modal billing
  summary` once per account. The cache TTL bounds that.
- **Measured caps are per calendar month**, because Modal's billing summary is.
  A cap resets at the month boundary, and `status` says so.
- **Real preemption is not reproduced in tests.** `signal.raise_signal` is not a
  container kill. The spec's "does not cover" section lists what remains
  untested: volume semantics, fsync ordering, and the stat-before-copy race.