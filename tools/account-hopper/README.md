# account-hopper — retired 2026-10-30

This tool was folded into [`tools/longhaul`](../longhaul/README.md), together with:
- the unmerged modal-budget-ledger measured layer;
- the closed durable-checkpoint PR (#398);
- the fractal-compute steward's guard and watchdog.

**What lives on in longhaul:**
- the config format (an account-hopper config loads unchanged);
- the append-only `spend.jsonl` ledger;
- `status` and `record`;
- the ceiling fix (`effective_remaining_usd` is the lesser of the account's room and the ceiling's room);
- the `MODAL_TOKEN_*` stripping;
- the `MIN_TESTS` floor.

**What was dropped on purpose:**
- `select`, `hop`, `hopper_launch.ps1` and `-MaxHops`.

longhaul makes no automatic hop on drain and does no free-credit rotation. The
next account is always the user's explicit choice: `longhaul.py check --profile P`
answers for the account you picked, and gives exit 3 with a reason when it is at
its line.

Migration steps: [`tools/longhaul/MIGRATION.md`](../longhaul/MIGRATION.md) §1.
The last version of this tool is on `main` at commit `7a1393ca` (PRs #396 and #397).
