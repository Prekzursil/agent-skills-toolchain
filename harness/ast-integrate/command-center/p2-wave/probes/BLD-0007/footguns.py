"""Five ledger-proven Windows footguns reconstructed from catalog citations.

`rules/common/windows-shell.md` is absent on this worktree. Names and section
numbers are taken from WORK-UNIT-CATALOG.json inputs (ADV-0118 lists sections
1, 2, 8c, 9, 10 as the five). Confidence is CATALOG-RECONSTRUCTED, not a live
read of the rule file.
"""
from __future__ import annotations

FOOTGUNS = [
    {
        "id": "WS-1",
        "section": "1",
        "name": "MSYS path rewriting of POSIX-looking arguments",
        "catalog_anchors": [
            "WORK-UNIT-CATALOG.json:9164 (windows-shell.md 1, 2, 8c, 9, 10)",
            "WORK-UNIT-CATALOG.json:41720 (windows-shell.md#1 and #11 global suppression inverts the problem)",
            "WORK-UNIT-CATALOG.json:32284 (MSYS rewriting POSIX-looking arguments)",
        ],
        "confidence": "CATALOG-RECONSTRUCTED",
        "probe_cells": ["windows__git-bash-msys"],
    },
    {
        "id": "WS-2",
        "section": "2",
        "name": "PowerShell ${n}: drive-qualified parse / Git Bash which misses .cmd shims",
        "catalog_anchors": [
            "WORK-UNIT-CATALOG.json:1371 (T0-7 PowerShell ${n}: footgun)",
            "WORK-UNIT-CATALOG.json:32284 ('which' in Git Bash missing .cmd shims that Get-Command resolves)",
            "WORK-UNIT-CATALOG.json:9164 (section 2)",
        ],
        "confidence": "CATALOG-RECONSTRUCTED",
        "probe_cells": ["windows__powershell-7", "windows__git-bash-msys"],
    },
    {
        "id": "WS-8c",
        "section": "8c",
        "name": "CRLF script: Git Bash igncr PASS vs real WSL/Linux bash FAIL",
        "catalog_anchors": [
            "WORK-UNIT-CATALOG.json:21186 (Git-Bash cell probe must FAIL on CRLF under WSL bash and PASS under Git Bash)",
            "WORK-UNIT-CATALOG.json:41493 (windows-shell.md#3 agent-written CRLF breaks real bash)",
            "WORK-UNIT-CATALOG.json:30137 (CRLF-bearing script must FAIL under WSL bash while passing under Git Bash)",
        ],
        "confidence": "CATALOG-RECONSTRUCTED",
        "probe_cells": ["windows__git-bash-msys", "windows__wsl-bash"],
    },
    {
        "id": "WS-9",
        "section": "9",
        "name": "here-string payload scanned as a command",
        "catalog_anchors": [
            "WORK-UNIT-CATALOG.json:4807 (windows-shell.md 9 and 10 payload scanned as a command)",
            "WORK-UNIT-CATALOG.json:84804 (windows-shell.md:9 a here-string PAYLOAD is scanned as a command)",
        ],
        "confidence": "CATALOG-RECONSTRUCTED",
        "probe_cells": ["windows__powershell-7"],
    },
    {
        "id": "WS-10",
        "section": "10",
        "name": "apostrophe breaks the tool's own quoting",
        "catalog_anchors": [
            "WORK-UNIT-CATALOG.json:4807 (apostrophe breaks the tool's own quoting)",
            "WORK-UNIT-CATALOG.json:41674 (windows-shell.md#10)",
        ],
        "confidence": "CATALOG-RECONSTRUCTED",
        "probe_cells": ["windows__powershell-7", "windows__cmd.exe"],
    },
]


def as_receipt() -> list[dict]:
    return list(FOOTGUNS)
