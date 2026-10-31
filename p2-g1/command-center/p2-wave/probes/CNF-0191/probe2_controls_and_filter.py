#!/usr/bin/env python3
"""CNF-0191 named probe 2 (wave-2 reconstruction): refusal filter + controls.

  FILTER CONSISTENCY  the reconstructed refusal classifier re-applied to all
                      53 live commands must agree with the receipt's recorded
                      classification: every recorded NOT-CHECKED row carries
                      the same refusal_rule, every executed row classifies
                      execution-eligible;
  REFUSE-BEFORE-EXEC  the filter runs on the command string only — the
                      recorded refused rows all have subprocess_attempted=false;
  TALLY               pass 5 + fail 24 + not_checked 24 == 53;
  MENTION/DIR-TREE    prose mentions and empty-lang fences are not commands;
  LIVE SAFE EXEC      an actually-safe documented command runs clean (the
                      both-states good arm), executed for real here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "CNF-0191.json"

from extract import extract_commands  # noqa: E402
from refuse import classify  # noqa: E402


def main():
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0191" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0191-probe2 sentinel absent")
        return 1
    recorded = doc.get("commands") or []

    disagree = []
    for c in recorded:
        live_rule = classify(c["command"])
        rec_rule = c.get("refusal_rule")
        if (live_rule or None) != (rec_rule or None):
            disagree.append({
                "command": c["command"][:80],
                "recorded": rec_rule,
                "live": live_rule,
            })
    if disagree:
        print("FAILED:CNF-0191-probe2 classifier disagreement " + json.dumps(disagree[:3]))
        return 1

    not_checked = [c for c in recorded if c.get("outcome") == "NOT-CHECKED"]
    executed = [c for c in recorded if c.get("outcome") != "NOT-CHECKED"]
    if len(not_checked) != 24 or len(executed) != 29:
        print("FAILED:CNF-0191-probe2 recorded outcome split drifted: NC=" + str(len(not_checked)) + " exec=" + str(len(executed)))
        return 1
    if any(c.get("subprocess_attempted") for c in not_checked):
        print("FAILED:CNF-0191-probe2 a refused row claims a subprocess attempt (filter not before exec)")
        return 1

    ans = doc.get("answer") or {}
    if (ans.get("live_pass"), ans.get("live_fail"), ans.get("live_not_checked")) != (5, 24, 24):
        print("FAILED:CNF-0191-probe2 tally inconsistent")
        return 1

    fixture_rows = extract_commands(
        (HERE / "fixtures" / "hand-counted.md").read_text(encoding="utf-8"), "fixture"
    )
    if len(fixture_rows) != 5 or any("mentioned" in r["command"] for r in fixture_rows) or any(
        r["command"].strip().startswith("docs/") for r in fixture_rows
    ):
        print("FAILED:CNF-0191-probe2 fixture controls failed")
        return 1

    # LIVE SAFE EXEC (good arm): a genuinely safe command actually runs here
    p = subprocess.run([sys.executable, "-c", "print('cnf0191-safe-exec-ok')"], capture_output=True, text=True)
    if p.returncode != 0 or "cnf0191-safe-exec-ok" not in (p.stdout or ""):
        print("FAILED:CNF-0191-probe2 safe execution arm failed")
        return 1
    if classify("echo harmless") is not None or classify("git clone x") is None:
        print("FAILED:CNF-0191-probe2 classifier both-states failed")
        return 1

    report = {
        "probe": "probe2-filter-and-controls",
        "unit_id": "CNF-0191",
        "classifier_rows_checked": len(recorded),
        "classifier_disagreements": 0,
        "not_checked_rows": len(not_checked),
        "executed_rows": len(executed),
        "refused_before_exec_structural": True,
        "recorded_tally": [ans.get("live_pass"), ans.get("live_fail"), ans.get("live_not_checked")],
        "fixture_controls": {"hand_count": len(fixture_rows), "mention_excluded": True, "dir_tree_excluded": True},
        "live_safe_exec_stdout": (p.stdout or "").strip(),
        "classifier_both_states": {"harmless_eligible": True, "git_clone_refused": True},
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0191-probe2 refusal filter consistency and controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
