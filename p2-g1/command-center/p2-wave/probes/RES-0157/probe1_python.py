#!/usr/bin/env python3
"""RES-0157 probe1_python.

Re-verifies the durability/transaction-model artifact from its own embedded
data: five side-effect classes, exactly one NON-COMPENSABLE (human
notification), every compensable class carries a named compensation, the
all-compensable negative control went red, schema class is gem-candidate.
Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/gem-hunt/RES-0157-transfer-durability-transaction-models.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:260]})
        return bool(ok)

    sec = doc.get("side_effect_classes") or []
    ck("five-side-effect-classes", len(sec) == 5, f"n={len(sec)}")
    noncomp = [c.get("class_id") or c.get("id") for c in sec if c.get("compensable") is False]
    ck("exactly-one-non-compensable", len(noncomp) == 1, f"noncomp={noncomp}")
    ck("notification-is-non-compensable", noncomp == ["human_notification"], str(noncomp))
    comp = [c for c in sec if c.get("compensable") is True]
    ck("compensables-have-compensation-action",
       all(str(c.get("compensation_or_noncompensable") or "").strip() for c in comp),
       str([len(str(c.get("compensation_or_noncompensable") or "")) for c in comp]))
    ck("every-class-names-real-action",
       all(str(c.get("real_program_action") or "").strip() and c.get("program_anchor") for c in sec),
       str([c.get("id") for c in sec]))

    nc = doc.get("negative_controls") or []
    nc0 = nc[0] if nc else {}
    bad = str(nc0.get("bad_state_output") or "")
    ck("all-compensable-mutant-went-red",
       nc0.get("fired_on_bad_state") is True and "DETECTOR_RESULT=RED" in bad
       and "notification-must-be-the-only-non-compensable-class" in bad,
       bad[-160:])

    claims = doc.get("claims") or []
    ck("claims-nonempty", len(claims) >= 1, f"n={len(claims)}")
    rep = doc.get("report") or {}
    ck("report-kind-gem-candidate", rep.get("kind") == "gem-candidate", str(rep.get("kind")))
    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0157" in txt, f"state={doc.get('state')}")
    # reviewer closure present in artifact (C5 wave) - presence checked, binding judged by receipt
    rev = doc.get("reviewer") or {}
    ck("reviewer-block-present",
       rev.get("verdict") == "PASS" and rev.get("independent") is True,
       str(rev.get("reviewer_id"))[:80])

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-python", "unit_id": "RES-0157", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0157-probe1 five classes, one non-compensable, control red" if not red
          else f"FAILED:RES-0157-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
