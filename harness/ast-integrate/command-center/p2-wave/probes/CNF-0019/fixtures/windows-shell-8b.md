# windows-shell.md section 8b (documentary mention)

On Windows, `git archive` returns CRLF worktree bytes. Do not use that
recipe to verify the LF blob. Use `git cat-file -p <rev>:<path>`.
