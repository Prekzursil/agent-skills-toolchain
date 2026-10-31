#!/usr/bin/env python3
# REL-0006 probe2: downgrade restoration + MTTR (resume 2026-10-25).
# Isolated-HOME canary: install candidate (BEHAVIOR:n-candidate), show the
# version FILE alone cannot satisfy acceptance (T2), downgrade to n-1, re-run
# the N-1 acceptance probe (BEHAVIOR:n-1-accept), measure MTTR with a named
# clock, and fire the recorded negative controls: a tiny SLO must REJECT the
# same measurement, and the isolation control must reject the owner home.
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0006_drill", HERE / "drill.py")
D = importlib.util.module_from_spec(spec)
sys.modules["rel0006_drill"] = D
spec.loader.exec_module(D)


def fail(msg):
    print("FAILED:REL-0006-probe2 " + str(msg))
    return 1


def main():
    rec = json.loads((REPO / "command-center/receipts/REL-0006.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if rec.get("isolation", {}).get("touched_owner_profile") is not False:
        return fail("receipt-isolation-drift")
    owner_home = Path.home()
    store = Path(tempfile.mkdtemp(prefix="rel0006-store-"))
    home = Path(tempfile.mkdtemp(prefix="rel0006-canary-"))
    if home.resolve() == owner_home.resolve():
        return fail("isolation-control-rejects-owner-home")
    try:
        D.build_store(store)
        zpath = store / "n-1.zip"
        cand_plugin = D.make_package("2.0.0-n", "n-candidate")
        cand_zip = Path(tempfile.mkdtemp(prefix="rel0006-cand-")) / "n.zip"
        D.install(home, D.zip_dir_to_path(cand_plugin, cand_zip))
        before = D.run_acceptance(home)
        D.write_version_disqualified_marker(home, "1.0.0-n-1")
        before_version_lies = D.run_acceptance(home)
        print("acceptance-before passed=" + str(before["passed"]) + " output=" + before["output"])
        if before["passed"] or before["output"] != "BEHAVIOR:n-candidate":
            return fail("before-state-drift:" + json.dumps(before))
        if before_version_lies["passed"] or before_version_lies["output"] != "BEHAVIOR:n-candidate":
            return fail("T2-version-string-not-disqualified")
        t0 = time.perf_counter_ns()
        D.install(home, zpath)
        after = D.run_acceptance(home)
        t1 = time.perf_counter_ns()
        mttr_s = (t1 - t0) / 1e9
        epoch_ns = time.time_ns()
        print("acceptance-after passed=" + str(after["passed"]) + " output=" + after["output"])
        print("MTTR seconds=%.6f clock_source=time.perf_counter_ns+time.time_ns runbook_slo_seconds=30.0 within_slo=%s"
              % (mttr_s, mttr_s <= D.SLO_SECONDS))
        if not after["passed"] or after["output"] != "BEHAVIOR:n-1-accept":
            return fail("restore-not-proven:" + json.dumps(after))
        if mttr_s > D.SLO_SECONDS:
            return fail("mttr-over-runbook-slo")
        if mttr_s <= D.TINY_SLO_SECONDS:
            return fail("tiny-slo-control-not-firing")
        m = rec.get("mttr") or {}
        if m.get("runbook_slo_seconds") != 30.0 or m.get("within_slo") is not True:
            return fail("receipt-mttr-numbers-drift")
        ap = rec.get("acceptance_probe") or {}
        if (ap.get("before") or {}).get("output") != "BEHAVIOR:n-candidate" or \
           (ap.get("after") or {}).get("output") != "BEHAVIOR:n-1-accept":
            return fail("receipt-acceptance-outputs-drift")
        print("epoch_ns_at_restore=" + str(epoch_ns))
        print("SUCCESS:REL-0006-probe2 restore-mttr")
        return 0
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
