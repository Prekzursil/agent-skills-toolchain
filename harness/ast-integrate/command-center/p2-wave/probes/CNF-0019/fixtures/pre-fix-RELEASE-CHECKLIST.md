# Release checklist (pre-fix, known-wrong)

Verify formatting against the LF blob (git archive):

```
git archive HEAD | tar -x -O -- rules/common/windows-shell.md
```

Hash and lint the extracted bytes before tagging a release.
