#!/usr/bin/env python3
"""Probe 1: every live entrypoint declares an interpreter; undeclared fails.

Signal 1 is the linter over the live .claude-plugin/plugin.json.
Signal 2 is the negative-control fixture (no interpreter) which MUST fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.interpreters import DeclarationError, lint_entrypoints, load_manifest  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0012.json"
UNDECLARED = REPO / "tools/plugin/tests/fixtures/undeclared.json"
TEST = REPO / "tools/plugin/tests/test_interpreters.py"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0012-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0012":
        print("FAILED:IMP-0012-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0012" not in text:
        print("FAILED:IMP-0012-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0012-probe1 self-declared", doc.get("state"))
        return 1

    rows = lint_entrypoints()
    if len(rows) < 2:
        print(f"FAILED:IMP-0012-probe1 expected >=2 entrypoints got {len(rows)}")
        return 1
    for row in rows:
        if not row.get("interpreter") or not row.get("min_version"):
            print("FAILED:IMP-0012-probe1 undeclared row", row)
            return 1
        script = REPO / row["path"]
        if not script.is_file():
            print("FAILED:IMP-0012-probe1 missing script", row["path"])
            return 1
        print(
            f"declared id={row['id']} interpreter={row['interpreter']} "
            f"min_version={row['min_version']} path={row['path']}"
        )

    bad = load_manifest(UNDECLARED)
    try:
        lint_entrypoints(bad)
    except DeclarationError as exc:
        fired = True
        bad_text = str(exc)
    else:
        fired = False
        bad_text = "linter accepted undeclared entrypoint"
    if not fired or "missing interpreter" not in bad_text:
        print("FAILED:IMP-0012-probe1 negative control silent", bad_text)
        return 1
    print(f"negative_control_fired={fired} detail={bad_text}")

    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(TOOLS), "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(tail.splitlines()[-1] if tail else "no-test-output")
    if proc.returncode != 0 or "SUCCESS:test_interpreters" not in tail:
        print(tail[-2000:])
        print("FAILED:IMP-0012-probe1 test_interpreters")
        return 1

    print(
        json.dumps(
            {
                "adjudicated": False,
                "declared": len(rows),
                "negative_control_fired": True,
                "pass": True,
                "probe": "probe1-declarations",
                "unit_id": "IMP-0012",
            }
        )
    )
    print("SUCCESS:IMP-0012-probe1 every entrypoint declares an interpreter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
