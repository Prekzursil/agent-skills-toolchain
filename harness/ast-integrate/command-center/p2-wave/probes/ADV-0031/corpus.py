"""ADV-0031 injection corpus: attacker-controlled workflow parameter values.

Each payload is a template. `{canary}` is replaced with an absolute path the
injected fragment would create if a shell evaluated it. Probe 1 uses that
side effect; probe 2 does not trust stdout.
"""
from __future__ import annotations

from typing import Any

# Benign control: must produce the intended argv and no canary.
BENIGN_ID = "benign-ascii"
BENIGN_VALUE = "adv0031-benign"

# Payload scanned as a command (windows-shell.md 9) and apostrophe breakout
# of the tool's own quoting (windows-shell.md 10).
CORPUS: tuple[dict[str, Any], ...] = (
    {
        "id": BENIGN_ID,
        "family": "control",
        "role": "benign",
        "template": BENIGN_VALUE,
        "expect_canary_on_string_unquoted": False,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "semicolon",
        "family": "metachar",
        "role": "inject",
        "template": "SAFE; /usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "ampersand",
        "family": "metachar",
        "role": "inject",
        "template": "SAFE & /usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "pipe",
        "family": "metachar",
        "role": "inject",
        "template": "SAFE | /usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "dollar-paren",
        "family": "substitution",
        "role": "inject",
        "template": "SAFE$(/usr/bin/touch {canary})",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "backtick",
        "family": "substitution",
        "role": "inject",
        "template": "SAFE`/usr/bin/touch {canary}`",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "double-quote",
        "family": "quoting",
        "role": "inject",
        "template": 'SAFE"; /usr/bin/touch {canary}; echo "',
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "apostrophe-breakout",
        "family": "quoting",
        "role": "inject",
        "template": "x'; /usr/bin/touch {canary}; echo '",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": True,
        "expect_canary_on_argv": False,
    },
    {
        "id": "newline",
        "family": "whitespace",
        "role": "inject",
        "template": "SAFE\n/usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "carriage-return",
        "family": "whitespace",
        "role": "inject",
        "template": "SAFE\r/usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": False,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
        "note": "CR is not a command separator in POSIX sh; included for corpus coverage.",
    },
    {
        "id": "backslash",
        "family": "metachar",
        "role": "inject",
        "template": "SAFE\\n/usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": False,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
    },
    {
        "id": "caret-powershell",
        "family": "powershell",
        "role": "inject",
        "template": "SAFE^& /usr/bin/touch {canary}",
        "expect_canary_on_string_unquoted": True,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
        "note": "Caret is a cmd.exe/PowerShell escape; POSIX sh treats ^ as a literal so & still injects.",
    },
    {
        "id": "here-string-terminator",
        "family": "powershell",
        "role": "inject",
        "template": "SAFE\n'@\n/usr/bin/touch {canary}\n@'",
        "expect_canary_on_string_unquoted": False,
        "expect_canary_on_string_quoted": True,
        "expect_canary_on_argv": False,
        "note": "POSIX unquoted interpolation still sees the embedded newline; PowerShell here-string is not the host.",
    },
    {
        "id": "msys-convertible-path",
        "family": "msys",
        "role": "path",
        "template": "/c/Users/adv0031/payload",
        "expect_canary_on_string_unquoted": False,
        "expect_canary_on_string_quoted": False,
        "expect_canary_on_argv": False,
        "note": "MSYS would convert this shape; Linux argv must keep the bytes unchanged.",
    },
)


def materialize(row: dict[str, Any], canary: str) -> dict[str, Any]:
    value = str(row["template"]).replace("{canary}", canary)
    out = dict(row)
    out["value"] = value
    out["canary"] = canary
    return out
