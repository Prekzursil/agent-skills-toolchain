# Windows shell notes (fixture copy of the documentary mention)

## 8b. Blob bytes versus worktree bytes

On Windows, `git archive` returns CRLF worktree bytes, not the LF blob.
Do not verify formatting against `git archive`. Use `git cat-file -p <rev>:<path>`.

| Purpose | Wrong on this box | Right |
| --- | --- | --- |
| blob bytes | `git archive HEAD -- path` | `git cat-file -p HEAD:path` |

`git archive` is quoted here because it is the defect, not the instruction.
