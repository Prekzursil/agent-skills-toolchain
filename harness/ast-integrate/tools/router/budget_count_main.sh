#!/usr/bin/env bash
# IMP-0392: the injection-budget running counter lives in the MAIN shell.
#
# This file is meant to be SOURCED, never executed:
#
#     source tools/router/budget_count_main.sh
#     BUDGET_COUNTER=0
#     budget_add 7
#     budget_add 5
#     printf '%s\n' "$BUDGET_COUNTER"   # -> 12
#
# budget_add mutates BUDGET_COUNTER in the caller's shell. Running the
# increment inside command substitution, e.g. _=$(budget_add 7), forks a
# subshell and the increment is lost when it exits — that is exactly the
# failure mode this counter exists to avoid (probe2 demonstrates the lost
# subshell counter next to this main-shell one).

BUDGET_COUNTER="${BUDGET_COUNTER:-0}"

budget_add() {
    local amount="${1:?budget_add requires a token amount}"
    BUDGET_COUNTER=$((BUDGET_COUNTER + amount))
}

budget_reset() {
    BUDGET_COUNTER=0
}
