#!/usr/bin/env python3
"""IMP-0012 probe1 (source): live manifest entrypoints all declare an interpreter
and pass the linter; the negative control (undeclared entrypoint) fails the linter."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.interpreters import DeclarationError, lint_entrypoints, load_manifest  # noqa: E402


def main() -> int:
    rows = lint_entrypoints()
    checks = {
        "entrypoints_present": len(rows) >= 6,
        "all_declared_python3_floor_311": all(
            r["interpreter"] == "python3" and r["min_version"] == "3.11" for r in rows
        ),
        "paths_exist": all((REPO / r["path"]).is_file() for r in rows),
    }
    # NEGATIVE CONTROL: an entrypoint with no declaration must fail the linter
    doc = load_manifest()
    broken = json.loads(json.dumps(doc))
    broken["entrypoints"].append({"id": "hook.undeclared", "kind": "hook", "path": "hooks/_dispatch/run.py"})
    raised = False
    try:
        lint_entrypoints(broken)
    except DeclarationError:
        raised = True
    checks["undeclared_fails_linter"] = raised
    for k, v in checks.items():
        print(f"{k}={v}")
    if not all(checks.values()):
        print("FAILED:IMP-0012-probe1 " + json.dumps(checks))
        return 1
    print("SUCCESS:IMP-0012-probe1 all entrypoints declared; undeclared control fails the linter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
