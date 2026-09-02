# windows-shell.md section 10 (fixture reconstruction)

Live path `rules/common/windows-shell.md` is absent on this worktree.
This fixture restates the catalog-cited rule that CNF-0023 names as an input.

## 10. Apostrophes break inline shell commands

An apostrophe inside a payload that is interpolated into a single-quoted
shell command terminates the tool's own quoting. The command the operator
typed is not the command that runs.

Required shape:

- Write the command body to a file.
- Invoke that file by path (argv array), never by inlining the body into
  `bash -c`, `python3 -c`, or a PowerShell `-Command` string.

Control: a payload containing `can't` must FAIL when inlined into a
single-quoted command and SUCCEED when the same bytes are invoked by path.

Catalog citations that independently name this section:

- CNF-0023 inputs: "rules/common/windows-shell.md section 10 (apostrophes break inline shell commands)"
- CNF-0023 tests_required: every generated script written to a file and invoked by path
- CNF-0105 tests_required: a script whose content contains an apostrophe must be invoked by PATH
- ADV-0031 inputs: "apostrophe breaks the tool's own quoting"
