# modal-budget-ledger

Per-account budget tracking over cloud accounts **you fund**. You tell it how much
of your own money each account may spend; it tracks what you have spent and
answers "which account should I use next, and have I got room left?"

Written for Modal profiles, but there is nothing Modal-specific in it — the
accounts are just names, so it works for any provider where you hold more than
one funded account.

Stdlib only, no dependencies. Python 3.11+.

## What it deliberately does not do

Each of these is a design decision, not an unfinished edge:

| Non-feature | Why |
|---|---|
| **No network calls** | Caps come only from your config. The module cannot read a provider-side limit, so nothing in it can trigger off one. A budget here is a number you chose. |
| **No switching** | `select` prints a profile name and exits. It never sets `MODAL_PROFILE`, spawns anything, or writes. Acting on the answer is your explicit step. |
| **No account discovery** | An account is eligible only if you enrolled it by hand with a cap and `funded: true`. It never enumerates the profiles on the machine, so it cannot assemble a fleet for you. |
| **No credentials** | It knows profile *names*. It never reads, stores or prints a token, and has no code path that could. |

`test_budget_ledger.py::test_imports_match_the_allowlist` asserts the first one
against the source rather than asking you to trust it: it walks the module's AST
and fails if any import is outside an explicit allowlist. The allowlist is the
reviewable surface — adding to it is a visible, deliberate act, and a second test
keeps `socket`, `urllib`, `http`, `requests`, `subprocess`, `importlib` and
`modal` out of it. An earlier version of this test grepped for four literal
strings and would have waved through `from urllib.request import urlopen`.

## Config

A JSON file you author. Its path is always a parameter — `--config PATH`, or the
`MODAL_BUDGET_CONFIG` environment variable. There is no implicit default, so the
tool can never read a config you did not name.

```json
{
  "global_ceiling_usd": 500.0,
  "min_headroom_usd": 5.0,
  "accounts": [
    {"profile": "my-paid-a", "cap_usd": 200.0, "funded": true, "note": "primary"},
    {"profile": "my-paid-b", "cap_usd": 300.0, "funded": true}
  ]
}
```

- `accounts[].cap_usd` — how much this account may spend in total. Your number.
- `accounts[].funded` — must be set explicitly to `true` or `false`; there is no
  default. Mark it `true` only if you fund the account and the cap is your own
  money. A `false` account is refused by name with a reason rather than silently
  skipped, so an account you deliberately parked stays visible in `status`.
- `global_ceiling_usd` *(optional)* — a hard total across every account. Omit for
  no total limit.
- `min_headroom_usd` *(optional, default 0)* — don't hand out an account with
  less than this spendable, so a job doesn't start on pennies. `== min` is still
  eligible; a cent under is not.

### How the ceiling and the caps interact

Each account reports two numbers, and the difference matters:

- `remaining_usd` — this account's own headroom, `cap_usd` minus its spend.
- `effective_remaining_usd` — what is **actually spendable** on it right now:
  the lesser of its own headroom and the room left under the global ceiling.

Eligibility, the `min_headroom_usd` test and the `most-remaining` ranking all use
the **effective** figure. That matters more than it sounds: with a $60 ceiling,
$58 already spent, and an account whose own cap leaves $8, only $2 is really
available. Reporting $8 there would let a launcher overshoot the "hard total" by
$6. Refusals name which limit bound — `bound by global ceiling` or
`bound by account cap` — because raising a ceiling and raising a cap are
different fixes.

This was a real bug, found in review and fixed: the ceiling used to be enforced
only once it had been *reached*, so the case above handed out the account.
`test_ceiling_clips_remaining_room_not_just_the_end` is the regression test, with
those exact numbers.

The spend ledger is a separate append-only `spend.jsonl`, written by the tool and
living beside the config unless you pass `--ledger PATH` or set
`MODAL_BUDGET_LEDGER`. Config is yours; the ledger is the tool's.

## Use

```bash
# What have I got?
python budget_ledger.py --config cfg.json status

# Which account should I use? (prints a bare profile name)
python budget_ledger.py --config cfg.json select

# Record what a finished job actually cost.
python budget_ledger.py --config cfg.json record \
    --account my-paid-a --usd 12.40 --job-id fep-a2d-01

# Show the effect without writing.
python budget_ledger.py --config cfg.json record \
    --account my-paid-a --usd 12.40 --dry-run
```

Because `select` prints a bare name on stdout, it composes:

```bash
PROFILE="$(python budget_ledger.py --config cfg.json select)" || exit 1
MODAL_PROFILE="$PROFILE" modal run my_job.py
python budget_ledger.py --config cfg.json record --account "$PROFILE" --usd "$COST"
```

### Selection strategies

- `--strategy order` *(default)* — walk the config order, take the first account
  with headroom. Spends one account down to its cap before moving to the next.
- `--strategy most-remaining` — take the largest *effective* balance, spreading
  spend across accounts. Ties break on profile name, so the pick is deterministic.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Fine |
| `2` | Bad invocation or bad config — a human needs to look |
| `3` | Well-formed question, and the answer is no: nothing has headroom, or the global ceiling is spent |

`3` is distinct from `2` on purpose, so a launcher can branch on "out of budget"
without treating it as a crash.

## Limitations worth knowing before you rely on it

- **Spend is recorded by the caller, after the fact.** Nothing here observes your
  actual bill, so a job that crashes or is abandoned before `record` runs leaves
  its spend untracked, and the ledger will over-estimate your remaining budget.
  Reconcile against the provider's own billing figures periodically. Treat this
  as a planning aid, not an accounting record.
- **Advisory, not a lock.** `select` reads, then you act. Two launchers running
  concurrently can be handed the same account and together overshoot its cap.
  Fine for one operator; if you need concurrent launchers, add a lock around
  select-and-record.
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
python test_budget_ledger.py     # self-contained, or run under pytest
```

33 tests covering config validation, ledger arithmetic, the selection strategies,
the headroom boundary, the ceiling clipping per-account headroom (and the
regression above), the unfunded and unenrolled refusals, dry-run, the CLI exit
codes, and the import allowlist. All run in a temp directory and touch no real
config, no real ledger and no network.
