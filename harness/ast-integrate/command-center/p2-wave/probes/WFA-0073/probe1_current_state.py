#!/usr/bin/env python3
"""Probe 1: current-state failure count over all 284 records, by disposition class.

A high count is data, not a lane failure. Independent recount must match the
artifact. Does not disarm the gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate  # noqa: E402
import registry as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0073-disposition-evidence-gate.json"
EXPECTED_N = 284


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0073-probe1 {msg}")
    return 1


def main() -> int:
    loaded = R.load_registry()
    report = gate.evaluate_registry(loaded["records"])
    print(
        json.dumps(
            {
                "probe": "probe1-current-state",
                "unit_id": "WFA-0073",
                "source": loaded.get("source"),
                "live": loaded.get("live"),
                "n": report["n"],
                "fail_n": report["fail_n"],
                "pass_n": report["pass_n"],
                "by_class": report["by_class"],
                "fail_by_class": report["fail_by_class"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if report["n"] != EXPECTED_N:
        return fail(f"n={report['n']} want {EXPECTED_N}")
    if loaded.get("source") == "catalog-histogram-stand-in":
        hist = R.catalog_histogram()
        if report["by_class"] != hist:
            return fail(f"stand-in histogram drift {report['by_class']}")
        # Empty typed evidence => every gated class fails, ungated pass.
        want_fail = {
            "ADOPT-AS-IS": hist["ADOPT-AS-IS"],
            "ADOPT-WITH-WRAPPER": hist["ADOPT-WITH-WRAPPER"],
            "RETIRE": hist["RETIRE"],
            "UNKNOWN-NEEDS-PROBE": hist["UNKNOWN-NEEDS-PROBE"],
        }
        if report["fail_by_class"] != want_fail:
            return fail(f"stand-in fail_by_class {report['fail_by_class']} want {want_fail}")
        if report["fail_n"] != sum(want_fail.values()):
            return fail(f"stand-in fail_n {report['fail_n']}")
        if "TRANSLATE" in report["by_class"]:
            return fail("stand-in unexpectedly contains TRANSLATE")
    if report["fail_n"] < 1:
        return fail("zero failures: a gate that only ever passes is no gate")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0073" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    census = doc.get("current_state") or {}
    if int(census.get("n") or 0) != report["n"]:
        return fail(f"artifact n {census.get('n')} != live {report['n']}")
    if int(census.get("fail_n") or -1) != report["fail_n"]:
        return fail(f"artifact fail_n {census.get('fail_n')} != live {report['fail_n']}")
    if census.get("fail_by_class") != report["fail_by_class"]:
        return fail("artifact fail_by_class disagreement")
    if census.get("by_class") != report["by_class"]:
        return fail("artifact by_class disagreement")
    print(
        f"n={report['n']} fail={report['fail_n']} "
        f"fail_by_class={json.dumps(report['fail_by_class'], sort_keys=True)} "
        f"live={loaded.get('live')} source={loaded.get('source')}"
    )
    print("SUCCESS:WFA-0073-probe1 current-state failure census over 284")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
