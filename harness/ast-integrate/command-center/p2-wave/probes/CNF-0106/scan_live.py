"""Static scan of live tools/command-center for network APIs. Not a comment check."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

NETWORK_RE = re.compile(
    r"\b(urllib\.request|urlopen|requests\.|httpx\.|http\.client|"
    r"socket\.create_connection|aiohttp)\b"
)


def scan(repo: Path) -> dict[str, Any]:
    root = repo / "tools" / "command-center"
    hits: list[dict[str, Any]] = []
    py_files = 0
    if root.is_dir():
        for path in sorted(root.rglob("*.py")):
            py_files += 1
            text = path.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                if NETWORK_RE.search(line) and "NETWORK_RE" not in line:
                    hits.append(
                        {
                            "path": path.relative_to(repo).as_posix(),
                            "line": i,
                            "snippet": line.strip()[:160],
                        }
                    )
    pytest_available = True
    try:
        import pytest  # noqa: F401
    except ImportError:
        pytest_available = False
    return {
        "root": "tools/command-center",
        "py_files_scanned": py_files,
        "pytest_available": pytest_available,
        "network_api_hits_in_command_center_tools": hits,
        "note": (
            "pytest is not installed on this runner; live command-center tests "
            "were not executed as pytest. Static scan + this unit's executable "
            "install/test fixture are the measurement."
        ),
    }
