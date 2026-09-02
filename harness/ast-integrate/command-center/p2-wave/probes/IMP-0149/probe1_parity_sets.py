#!/usr/bin/env python3
"""Probe 1: Python and JS emit identical violation-id SETS over shared fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUN = REPO / "tools" / "agentspec-js" / "parity" / "run.py"
BEHAVIOUR = REPO / "tools" / "agentspec-js" / "parity" / "emit_behaviour_py.py"
EMIT_PY = REPO / "tools" / "agentspec-js" / "parity" / "emit_py.py"
CORPUS = REPO / "tools" / "agentspec-js" / "fixtures" / "corpus"


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    if not any(CORPUS.glob("*.json")):
        code, text = run(
            [
                sys.executable,
                "-B",
                str(REPO / "tools" / "agentspec-js" / "fixtures" / "build_corpus.py"),
            ]
        )
        if code != 0:
            print(text)
            print("FAILED:IMP-0149-probe1 corpus build")
            return 1
    code, text = run([sys.executable, "-B", str(RUN)])
    print(text[-4000:])
    if code != 0:
        print("FAILED:IMP-0149-probe1 parity not green")
        return 1
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        print("FAILED:IMP-0149-probe1 no JSON report")
        return 1
    report = json.loads(text[start : end + 1])
    if report.get("compared_as") != "sets":
        print("FAILED:IMP-0149-probe1 comparison is not set-based")
        return 1
    if report.get("fixture_count", 0) < 40:
        print("FAILED:IMP-0149-probe1 too few fixtures")
        return 1
    if report.get("failures"):
        print("FAILED:IMP-0149-probe1 set mismatch")
        return 1
    c2, t2 = run([sys.executable, "-B", str(EMIT_PY)])
    if c2 != 0:
        print(t2)
        print("FAILED:IMP-0149-probe1 emit_py")
        return 1
    s2, e2 = t2.find("{"), t2.rfind("}")
    py_map = json.loads(t2[s2 : e2 + 1])
    if "valid.json" not in py_map:
        print("FAILED:IMP-0149-probe1 valid.json missing")
        return 1
    if py_map["valid.json"] != []:
        print("FAILED:IMP-0149-probe1 valid fixture not clean", py_map["valid.json"])
        return 1
    if "param-unknown-key.json" not in py_map:
        print("FAILED:IMP-0149-probe1 planted-key fixture missing")
        return 1
    if "param-unknown-key" not in py_map["param-unknown-key.json"]:
        print("FAILED:IMP-0149-probe1 param-unknown-key not emitted")
        return 1
    phase7_types = {
        "phase7-all-types.json",
    }
    if "phase7-all-types.json" not in py_map or py_map["phase7-all-types.json"] != []:
        print("FAILED:IMP-0149-probe1 phase-7 all-types not clean", py_map.get("phase7-all-types.json"))
        return 1
    c3, t3 = run([sys.executable, "-B", str(BEHAVIOUR)])
    print(t3[-1500:])
    if c3 != 0:
        print("FAILED:IMP-0149-probe1 behaviour AST")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-parity-sets",
                "unit_id": "IMP-0149",
                "compared_as": "sets",
                "fixture_count": report["fixture_count"],
                "valid_clean": True,
                "phase7_all_types_clean": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0149-probe1 python/js violation-id sets identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
