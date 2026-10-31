"""Declared environment allowlist vs observed child keys. TST-0210."""
from __future__ import annotations

import re
from pathlib import Path


def load_declared_allowlist(path: Path | str) -> set[str]:
    text = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
    keys = set(re.findall(r'["\']([A-Z][A-Z0-9_]{1,})["\']', text))
    keys.update({"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR"})
    return keys


def adapter_run_calls_pass_env(src: str) -> dict[str, bool]:
    return {
        "perform_found": "_perform" in src,
        "bash_env": "env=" in src and "Bash" in src,
        "powershell_env": "env=" in src and "PowerShell" in src,
    }


def extras_vs_allowlist(observed: set[str] | list[str], declared: set[str]) -> list[str]:
    return sorted(set(observed) - set(declared))


def child_env() -> dict[str, str]:
    import os

    allow = {"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR"}
    return {k: v for k, v in os.environ.items() if k in allow}
