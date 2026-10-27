#!/usr/bin/env python3
"""TST-0081 probe2: live both-states gate battery (this box).

Mechanically different from probe1's census: runs the estate gate
module's own four both-states tests (clean package passes; planted .git
fails; oversize payload fails above a small ceiling; transcript/log and
credential-shaped names fail with the body never printed), plus the
rule-mutation control that makes the planted .git zip pass, proving the
detector is not vacuous."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import package_hygiene as ph  # noqa: E402

UNIT = "TST-0081"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0081" in OUT.read_text(encoding="utf-8"), "sentinel-absent")

    clean = ph.test_clean_package_passes()
    chk(clean["pass"] is True and clean["gate_ok"] is True, "clean-package-must-pass", json.dumps(clean)[:200])
    planted = ph.test_gate_fails_on_a_planted_dot_git()
    chk(planted["pass"] is True, "planted-git-must-fail", json.dumps(planted)[:200])
    chk(planted.get("mutant_disabled_git_rule_ok") is True, "rule-mutation-control-not-vacuous")
    size = ph.test_gate_fails_above_the_size_budget()
    chk(size["pass"] is True and size["clean_under_budget_ok"] is True, "oversize-must-fail-under-must-pass", json.dumps(size)[:200])
    cred = ph.test_gate_fails_on_transcript_log_and_credential_names()
    chk(cred["pass"] is True, "transcript-log-credential-names-must-fail", json.dumps(cred)[:200])
    chk(cred.get("credential_body_absent_from_report") is True, "credential-body-never-printed")
    tests = doc.get("tests") or []
    chk(len(tests) >= 3, "tests-rows-recorded", str(len(tests)))
    nc = {c.get("id") for c in doc.get("negative_controls") or []}
    chk({"TST-0081-C1-archive-not-tree", "TST-0081-C2-git-rule-mutation"} <= nc, "controls-recorded", json.dumps(sorted(nc)))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"clean": clean["pass"], "planted_git_red": planted["pass"],
                      "mutation_control_green": planted.get("mutant_disabled_git_rule_ok"),
                      "oversize_red_under_green": size["pass"],
                      "transcript_log_credential_red": cred["pass"],
                      "credential_body_absent": cred.get("credential_body_absent_from_report")}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 live gate battery: clean green, planted .git red, oversize red/under green, transcript+log+credential names red with body never printed, rule-mutation control proves the detector not vacuous")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
