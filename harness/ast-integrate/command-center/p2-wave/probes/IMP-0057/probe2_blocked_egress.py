#!/usr/bin/env python3
"""IMP-0057 probe 2: OS-blocked egress; command surface still completes.

Signal 2 of 2. Independent of the static AST audit: this actually removes
the network namespace and runs the CLI. A planted urlopen must fail.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
LIB = REPO / "tools" / "lib"
CLI = PLUGIN / "privacy_cli.py"


def _run(cmd: list[str], *, netns: bool) -> subprocess.CompletedProcess:
    prefix = ["unshare", "--net"] if netns else []
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join([str(PLUGIN), str(LIB), env.get("PYTHONPATH", "")])
    return subprocess.run(
        prefix + cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def main() -> int:
    verbs = [
        ["help"],
        ["version"],
        ["telemetry-status"],
        ["consent-show"],
        ["doctor"],
        ["inventory"],
        ["try-egress"],
    ]
    cmd_rc: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as td:
        verbs.append(["local-event", str(Path(td) / "e.jsonl")])
        for args in verbs:
            proc = _run([sys.executable, "-B", str(CLI), *args], netns=True)
            cmd_rc[args[0]] = proc.returncode
            if proc.returncode != 0:
                print(proc.stdout)
                print(proc.stderr)
                print(f"FAILED:IMP-0057-probe2 command {args[0]} rc={proc.returncode}")
                return 1
        mutant = Path(td) / "mutant.py"
        mutant.write_text(
            "import urllib.request\n"
            "urllib.request.urlopen('http://203.0.113.1/telemetry-canary')\n",
            encoding="utf-8",
        )
        planted = _run([sys.executable, "-B", str(mutant)], netns=True)
    planted_caught = planted.returncode != 0
    tests = _run(
        [sys.executable, "-B", str(PLUGIN / "tests" / "test_no_default_egress.py")],
        netns=False,
    )
    # Re-run the catalog test file live (includes blocked-net cases).
    ok = planted_caught and tests.returncode == 0 and all(v == 0 for v in cmd_rc.values())
    doc = {
        "probe": "probe2-blocked-egress",
        "unit_id": "IMP-0057",
        "command_exit_codes": cmd_rc,
        "planted_urlopen_rc": planted.returncode,
        "planted_caught": planted_caught,
        "catalog_tests_rc": tests.returncode,
        "pass": ok,
    }
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0057-probe2 blocked-egress")
        return 1
    print("SUCCESS:IMP-0057-probe2 command surface completes under unshare --net")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
