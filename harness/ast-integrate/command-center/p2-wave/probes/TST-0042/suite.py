#!/usr/bin/env python3
"""Conformance suite for the hook-dispatch contract (written before a full runtime).

Rules:
  R-EVENT     event present and in the pinned client vocabulary (unknown => load reject)
  R-MATCHER   matcher declared and non-empty
  R-INTERP    explicit interpreter (not shebang, not the script path)
  R-BIND      dispatcher actually binds (interpreter on PATH, script exists)

Both-states: the same suite function PASSES a conforming manifest and FAILS
an invented-event manifest in one process.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
LIVE = REPO / "hooks" / "_dispatch" / "manifest.json"
DISPATCH_PY = REPO / "hooks" / "_dispatch" / "dispatch.py"

CASES = (
    ("conforming", "conforming.json", True, None),
    ("invented-event", "invented-event.json", False, "UNKNOWN_EVENT"),
    ("missing-event", "missing-event.json", False, "MISSING_EVENT"),
    ("missing-matcher", "missing-matcher.json", False, "MISSING_MATCHER"),
    ("missing-interpreter", "missing-interpreter.json", False, "MISSING_INTERPRETER"),
    ("shebang-only", "shebang-only.json", False, "IMPLICIT_INTERPRETER"),
    ("script-as-interpreter", "script-as-interpreter.json", False, "IMPLICIT_INTERPRETER"),
    ("missing-script", "missing-script.json", False, "UNBOUND_SCRIPT"),
)


def load_dispatch():
    spec = importlib.util.spec_from_file_location("hook_dispatch_tst0042", DISPATCH_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {DISPATCH_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_case(mod, name: str, filename: str, expect_pass: bool, expect_code: str | None) -> dict[str, Any]:
    path = FIX / filename
    result = mod.load_and_bind(path, REPO)
    if expect_pass:
        ok = bool(result.get("ok")) and bool(result.get("all_bound"))
        observed = "PASS" if ok else "FAIL"
        return {
            "name": name,
            "file": f"command-center/p2-wave/probes/TST-0042/fixtures/{filename}",
            "expect_pass": True,
            "observed": observed,
            "ok": ok,
            "detail": result,
        }
    if expect_code == "UNBOUND_SCRIPT":
        # Load must succeed; bind must fail. Unknown events are a different rule.
        load_ok = bool(result.get("ok")) and result.get("rejected") is False
        binds = result.get("binds") or []
        unbound = load_ok and binds and not all(b.get("bound") for b in binds)
        return {
            "name": name,
            "file": f"command-center/p2-wave/probes/TST-0042/fixtures/{filename}",
            "expect_pass": False,
            "expect_code": expect_code,
            "observed": "REJECTED" if unbound else "MISSED",
            "ok": unbound,
            "detail": result,
        }
    code = result.get("code")
    rejected = bool(result.get("rejected")) and code == expect_code
    return {
        "name": name,
        "file": f"command-center/p2-wave/probes/TST-0042/fixtures/{filename}",
        "expect_pass": False,
        "expect_code": expect_code,
        "observed_code": code,
        "observed": "REJECTED" if rejected else "MISSED",
        "ok": rejected,
        "detail": result,
    }


def run_suite() -> dict[str, Any]:
    mod = load_dispatch()
    rows = [run_case(mod, *c) for c in CASES]
    by_name = {r["name"]: r for r in rows}
    both = {
        "conforming_passes": bool(by_name["conforming"]["ok"]),
        "invented_event_rejected": bool(by_name["invented-event"]["ok"]),
        "same_process": True,
        "holds": bool(by_name["conforming"]["ok"]) and bool(by_name["invented-event"]["ok"]),
    }
    live = mod.load_and_bind(LIVE, REPO)
    live_ok = bool(live.get("ok")) and bool(live.get("all_bound")) and int(live.get("count") or 0) >= 1
    all_ok = all(r["ok"] for r in rows) and live_ok and both["holds"]
    return {
        "unit_id": "TST-0042",
        "pass": all_ok,
        "vocabulary": sorted(mod.CLIENT_EVENT_VOCABULARY),
        "cases": rows,
        "both_states": both,
        "live": live,
        "live_ok": live_ok,
        "negative_per_rule": {
            "R-EVENT": by_name["invented-event"]["ok"] and by_name["missing-event"]["ok"],
            "R-MATCHER": by_name["missing-matcher"]["ok"],
            "R-INTERP": by_name["missing-interpreter"]["ok"]
            and by_name["shebang-only"]["ok"]
            and by_name["script-as-interpreter"]["ok"],
            "R-BIND": by_name["missing-script"]["ok"] and live_ok,
        },
    }


def main() -> int:
    report = run_suite()
    print(json.dumps({k: report[k] for k in ("unit_id", "pass", "both_states", "live_ok", "negative_per_rule")}, sort_keys=True))
    for row in report["cases"]:
        mark = "ok" if row["ok"] else "FAIL"
        extra = row.get("expect_code") or "PASS"
        print(f"  {mark} {row['name']} expect={extra} observed={row.get('observed')}")
    if not report["pass"]:
        print("FAILED:TST-0042 suite")
        return 1
    print("SUCCESS:TST-0042-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
