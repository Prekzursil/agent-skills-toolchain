# Fixture ROLLBACK-MANIFEST (CNF-0041)

This file is the hashing-walker scope for the disposable confirmation
fixture. It is not a substitute for the program-wide
`command-center/ROLLBACK-MANIFEST.md`, which is absent on this worktree.

The walker follows the listed trees exactly. Paths are relative to the
fixture root created by `scenario.py`.

## Affected trees

- `affected/app`
- `affected/config`

## Reserved device name

`affected/app/NUL` is a reserved Windows device name. The walker must
open it through the extended-length prefix (`\\?\` on Windows; the same
guard on POSIX) or a naive walk raises `ValueError: path is on mount
'\\.\NUL'` and, if swallowed, reports zero files.

## Rollback

Complete rollback restores snapshot bytes and deletes extras.
Incomplete rollback (detector control) restores snapshot bytes and
leaves a planted extra file in place so the pre vs post-rollback
comparison must list it.
