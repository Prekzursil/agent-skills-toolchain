#!/usr/bin/env python3
"""Package payload and destination builders for TST-0200."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from installer import abs_dest, plan_install, WIN32_MAX_PATH

PACKAGE: dict[str, str] = {
    "plugin.json": '{"id":"pkg.tst-0200","version":"1.0.0"}\n',
    "hooks/hook.pre-tool.json": '{"hook":"pre-tool","id":"hook.pre-tool"}\n',
    "rules/rule.no-secrets.md": "# no-secrets\nDo not embed credentials.\n",
    "skills/skill.council/SKILL.md": "# council\nFour-voice prompt skill.\n",
    "workflows/wf.catalog-class.discovery-only.json": '{"id":"wf.catalog-class.discovery-only"}\n',
}


def longest_rel(package: dict[str, str] | None = None) -> str:
    pkg = package or PACKAGE
    return max(pkg, key=lambda r: len(r.replace("\\", "/")))


def longest_measured(dest: Path, package: dict[str, str] | None = None) -> int:
    pkg = package or PACKAGE
    planned = plan_install(dest, pkg)
    return max(int(r["measured_chars"]) for r in planned)


def make_short_dest(root: Path) -> Path:
    dest = Path(root) / "short"
    n = longest_measured(dest)
    if n > WIN32_MAX_PATH:
        raise RuntimeError(f"short dest already over MAX_PATH: {n} at {abs_dest(dest)}")
    return dest


def make_deep_dest(root: Path, *, overshoot: int = 12) -> Path:
    """Grow a dest so the longest packaged file path is > 260 characters."""
    root = Path(root)
    want = WIN32_MAX_PATH + overshoot
    dest = root / "deep"
    pad = 1
    while longest_measured(dest, PACKAGE) <= WIN32_MAX_PATH:
        pad += 4
        if pad <= 240:
            dest = root / ("w" * pad)
        else:
            extra = min(pad - 240, 240)
            dest = root / ("w" * 240) / ("w" * max(extra, 1))
        if pad > 800:
            raise RuntimeError("could not construct a dest over MAX_PATH")
    # Stretch to a comfortable overshoot so the case is not a 261-vs-260 flake.
    while longest_measured(dest, PACKAGE) < want:
        dest = dest / "x"
        if len(str(abs_dest(dest))) > 4000:
            break
    n = longest_measured(dest, PACKAGE)
    if n <= WIN32_MAX_PATH:
        raise RuntimeError(f"deep dest still in-budget: {n}")
    return dest


def dest_report(dest: Path) -> dict[str, Any]:
    planned = plan_install(dest, PACKAGE)
    return {
        "dest": str(abs_dest(dest)),
        "longest_measured_chars": max(int(r["measured_chars"]) for r in planned),
        "files": [
            {
                "rel": r["rel"],
                "measured_chars": r["measured_chars"],
                "over_limit": int(r["measured_chars"]) > WIN32_MAX_PATH,
            }
            for r in planned
        ],
    }
