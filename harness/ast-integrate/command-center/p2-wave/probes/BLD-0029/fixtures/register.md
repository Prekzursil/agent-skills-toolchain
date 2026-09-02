# Fixture unknowns register (not the live command-center/UNKNOWNS-REGISTER.md)

## U-VACUOUS
unknown: planted unknown whose experiment is only "investigate further"
source: fixtures/register.md
experiment: investigate further
impact: If this stays open, customers may receive a broken release because the failing test was never re-run.

## U-JARGON
unknown: planted unknown whose impact is only agent jargon
source: fixtures/register.md
experiment:
command: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/BLD-0029/fixtures/settle_demo.py
input: command-center/p2-wave/probes/BLD-0029/fixtures/settle_input.txt
observation: stdout contains SETTLED:yes and the process exit code is 0
impact: detector-controlled both-states fingerprint remains G-1 predicate:absent on the worktree

## U-WELL-FORMED
unknown: planted well-formed unknown that must pass both halves
source: fixtures/register.md
experiment:
command: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/BLD-0029/fixtures/settle_demo.py
input: command-center/p2-wave/probes/BLD-0029/fixtures/settle_input.txt
observation: stdout contains SETTLED:yes and the process exit code is 0
impact: If this unknown stays open, a release can ship while coverage is unmeasured, so the owner cannot tell whether tests actually protect the product.
