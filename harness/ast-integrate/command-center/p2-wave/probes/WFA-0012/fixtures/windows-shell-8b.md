# windows-shell.md section 8b (catalog input; live rules/common/windows-shell.md is ABSENT)

On Windows, `core.autocrlf=true` materialises CRLF in the working tree.
`git archive` returns those CRLF worktree bytes. Do not hash `git archive`
output and do not hash the working tree when a gate must match CI.

Use `git cat-file -p <rev>:<path>` (or `git show <rev>:<path>`) to read
the committed LF blob, or LF-normalise before hashing. A genuine one-byte
content change must still fail the hash gate; newline conversion alone
must not.
