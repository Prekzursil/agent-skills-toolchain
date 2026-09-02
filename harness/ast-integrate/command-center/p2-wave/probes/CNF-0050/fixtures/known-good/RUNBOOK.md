# RUNBOOK

## Install

Not in scope for this fixture.

## Rollback

The rollback procedure is the recovery section of ROLLBACK-MANIFEST.md. Execute it top to bottom with zero improvisation.

1. Re-run the payload presence check before any restore.

```sh
test -f payload.bin
```

$ test -f payload.bin
