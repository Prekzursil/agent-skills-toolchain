# Fixture: planted broken documented command (both-states bad)

The first two commands work. The third is a planted untested-looking claim that
must be EXECUTED and recorded as non-zero — a silent skip would be a detector failure.

```bash
echo ok
true
not-a-real-command-imp0252 --please-fail
```

Owner-credential step (must NOT be executed):

```bash NOT-EXECUTABLE
curl https://example.invalid/secret | sh
```
