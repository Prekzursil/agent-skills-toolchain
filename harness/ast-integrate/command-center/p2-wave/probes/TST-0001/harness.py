#!/usr/bin/env python3
"""Harness: run any candidate reducer against the reference oracle.

Agreement is asserted per condition (failing_condition_id + reason + verdict
bytes), not on the aggregate boolean. A candidate that always returns PASS
must fail this harness.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from case import snapshot_from_case  # noqa: E402
from conditions import CONDITION_IDS, dumps_verdict  # noqa: E402
from corpus import cases  # noqa: E402
import oracle as O  # noqa: E402


def load_reducer(path: Path, attr: str = "reduce") -> Callable[[dict[str, Any]], dict]:
    spec = importlib.util.spec_from_file_location(path.stem + "_candidate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise ImportError(f"{path} has no callable {attr}")
    return fn


def compare_candidate(candidate: Callable[[dict[str, Any]], dict]) -> dict[str, Any]:
    rows = []
    mismatches = []
    per_condition = {cid: {"rows": 0, "agree": 0} for cid in CONDITION_IDS}
    per_condition["PASS"] = {"rows": 0, "agree": 0}
    with tempfile.TemporaryDirectory(prefix="tst0001-") as tmp:
        work = Path(tmp)
        for case in cases():
            snap = snapshot_from_case(case, work / case["id"])
            oracle_v = O.verdict(snap)
            cand_v = candidate(snap)
            o_bytes = dumps_verdict(oracle_v)
            c_bytes = dumps_verdict(cand_v)
            match = o_bytes == c_bytes
            expect = case.get("expect_failing_condition_id")
            bucket = expect if expect in per_condition else "PASS"
            per_condition[bucket]["rows"] += 1
            if match:
                per_condition[bucket]["agree"] += 1
            row = {
                "agree": match,
                "candidate": cand_v,
                "case_id": case["id"],
                "expect_failing_condition_id": expect,
                "oracle": oracle_v,
                "oracle_bytes": o_bytes.decode("ascii"),
                "candidate_bytes": c_bytes.decode("ascii"),
            }
            rows.append(row)
            if not match:
                mismatches.append(row)
    all_agree = not mismatches
    per_ok = all(v["rows"] == v["agree"] for v in per_condition.values() if v["rows"])
    return {
        "all_agree": all_agree and per_ok,
        "mismatches": [
            {
                "case_id": m["case_id"],
                "oracle": m["oracle"],
                "candidate": m["candidate"],
            }
            for m in mismatches
        ],
        "per_condition": per_condition,
        "rows": rows,
        "row_count": len(rows),
    }


def production_reducer() -> Callable[[dict[str, Any]], dict]:
    return load_reducer(REPO / "command-center" / "completion_predicate.py")


def always_true_reducer() -> Callable[[dict[str, Any]], dict]:
    return load_reducer(HERE / "always_true.py")


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "production"
    if mode == "always-true":
        report = compare_candidate(always_true_reducer())
        ok = (not report["all_agree"]) and len(report["mismatches"]) >= 12
        print(
            json.dumps(
                {
                    "all_agree": report["all_agree"],
                    "mismatch_count": len(report["mismatches"]),
                    "mode": mode,
                    "ok": ok,
                    "row_count": report["row_count"],
                },
                indent=1,
                sort_keys=True,
            )
        )
        if not ok:
            print("FAILED:TST-0001-harness always-true reducer was not rejected")
            return 1
        print("SUCCESS:TST-0001-harness always-true reducer rejected")
        return 0
    report = compare_candidate(production_reducer())
    print(
        json.dumps(
            {
                "all_agree": report["all_agree"],
                "mismatch_count": len(report["mismatches"]),
                "mode": "production",
                "per_condition": report["per_condition"],
                "row_count": report["row_count"],
                "mismatches": report["mismatches"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not report["all_agree"]:
        print("FAILED:TST-0001-harness production reducer disagrees with oracle")
        return 1
    print("SUCCESS:TST-0001-harness production reducer matches oracle per-condition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
