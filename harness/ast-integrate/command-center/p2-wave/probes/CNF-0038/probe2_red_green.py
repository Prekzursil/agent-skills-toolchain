#!/usr/bin/env python3
"""Probe 2: live red-then-green re-run plus already-satisfied and overfitted controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import classify as K  # noqa: E402
import controls as C  # noqa: E402
import execute as E  # noqa: E402
from paths import AUTHOR_TEST, OUT_PATH, POST_FIX, PRE_FIX, SYNTH_TEST, UNIT  # noqa: E402


def executions_of(artifact: dict) -> list:
    if isinstance(artifact.get("executions"), list):
        return artifact["executions"]
    report = artifact.get("report")
    if isinstance(report, dict) and isinstance(report.get("executions"), list):
        return report["executions"]
    return []


def main() -> int:
    if not OUT_PATH.is_file() or not SYNTH_TEST.is_file():
        print("FAILED:CNF-0038-probe2 artifact or synthesised test missing")
        return 1
    artifact = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    pre = E.run_python(SYNTH_TEST, PRE_FIX)
    post = E.run_python(SYNTH_TEST, POST_FIX)
    pattern = K.classify(pre["verdict"], post["verdict"])
    if pattern["classification"] != "red-then-green":
        print("FAILED:CNF-0038-probe2 live pattern", pattern, pre, post)
        return 1
    recorded = executions_of(artifact)
    by_role = {row.get("role"): row for row in recorded if isinstance(row, dict)}
    for role, live in (("pre-fix", pre), ("post-fix", post)):
        rec = by_role.get(role) or {}
        if rec.get("verdict") != live["verdict"] or rec.get("exit_code") != live["exit_code"]:
            print(f"FAILED:CNF-0038-probe2 {role} mismatch rec={rec} live={live}")
            return 1
        if live["verdict"] == "RED" and "CASE" not in live["verbatim_stdout"]:
            print("FAILED:CNF-0038-probe2 red run produced no CASE lines")
            return 1
        if live["verdict"] == "GREEN" and "SUMMARY failed=0" not in live["verbatim_stdout"]:
            print("FAILED:CNF-0038-probe2 green run missing SUMMARY failed=0")
            return 1
    ctrls = C.pattern_controls()
    if not ctrls["already_satisfied"]["caught"]:
        print("FAILED:CNF-0038-probe2 already-satisfied control silent", ctrls)
        return 1
    if not ctrls["overfitted_patch"]["caught"]:
        print("FAILED:CNF-0038-probe2 overfitted control silent", ctrls)
        return 1
    author_pre = E.run_python(AUTHOR_TEST, PRE_FIX)
    author_post = E.run_python(AUTHOR_TEST, POST_FIX)
    if author_pre["verdict"] != "RED" or author_post["verdict"] != "GREEN":
        print("FAILED:CNF-0038-probe2 author pair unexpected", author_pre, author_post)
        return 1
    doc = {
        "independent_pre": pre["verdict"],
        "independent_post": post["verdict"],
        "author_pre": author_pre["verdict"],
        "author_post": author_post["verdict"],
        "pattern": pattern["classification"],
        "already_satisfied_caught": True,
        "overfitted_caught": True,
        "pass": True,
        "probe": "probe2-red-green",
        "unit_id": UNIT,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        f"pre={pre['verdict']} post={post['verdict']} "
        f"already_satisfied_caught=True overfitted_caught=True"
    )
    print("SUCCESS:CNF-0038-probe2 live red-then-green and pattern controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
