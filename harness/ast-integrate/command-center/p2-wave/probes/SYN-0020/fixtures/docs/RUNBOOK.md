# Fixture RUNBOOK

`python3 -c "print('SYN-0020-runbook-ok')"` exits 0 and prints SYN-0020-runbook-ok.

```bash
python3 -c "print('SYN-0020-runbook-ok')"
```

A documented command that does not exist must be attempted, not omitted:

```bash
syn0020-missing-binary --please-fail
```
