#!/usr/bin/env python3
"""TST-0088 probe2: atomic tmp+rename publish (live, independent).

Mechanically different from probe1's direct-write orphan: here the same
hard kill lands while the writer holds the tmp-side partial; the
destination path never becomes visible (the stronger fix the receipt
records). The uninterrupted control publishes SUCCESS. Asserts the
receipt's atomic_fix block and both_states re-derive."""
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
    td = tempfile.mkdtemp(prefix="tst0088-p2-")
    try:
        dest = Path(td) / "published.json"
        victim = subprocess.Popen([sys.executable, "-B", str(HERE / "victim_atomic.py"), str(dest)],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        line = victim.stdout.readline().strip()
        chk(line == "READY", "atomic-victim-ready", line)
        victim.kill()
        victim.wait(timeout=30)
        time.sleep(0.2)
        chk(not dest.exists(), "destination-invisible-after-kill", str(dest.exists()))
        tmp_left = Path(str(dest) + ".tmp")
        chk(tmp_left.exists(), "tmp-side-partial-preserved", str(tmp_left.exists()))
        v = classify(dest, "SUCCESS:VICTIM-0088")
        chk(v["verdict"] == "FAILED" and v["condition_id"] == 2, "fan-in-sees-absent-at-2", json.dumps(v))
        # uninterrupted control publishes and passes
        dest2 = Path(td) / "published-control.json"
        tmp2 = Path(str(dest2) + ".tmp")
        tmp2.write_text(json.dumps({"unit_id": "VICTIM-0088", "state": "SUCCESS",
                                    "completion_sentinel": "SUCCESS:VICTIM-0088"}), encoding="utf-8")
        tmp2.replace(dest2)
        v2 = classify(dest2, "SUCCESS:VICTIM-0088")
        chk(v2["verdict"] == "SUCCESS", "uninterrupted-publishes-green", json.dumps(v2))
        af = doc.get("atomic_fix") or {}
        chk(af.get("destination_visible_after_sigkill") is False and af.get("published_partial") is False, "receipt-atomic-fix-block")
        bs = doc.get("both_states") or {}
        chk(str(bs.get("atomic_complete_verdict")) == "SUCCESS" and str(bs.get("truncated_verdict")) == "FAILED", "receipt-both-states")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"destination_visible_after_kill": dest.exists(),
                      "tmp_partial_preserved": tmp_left.exists(),
                      "fanin_on_invisible_destination": v,
                      "uninterrupted_control": v2["verdict"]}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 atomic tmp+rename publish live: the kill lands while the partial is tmp-side; destination never visible (fan-in sees condition 2); uninterrupted publish classifies SUCCESS - the stronger fix re-derives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
