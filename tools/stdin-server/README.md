# tools/stdin-server

A stdlib-only, zero-dependency MCP server that gives an agent a **persistent
interactive stdin channel** to a child process — the one thing Claude Code's
Bash tool cannot do.

| File | What it is | Gated |
|---|---|---|
| `stdin_server.py` | `ManagedProcess` + session registry + a hand-rolled newline-delimited JSON-RPC 2.0 loop exposing three verbs. Stdlib only. | 100% line+branch |
| `test_stdin_server.py` | Drives **real** child processes (a `python -i -u` REPL, `python -c` one-shots) so the gate measures behaviour, not mocks. | — |

## The gap it closes

Claude Code's Bash tool runs `-NonInteractive` with stdin wired to the null
device. So it can *launch* a REPL, a debugger (`pdb`), a database shell, an SSH
session, or any prompt-driven CLI — but it cannot **type into** one after it
starts. This server owns the child process and relays stdin/stdout for it, the
non-duplicate surface of Desktop Commander's
`start_process` / `interact_with_process` / `read_process_output`.

## The three verbs

```
start_process(command: list[str], cwd?: str)
    -> {session_id, pid}

interact_with_process(session_id: str, input: str, wait_ms=200)
    -> {output, alive, exit_code}

read_process_output(session_id: str, max_chars=8192, timeout_ms=1000)
    -> {output, more, truncated, alive, exit_code}
```

* **`start_process`** spawns a persistent child (`stdin=PIPE`, merged
  `stdout+stderr=PIPE`) and registers it under a `session_id`. A daemon thread
  immediately begins draining its output.
* **`interact_with_process`** writes `input` to the child's stdin, waits `wait_ms`
  for it to react, then returns whatever the child produced plus its liveness
  (`alive` / `exit_code`).
* **`read_process_output`** pulls up to `max_chars` of buffered output, blocking
  up to `timeout_ms` for the first byte. `more` means output still remains to be
  read; `truncated` means the ring buffer **dropped older output** (the child
  outran the reader past `BUFFER_CAP`).

## Driving a REPL — the canonical flow

```
start_process(["python", "-i", "-u"])          -> {session_id: "proc-1", pid: 4242}
interact_with_process("proc-1", "print(2+2)\n") -> {output: ">>> 4\n>>> ", alive: true, exit_code: null}
interact_with_process("proc-1", "exit()\n")     -> {output: "", alive: false, exit_code: 0}
```

## Design decisions

* **Opt-in mount, NOT always-on.** This box has a measured commit-exhaustion
  freeze caused by per-session stdio-MCP duplication. Keeping the server
  zero-dependency and mounting it only for the session that needs an interactive
  channel avoids adding to that load.
* **Bounded memory (`BUFFER_CAP = 256 KiB`, drop-oldest ring).** The reader
  thread appends into a `deque` capped in characters; past the cap the oldest
  characters are discarded and the drop is remembered, so a runaway child cannot
  grow memory without bound. A discarded-data event surfaces as `truncated`.
* **Session cap (`MAX_SESSIONS = 16`)** and an `atexit` hook that terminates every
  child, so the server never leaks processes.
* **Why hand-rolled JSON-RPC and not an SDK.** The zero-dependency requirement is
  the point (see the commit-exhaustion note above); the MCP subset needed here —
  `initialize`, `tools/list`, `tools/call` — is ~40 lines of stdlib.

## Windows caveat (stated, not hidden)

`pty` is Unix-only, so children are driven over ordinary **pipes**, not a
pseudo-terminal. Two consequences:

1. A program that gates its prompt on `isatty()` may **suppress that prompt** when
   its stdout is a pipe. For the CPython REPL, launch it with `-i -u` (force
   interactive, unbuffer stdout) — as every test here does.
2. A child that writes without flushing will not emit until it flushes or exits
   (pipe stdio is fully buffered). Prefer `-u` / `flush=True` for line-by-line
   interaction.

A **ConPTY / pywinpty** front-end that presents a real terminal to the child is a
documented dependency follow-on, deliberately outside this stdlib-only scope.

## Local test / coverage command (mirrors the CI lane)

```bash
cd tools/stdin-server
pip install pytest pytest-cov
pytest --cov=stdin_server --cov-branch --cov-report=term-missing --cov-fail-under=100
```
