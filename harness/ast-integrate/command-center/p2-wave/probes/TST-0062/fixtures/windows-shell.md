# windows-shell.md (regression seed for TST-0062 / catalog input #2)

## 2. PowerShell caret and git peel refs

Measured: `git rev-parse v1.4.1^{commit}` is not one argv under PowerShell.
`{commit}` is a scriptblock; git sees `v1.4.1^` and fails (or, under cmd.exe,
`^` escapes `{` and git sees `v1.4.1{commit}`).

Sanctioned forms, proven equivalent on a live annotated tag:

- `git rev-list -n 1 v1.4.1`
- `git rev-parse 'v1.4.1^{commit}'`
