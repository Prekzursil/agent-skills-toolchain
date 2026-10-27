#!/usr/bin/env python3
"""TST-0088 probe1: kill mid-stream, fan-in must fail it at condition 5.

Live SIGKILL injection on this box: spawn the victim writer, wait for
READY (parseable SUCCESS-looking artifact already on disk), kill it
hard, then classify the orphaned file with the fan-in conditions.
Asserts the receipt: truncated/plausible/no-sentinel => FAILED at
condition 5; wholly-absent => condition 2; complete-with-sentinel =>
SUCCESS. The kill is the datum (retry_policy: NO retry)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0088"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from fanin import classify  # noqa: E402

UNIT = "TST-0088"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0088" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    td = tempfile.mkdtemp(prefix="tst0088-p1-")
    try:
        dest = Path(td) / "orphaned-partial.json"
        victim = subprocess.Popen([sys.executable, "-B", str(HERE / "victim_writer.py"), str(dest)],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        line = victim.stdout.readline().strip()
        chk(line == "READY", "victim-ready", line)
        saw_ready = line == "READY"
        existed_before_kill = dest.exists() and dest.stat().st_size > 0
        victim.kill()
        rc = victim.wait(timeout=30)
        chk(rc is not None, "victim-terminated", str(rc))
        verdict = classify(dest, "SUCCESS:VICTIM-0088")
        chk(verdict["verdict"] == "FAILED" and verdict["condition_id"] == 5, "truncated-must-fail-at-5", json.dumps(verdict)[:200])
        parsed = True
        try:
            json.loads(dest.read_text(encoding="utf-8"))
        except Exception:
            parsed = False
        plausible = parsed and json.loads(dest.read_text(encoding="utf-8")).get("state") == "SUCCESS"
        chk(parsed and plausible, "partial-parses-and-looks-success", str(parsed) + "/" + str(plausible))
        absent = Path(td) / "never-written.json"
        v2 = classify(absent, "SUCCESS:VICTIM-0088")
        chk(v2["verdict"] == "FAILED" and v2["condition_id"] == 2, "absent-must-fail-at-2", json.dumps(v2))
        complete = Path(td) / "complete.json"
        complete.write_text(json.dumps({"unit_id": "VICTIM-0088", "state": "SUCCESS",
                                        "completion_sentinel": "SUCCESS:VICTIM-0088"}), encoding="utf-8")
        v3 = classify(complete, "SUCCESS:VICTIM-0088")
        chk(v3["verdict"] == "SUCCESS", "complete-with-sentinel-passes", json.dumps(v3))
        inj = doc.get("injection") or {}
        chk(inj.get("kill_issued") is True and int(inj.get("returncode", 0)) in (-9, 1), "receipt-kill-recorded")
        cls = doc.get("classification") or {}
        chk(int(cls.get("condition_id", -1)) == 5 and str(cls.get("condition_name", "")).startswith("required sentinel"), "receipt-condition-5")
        bs = doc.get("both_states") or {}
        chk(str(bs.get("truncated_verdict")) == "FAILED" and int(bs.get("absent_condition_id", 0)) == 2, "receipt-both-states")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({"victim_ready": saw_ready, "existed_before_kill": existed_before_kill,
                      "kill_returncode": rc, "orphan": verdict,
                      "absent_control": v2, "complete_control": v3["verdict"]}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 live hard-kill of a mid-stream writer: orphaned file exists, parses, looks SUCCESS, carries NO sentinel - fan-in classifies FAILED at condition 5 (sentinel present?); absent fails at 2; complete+sentinel passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
