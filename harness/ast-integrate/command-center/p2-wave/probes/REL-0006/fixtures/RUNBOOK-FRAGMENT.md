# Runbook fragment — rollback MTTR (REL-0006 rehearsal)

Catalog input `command-center/RUNBOOK.md` is absent on this worktree.
This fragment is the figure the drill compares against. It is not an
estimated duration invented after the run.

The published rollback MTTR SLO is wall time from the rollback
**decision** (retrievability gate begins) to **restored N-1 behaviour**
(N-1 acceptance probe pass). Clock named in the receipt.

```
MTTR_SLO_SECONDS=30
```

A measured duration that exceeds 30 seconds fails the drill.
A receipt that reports an estimated duration without a named clock
fails the evidence requirement.
