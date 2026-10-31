#!/usr/bin/env python3
"""probe2 for TST-0020: run the actual grep pathology both states LIVE.

Bad state  : grep -c MISSING fixtures/prs.txt || echo 0  -> "0\n0\n"
             (grep prints 0 and exits 1, then || echoes another 0)
             -> post-processor must FAIL THE RUN as detector-failure, name the
             violated mutex invariant, and publish NO numbers.
Good state : grep -c MISSING fixtures/prs.txt || true     -> "0\n"
             -> consistent counts, run passes, numbers published.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0020"
HERE = Path(__file__).resolve().parent
PRS = HERE / "fixtures" / "prs.txt"
UNIVERSE = len(PRS.read_text(encoding="utf-8").strip().splitlines())


def load_pp():
    spec = importlib.util.spec_from_file_location("tst0020_pp", HERE / "postprocessor.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tst0020_pp"] = mod
    spec.loader.exec_module(mod)
    return mod


def grep_out(cmd: str) -> str:
    p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, cwd=str(HERE))
    return p.stdout


def main() -> int:
    pp = load_pp()
    checks = {}
    bad_raw = grep_out( f"grep -c DOES-NOT-OCCUR-STRING fixtures/{PRS.name} || echo 0")
    bad_counts = pp.naive_counts(bad_raw, UNIVERSE)
    bad_res = pp.postprocess(bad_counts)
    checks["contradictory_counts_fail_the_run"] = bad_res["ok"] is False and bad_res["classification"] == "detector-failure"
    checks["failure_names_violated_invariant"] = "mutex-all-hit-empty-intersection" in bad_res["violated_invariants"]
    checks["no_numbers_published_on_failure"] = bad_res["published_numbers"] is None
    good_raw = grep_out( f"grep -c DOES-NOT-OCCUR-STRING fixtures/{PRS.name} || true")
    good_counts = pp.naive_counts(good_raw, UNIVERSE)
    good_res = pp.postprocess(good_counts)
    checks["consistent_counts_pass"] = good_res["ok"] is True
    checks["good_numbers_consistent"] = (
        good_res["published_numbers"]["hit"] + good_res["published_numbers"]["miss"] == UNIVERSE
        and good_res["published_numbers"]["intersection"] <= UNIVERSE
    )
    checks["invariants_declared_before_run"] = json.loads((HERE / "invariants.json").read_text(encoding="utf-8"))["declared_before_run"] is True
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({
        "unit_id": UID, "probe": "probe2-both-states-live", "pass": ok,
        "bad_state": {"raw": bad_raw.splitlines(), "counts": {k: bad_counts[k] for k in ("hit", "miss", "intersection", "universe", "claims")}, "result": {k: bad_res[k] for k in ("ok", "classification", "violated_invariants", "published_numbers")}},
        "good_state": {"raw": good_raw.splitlines(), "published": good_res["published_numbers"]},
        "checks": checks,
    }))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live grep -c||echo 0 doubled zero -> run failed as detector-failure naming mutex-all-hit-empty-intersection, zero published; || true state passes with consistent counts")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
