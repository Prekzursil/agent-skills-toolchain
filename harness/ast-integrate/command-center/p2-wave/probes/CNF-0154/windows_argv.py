"""Windows CreateProcessW command-line length and quoting.

The measured failure is os error 206 on an inline prompt of 34,472 chars
because CreateProcessW caps the command line at 32,767 characters including
the terminating NUL. Linux ARG_MAX is larger; the Codex MCP rail still
enforces the Windows cap so prompt-by-file is a real transport, not cargo cult.
"""
from __future__ import annotations

WIN_CMDLINE_MAX = 32767  # including terminating NUL
WIN_CMDLINE_USABLE = WIN_CMDLINE_MAX - 1
INLINE_PROMPT_MEASURED = 34472
OS_ERROR_206 = 206


def win_quote(arg: str) -> str:
    if arg == "":
        return '""'
    if not any(ch in arg for ch in ' \t"'):
        return arg
    out: list[str] = ['"']
    bs = 0
    for ch in arg:
        if ch == "\\":
            bs += 1
            continue
        if ch == '"':
            out.append("\\" * (bs * 2 + 1))
            out.append('"')
            bs = 0
            continue
        out.append("\\" * bs)
        out.append(ch)
        bs = 0
    out.append("\\" * (bs * 2))
    out.append('"')
    return "".join(out)


def win_command_line(argv: list[str]) -> str:
    return " ".join(win_quote(a) for a in argv)


def exceeds_win_arg_limit(cmdline: str) -> bool:
    return (len(cmdline) + 1) > WIN_CMDLINE_MAX
