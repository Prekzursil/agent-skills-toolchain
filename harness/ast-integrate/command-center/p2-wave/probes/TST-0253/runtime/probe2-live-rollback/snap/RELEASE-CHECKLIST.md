# Release checklist

Byte-sensitive format, lint, and hash gates judge the **stored blob**,
not the working tree and not `git archive` output.

Obtain those bytes with:

```
git cat-file -p HEAD:path/to/file
```

Do not verify against `git archive`. On this platform `git archive`
returns CRLF worktree form; `git cat-file -p` returns the LF blob CI
judges. `rules/common/windows-shell.md` section 8b documents the trap
and is a mention, not a prescription.

CNF-0019 measured the three routes on a control with `eol=crlf`:
archive and worktree emit CRLF; cat-file emits LF; all three match
after LF normalisation.
