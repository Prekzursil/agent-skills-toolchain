#!/usr/bin/env python3
"""Probe 1: live named-interpreter verdicts on this box + fixture matrix.

Signal (1) of the catalog evidence requirement: the probe's own verdict for
each declared interpreter. Also re-runs the fixture tests (below floor, at
floor, missing, ambiguous, PATH-hide negative control).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import interpreter_probe as ip  # noqa: E402

TEST = REPO / "tools" / "plugin" / "tests" / "test_interpreter_probe.py"


def main() -> int:
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(tail)
    if proc.returncode != 0:
        print("FAILED:IMP-0016-probe1 fixture tests")
        return 1
    if "SUCCESS:IMP-0016-tests" not in tail:
        print("FAILED:IMP-0016-probe1 tests sentinel absent")
        return 1

    report = ip.probe_all()
    if report["silent_fallback"]:
        print("FAILED:IMP-0016-probe1 silent_fallback=true")
        return 1
    if len(report["results"]) < 4:
        print(f"FAILED:IMP-0016-probe1 expected 4 interpreters got {len(report['results'])}")
        return 1

    for row in report["results"]:
        if row["silent_fallback"]:
            print(f"FAILED:IMP-0016-probe1 fallback on {row['declared_name']}")
            return 1
        if row["verdict"] in ip.VERDICTS_FAIL and not (
            isinstance(row.get("remediation"), dict) and row["remediation"].get("code")
        ):
            print(f"FAILED:IMP-0016-probe1 {row['declared_name']} fail without named remediation")
            return 1
        if row["verdict"] == "OK" and row.get("remediation") is not None:
            print(f"FAILED:IMP-0016-probe1 OK row carried remediation {row}")
            return 1
        names = set(ip.candidate_names(row["declared_name"]))
        for path in row["all_paths"]:
            if Path(path).name not in names:
                print(f"FAILED:IMP-0016-probe1 foreign basename {path}")
                return 1
        print(
            f"live {row['declared_name']} verdict={row['verdict']} "
            f"path={row['resolved_path'] or '-'} parsed={row['parsed_probe']} "
            f"floor={row['floor']} "
            f"remediation={(row['remediation'] or {}).get('code', '-')}"
        )

    print(json.dumps({"ok_count": report["ok_count"], "fail_count": report["fail_count"]}, sort_keys=True))
    print(
        f"silent_fallback={report['silent_fallback']} "
        f"declaration_source={report['declaration_source']}"
    )
    print("SUCCESS:IMP-0016-probe1 live verdicts and fixture matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
