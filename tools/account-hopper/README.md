---
title: README
type: note
permalink: dqverify-repo-20261013/tools/account-hopper/readme
---

# account-hopper

Per-account budget ledger **plus** an account hopper, over cloud accounts **you
fund**. You tell it how much of your own money each account may spend; it
tracks what you have spent, answers "which account should I use next, and have
I got room left?", and its `hop` step closes out the account you are leaving
and names the next one in the same breath.

Built for the Modal-profile rotation pattern — drain one funded account, relay
the job's checkpointed state to the next, resume — but there is nothing
Modal-specific in it: the accounts are just names, so it works for any provider
where you hold more than one funded account.

Stdlib only, no dependencies. Python 3.11+.

## What it deliberately does not do

Each of these is a design decision, not an unfinished edge:

| Non-feature | Why |
|---|---|
| **No network calls** | Caps come only from your config. The module cannot read a provider-side limit, so nothing in it can trigger off one. A budget here is a number you chose. |
| **No switching** | `select` and `hop` print a profile name and exit. Neither sets `MODAL_PROFILE`, spawns anything, or touches an account (`hop` writes only its own ledger line). Acting on the answer is your explicit step. |
| **No account discovery** | An account is eligible only if you enrolled it by hand with a cap and `funded: true`. It never enumerates the profiles on the machine, so it cannot assemble a fleet for you. |
| **No credentials** | It knows profile *names*. It never reads, stores or prints a token, and has no code path that could. |

`test_account_hopper.py::test_imports_match_the_allowlist` asserts the first
one against the source rather than asking you to trust it: it walks the
module's AST and fails if any import is outside an explicit allowlist. The
allowlist is the reviewable surface — adding to it is a visible, deliberate
act, and a second test keeps `socket`, `urllib`, `http`, `requests`,
`subprocess`, `importlib` and `modal` out of it. An earlier version of this
test grepped for four literal strings and would have waved through
`from urllib.request import urlopen`.

## The rotation loop this exists for

The workflow behind the tool: several funded Modal accounts, each with roughly
a month of free credit (about $30, or ~7.5 H100-hours), and long GPU jobs that
outlive any one account's budget. The pattern: drain account A to its cap,
relay the job's checkpointed state to account B, resume there, and keep hopping
until the job is done or the rotation is dry.

`hop` is one rotation step. The loop around it lives in your launcher:

```bash
# One rotation step: record what the current account spent, get the next one.
# Exit 3 means the rotation is out of budget — stop, or enrol more accounts.
PROFILE="$(python account_hopper.py --config cfg.json hop \
    --account "$CURRENT" --usd "$SPENT" --job-id "$JOB")" || exit $?

# Switching profiles is YOUR explicit step (the tool never does it). On Modal,
# unset any MODAL_TOKEN_* env vars first: they override ~/.modal.toml and would
# silently pin every call to one account no matter what MODAL_PROFILE says.
unset MODAL_TOKEN_ID MODAL_TOKEN_SECRET
export MODAL_PROFILE="$PROFILE"

modal run my_job.py ...   # checkpoint the job to a volume as you go

# When the hopper hands you a new account, relay the job state yourself.
# Modal volumes are per-workspace, so state does not follow the profile switch:
#   modal volume get <vol> /path ./relay    (on the drained account)
#   modal volume put <vol> ./relay /path    (on the fresh account)
# The hopper deliberately knows nothing of job state; the budget is its whole view.
```

A config shaped like the real thing (names only — the tool never touches
tokens):

```json
{
  "global_ceiling_usd": 240.0,
  "min_headroom_usd": 2.0,
  "accounts": [
    {"profile": "prekzursil1993", "cap_usd": 30.0, "funded": true, "note": "free credit"},
    {"profile": "florineldanciu4", "cap_usd": 30.0, "funded": true, "note": "free credit"},
    {"profile": "darias-grama", "cap_usd": 30.0, "funded": true, "note": "free credit"},
    {"profile": "andreivisalon2002", "cap_usd": 30.0, "funded": true, "note": "free credit"}
  ]
}
```

Ground truth for the rotation this was designed around — the checkpoint/resume
design, the per-workspace volume relay, and the account drain that forced the
first hop — is the phenibut manuscript compute log:
`D:\Research\projects\phenibut\compute\modal_ckpt_2026-09-15\MODAL_RUNS.md`.

### The automatic loop: `hopper_launch.ps1`

The launcher that acts on the answers, so you do not have to. It wraps any
resumable job: `hop` names the account, the script unsets `MODAL_TOKEN_*` (the
override gotcha above), sets `MODAL_PROFILE`, runs your job, and on a non-zero
exit treats the account as drained — records the run, hops to the next account,
and loops. Job exit 0 stops the loop (done); the ledger's exit 3 stops it
(rotation dry); `-MaxHops` caps the loop for a human look.

```powershell
.\hopper_launch.ps1 -Config cfg.json -CostEstimateUsd 8 -JobId gpn-run1 `
  -Job 'modal run D:\Research\projects\phenibut\compute\modal_scripts\atm_modal_resumable.py --cmd gpn'
```

`-CostEstimateUsd` is what gets recorded per drained run; without it the loop
still rotates but warns that the spend is invisible to the ledger. The job
command is yours verbatim — the script never talks to Modal itself, and the
ledger stays network-free. Relay the job's checkpointed state across accounts
however the job does it (for ATM/FEP: the volume get/put relay) — the loop
calls your job fresh on each new account and the job's own resume logic picks
up its checkpoints.

## Config

A JSON file you author. Its path is always a parameter — `--config PATH`, or
the `ACCOUNT_HOPPER_CONFIG` environment variable. There is no implicit default,
so the tool can never read a config you did not name.

- `accounts[].cap_usd` — how much this account may spend in total. Your number.
- `accounts[].funded` — must be set explicitly to `true` or `false`; there is
  no default. Mark it `true` only if you fund the account and the cap is your
  own money. A `false` account is refused by name with a reason rather than
  silently skipped, so an account you deliberately parked stays visible in
  `status`.
- `global_ceiling_usd` *(optional)* — a hard total across every account. Omit
  for no total limit.
- `min_headroom_usd` *(optional, default 0)* — don't hand out an account with
  less than this spendable, so a job doesn't start on pennies. `== min` is
  still eligible; a cent under is not.

### How the ceiling and the caps interact

Each account reports two numbers, and the difference matters:

- `remaining_usd` — this account's own headroom, `cap_usd` minus its spend.
- `effective_remaining_usd` — what is **actually spendable** on it right now:
  the lesser of its own headroom and the room left under the global ceiling.

Eligibility, the `min_headroom_usd` test and the `most-remaining` ranking all
use the **effective** figure. That matters more than it sounds: with a $60
ceiling, $58 already spent, and an account whose own cap leaves $8, only $2 is
really available. Reporting $8 there would let a launcher overshoot the "hard
total" by $6. Refusals name which limit bound — `bound by global ceiling` or
`bound by account cap` — because raising a ceiling and raising a cap are
different fixes.

This was a real bug, found in review and fixed: the ceiling used to be enforced
only once it had been *reached*, so the case above handed out the account.
`test_ceiling_clips_remaining_room_not_just_the_end` is the regression test,
with those exact numbers.

The spend ledger is a separate append-only `spend.jsonl`, written by the tool
and living beside the config unless you pass `--ledger PATH` or set
`ACCOUNT_HOPPER_LEDGER`. Config is yours; the ledger is the tool's.

## Use

```bash
# What have I got?
python account_hopper.py --config cfg.json status

# Which account should I use? (prints a bare profile name)
python account_hopper.py --config cfg.json select

# The rotation step: account $CURRENT is done, it spent $SPENT — what next?
python account_hopper.py --config cfg.json hop \
    --account "$CURRENT" --usd "$SPENT" --job-id "$JOB"

# Record a cost without hopping (mid-account top-up, a correction run).
python account_hopper.py --config cfg.json record \
    --account my-paid-a --usd 12.40 --job-id fep-a2d-01

# Preview any of the above without writing.
python account_hopper.py --config cfg.json hop \
    --account "$CURRENT" --usd "$SPENT" --dry-run
```

Because `select` and `hop` print a bare name on stdout, they compose. The
plain two-call shape:

```bash
PROFILE="$(python account_hopper.py --config cfg.json select)" || exit 1
MODAL_PROFILE="$PROFILE" modal run my_job.py
python account_hopper.py --config cfg.json record --account "$PROFILE" --usd "$COST"
```

`hop --dry-run` previews the hop with the pending spend **counted**, so what it
prints is what a real hop would pick — while writing nothing.

### Selection strategies

`select` and `hop` both take:

- `--strategy order` *(default)* — walk the config order, take the first
  account with headroom. Spends one account down to its cap before moving to
  the next: the drain-then-hop shape.
- `--strategy most-remaining` — take the largest *effective* balance, spreading
  spend across accounts. Ties break on profile name, so the pick is
  deterministic.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Fine |
| `2` | Bad invocation or bad config — a human needs to look |
| `3` | Well-formed question, and the answer is no: nothing has headroom, or the global ceiling is spent. For `hop`, this is "the rotation is dry" — the launcher stops here. |

`3` is distinct from `2` on purpose, so a launcher can branch on "out of
budget" without treating it as a crash.

## Limitations worth knowing before you rely on it

- **Spend is recorded by the caller, after the fact.** Nothing here observes
  your actual bill, so a job that crashes or is abandoned before `record`/`hop`
  runs leaves its spend untracked, and the ledger will over-estimate your
  remaining budget. Reconcile against the provider's own billing figures
  periodically. Treat this as a planning aid, not an accounting record.
- **Advisory, not a lock.** `select`/`hop` read, then you act. Two launchers
  running concurrently can be handed the same account and together overshoot
  its cap. Fine for one operator; if you need concurrent launchers, add a lock
  around hop-and-record.
- **No corrections in v1.** Negative amounts are refused, because they would
  manufacture headroom. Refunds and misrecorded amounts currently mean editing
  `spend.jsonl` by hand — it is one JSON object per line, append-only, so a bad
  line is easy to find and fix.
- **Money is float, rounded to cents at every boundary.** At this scale the
  representation error is ~1e-13, irrelevant against a dollar-denominated
  threshold. If you ever need cent-exact billing arithmetic, move to
  `decimal.Decimal` rather than adding more rounding.
- **A corrupt ledger line is fatal, by choice.** Skipping it would under-report
  spend, which is the one failure this tool exists to prevent.

## Tests

```bash
python test_account_hopper.py    # self-contained, or run under pytest
```

61 tests covering config validation, ledger arithmetic, the selection
strategies, the headroom boundary, the ceiling clipping per-account headroom
(and the regression above), the unfunded and unenrolled refusals, the hop
rotation step and its dry-run preview, the CLI exit codes, the env-var config
and ledger paths, and the import allowlist. Measured at **100% line and branch
coverage** of `account_hopper.py`. The runner fails below its `MIN_TESTS`
floor, so a discovery break reports FAIL rather than a green 0/0. All tests run
in a temp directory and touch no real config, no real ledger and no network.