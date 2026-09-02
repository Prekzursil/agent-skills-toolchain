# 8b Blob-versus-archive recipe (SYN-0018 fixture excerpt)

Live `rules/common/windows-shell.md` is not on this worktree. This fixture
records the recipe this unit is required to use:

- Read stored bytes with `git cat-file -p <rev>:<path>`.
- `git show <rev>:<path>` must agree byte-for-byte with cat-file.
- Do **not** classify from `git archive`. Archive applies export-time EOL
  conversion (`* text eol=crlf` in `.gitattributes`) and returns CRLF on the
  Windows box this program was measured against.

A run that used `git archive` is invalid by construction.
