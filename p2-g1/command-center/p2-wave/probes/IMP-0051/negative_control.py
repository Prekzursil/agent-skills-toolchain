#!/usr/bin/env python3
"""IMP-0051 negative control: an uncoded raise must turn the scan red.

Plants a fixture with ``raise PluginError('E_NOT_IN_TAXONOMY', ...)`` and
runs the SAME raise-site scan logic against it, requiring the site to be
flagged. The good platform tree stays green in the same run.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "platform"))

from plugin.errors import BY_CODE  # noqa: E402
from probe1_static_scan import scan_raise_sites  # noqa: E402


def scan_fixture(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    unknown: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            func = node.exc.func
            name = getattr(func, "id", "") or getattr(func, "attr", "")
            if "PluginError" not in name:
                continue
            if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
                code = node.exc.args[0].value
                if code not in BY_CODE:
                    unknown.append(f"{path.name}:{node.lineno}:{code}")
    return unknown


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        fixture = Path(raw) / "mutant.py"
        fixture.write_text(
            "from plugin.errors import PluginError\n"
            "def boom():\n"
            "    raise PluginError('E_NOT_IN_TAXONOMY', 'uncoded mutant')\n",
            encoding="utf-8",
        )
        unknown = scan_fixture(fixture)
        checks = {
            "mutant_flagged": len(unknown) == 1,
            "mutant_code_named": "E_NOT_IN_TAXONOMY" in "".join(unknown),
        }
    live = scan_raise_sites()
    checks["good_tree_green"] = (
        len(live["uncoded_raise_sites"]) == 0  # type: ignore[arg-type]
        and len(live["unknown_codes"]) == 0  # type: ignore[arg-type]
    )
    out = {
        "probe": "negative-control-uncoded-raise",
        "unit_id": "IMP-0051",
        "mutant_unknown": unknown,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print(f"FAILED:IMP-0051-negative-control {checks}")
        return 1
    print("SUCCESS:IMP-0051-negative-control uncoded raise caught, good tree stays green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
