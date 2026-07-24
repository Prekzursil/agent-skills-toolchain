---
name: stdin-server
description: Interactive-stdin MCP server (stdlib-only, zero-dependency) giving an agent a persistent write-to-stdin plus read-incremental-stdout channel to a child process — start_process / interact_with_process / read_process_output. Use when you must drive a LIVE prompt-driven process after it launches: a REPL, a debugger (pdb), a database or language shell, an SSH session, or any CLI that keeps reading stdin — the thing Claude Code's -NonInteractive Bash (stdin on the null device) cannot do. NOT for one-shot commands (use Bash) and NOT always-on (opt-in mount only, because this box has a measured commit-exhaustion freeze from per-session stdio-MCP duplication).
license: MIT
---
# stdin-server — interactive stdin for a child process

Source of truth: `tools/stdin-server/stdin_server.py` (stdlib-only, 100% line+branch
gated). Full design + caveats: `tools/stdin-server/README.md`.

## The gap it closes

Claude Code's Bash tool runs `-NonInteractive` with stdin wired to the null device,
so it can *launch* a REPL / debugger / db-shell but cannot **type into** one after
it starts. This server owns the child process and relays its stdin/stdout — the
non-duplicate surface of Desktop Commander.

## Mount (opt-in, NOT always-on)

Zero third-party deps, so there is no install step. Register an MCP server whose
command is `python tools/stdin-server/stdin_server.py`; it speaks newline-delimited
JSON-RPC 2.0 on its own stdio. Mount it only for the session that needs an
interactive channel — the box has a measured commit-exhaustion freeze caused by
per-session stdio-MCP duplication, so do not add it to the always-on fleet.

## The three verbs

- `start_process(command: list[str], cwd?)` -> `{session_id, pid}`
- `interact_with_process(session_id, input, wait_ms=200)` -> `{output, alive, exit_code}`
- `read_process_output(session_id, max_chars=8192, timeout_ms=1000)` -> `{output, more, truncated, alive, exit_code}`

`more` means buffered output still remains; `truncated` means the 256 KiB
drop-oldest ring discarded older output before you read it.

## Canonical flow — drive a REPL

```
start_process(["python", "-i", "-u"])            -> {session_id: "proc-1", pid: ...}
interact_with_process("proc-1", "print(2+2)\n")  -> {output: ">>> 4\n>>> ", alive: true}
interact_with_process("proc-1", "exit()\n")      -> {alive: false, exit_code: 0}
```

## Windows caveat

`pty` is Unix-only, so children run over ordinary pipes: an `isatty()`-gated prompt
may be suppressed (launch the CPython REPL with `-i -u`), and a child that writes
without flushing will not emit until it flushes or exits. A ConPTY / pywinpty
front-end is a documented follow-on, outside this stdlib-only scope.
