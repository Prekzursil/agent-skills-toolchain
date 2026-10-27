#!/usr/bin/env python3
# REL-0014 probe2: detector control + tooling-exit honesty (resume 2026-10-25).
# T2 detector_known_advisory: the pinned scanner MUST detect CVE-2021-23337 on
#   lodash 4.17.20 (mutation control) and stay silent on the clean lockfile.
# T3 tooling_exit_not_checked: a scanner command that CANNOT run must leave
#   the gate in NOT-CHECKED - never PASS - and a promotion consuming such a
#   result must refuse (tool-error-as-pass), visible in the log.
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0014_scanner", HERE / "scanner.py")
S = importlib.util.module_from_spec(spec)
sys.modules["rel0014_scanner"] = S
spec.loader.exec_module(S)
CLEAN = HERE / "fixtures" / "lockfile-clean.json"
VULN = HERE / "fixtures" / "lockfile-vulnerable.json"


def fail(msg):
    print("FAILED:REL-0014-probe2 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0014-p2-"))
    try:
        p = subprocess.run([sys.executable, "-B", str(HERE / "scanner.py"),
                            "--lockfile", str(VULN), "--db-pull", "2026-08-24T18:00:00Z",
                            "--report", str(tmp / "vuln.json")],
                           capture_output=True, text=True, timeout=300)
        rep = json.loads((tmp / "vuln.json").read_text(encoding="utf-8"))
        ids = [f["advisory_id"] for f in rep.get("findings") or []]
        print("detector exit=%d findings=%s" % (p.returncode, json.dumps(ids)))
        if p.returncode != 1 or "CVE-2021-23337" not in ids:
            return fail("detector-missed-known-advisory")
        pc = subprocess.run([sys.executable, "-B", str(HERE / "scanner.py"),
                             "--lockfile", str(CLEAN), "--db-pull", "2026-08-24T18:00:00Z"],
                            capture_output=True, text=True, timeout=300)
        if pc.returncode != 0:
            return fail("clean-lockfile-flagged")
        # T3: a stored result whose scanner never ran (exit 127) is NOT-CHECKED
        stored = {"timestamp": "2026-08-24T18:00:00Z", "exit_code": 127,
                  "classification": "PASS", "findings": [],
                  "artifact_sha256": rep.get("artifact_sha256")}
        (tmp / "stored-bad.json").write_text(json.dumps(stored), encoding="utf-8", newline="\n")
        log = tmp / "promotion-log.json"
        g = subprocess.run([sys.executable, "-B", str(HERE / "gate.py"),
                            "--stored", str(tmp / "stored-bad.json"),
                            "--now", "2026-08-24T18:30:00Z", "--window", "86400",
                            "--lockfile", str(CLEAN), "--log", str(log),
                            "--rescan-pull", "2026-08-24T18:30:00Z"],
                           capture_output=True, text=True, timeout=300)
        events = json.loads(log.read_text(encoding="utf-8"))
        refused = [e for e in events if e.get("event") == "REFUSED"]
        print("tooling-refusal classification=" + str(refused[0].get("classification") if refused else None))
        if not refused or refused[0].get("classification") != "tool-error-as-pass":
            return fail("tool-error-not-visible-as-refusal")
        rec = json.loads((REPO / "command-center/receipts/REL-0014.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        obs = (rec.get("report") or {}).get("observations") or []
        tool_obs = [o for o in obs if o.get("name") == "tooling_exit_127"]
        if not tool_obs or tool_obs[0].get("measured") != "NOT-CHECKED":
            return fail("receipt-tooling-not-checked-drift")
        det_obs = [o for o in obs if o.get("name") == "detector_cve_2021_23337"]
        if not det_obs or det_obs[0].get("measured") != "CVE-2021-23337":
            return fail("receipt-detector-observation-drift")
        if "CVE-2021-23337" not in json.dumps(rec):
            return fail("receipt-detector-advisory-absent")
        print("SUCCESS:REL-0014-probe2 detector-and-tooling-exit")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
