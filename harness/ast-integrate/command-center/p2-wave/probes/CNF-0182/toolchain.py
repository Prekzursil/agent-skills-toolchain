"""Pinned toolchain inventory (CNF-0185 fallback when that receipt is absent)."""
from __future__ import annotations

import platform
import subprocess
import sys

from common import REPO, load_json


def python_version_line() -> str:
    proc = subprocess.run(
        [sys.executable, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return line or sys.version.split()[0]


def pin_major_minor() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}"


def inventory() -> list[dict]:
    ci_pin = None
    cnf185 = REPO / "command-center" / "receipts" / "CNF-0185.json"
    if cnf185.is_file():
        try:
            doc = load_json(cnf185)
            rows = doc.get("inventory") or doc.get("pinned_toolchain_inventory") or []
            if isinstance(rows, list) and rows:
                return rows
        except (OSError, ValueError):
            pass
        ci_pin = "CNF-0185-PRESENT-UNPARSED"
    return [
        {
            "tool": "python3",
            "local_version": python_version_line(),
            "pin_major_minor": pin_major_minor(),
            "invoke": "python3 --version",
            "invoke_used": f"{sys.executable} --version",
            "ci_pin": ci_pin,
            "platform": platform.system().lower(),
            "claim_verdict_local": "PIN-CAPTURED",
            "claim_verdict_ci": "NOT-CHECKED",
        }
    ]


def pin_ok(pkg_pins: list[dict]) -> tuple[bool, str]:
    have = pin_major_minor()
    for pin in pkg_pins:
        if pin.get("tool") != "python3":
            continue
        raw = str(pin.get("version") or "").replace("Python ", "").strip()
        want_mm = ".".join(raw.split(".")[:2])
        if want_mm == have:
            return True, have
        return False, f"python pin {raw} != local {have}"
    return False, "python3 pin missing"
