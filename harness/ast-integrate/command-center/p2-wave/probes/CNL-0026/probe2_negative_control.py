#!/usr/bin/env python3
"""Probe 2: negative control + independent both-states re-run (reviewer).

The check is meant to reject fused relabelling (judge writes the verdict).
This probe re-executes both states itself. A review that only read the
artifact's stored control is rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import separation as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0026-judge-and-juror-separation-to-remove-the-single-epistemic-.md"
)
SCHEMA = HERE / "note.schema.json"
FIX = HERE / "fixtures" / "fused-relabel-corrupted-judge.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0026-probe2 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)

    mutant = copy.deepcopy(doc)
    mutant["corruption_threshold"]["computed_not_asserted"] = False
    try:
        jsonschema.Draft202012Validator(schema).validate(mutant)
    except jsonschema.ValidationError:
        mutant_rejected = True
    else:
        mutant_rejected = False
    print(f"mutant_computed_flag_rejected={mutant_rejected}")
    if not mutant_rejected:
        print("FAILED:CNL-0026-probe2 schema accepted computed_not_asserted=false")
        return 1

    both = S.both_states_control()
    print(S.verbatim_line(both["separated"]))
    print(S.verbatim_line(both["fused"]))
    if not both["pass"]:
        print("FAILED:CNL-0026-probe2 both-states did not pass", both)
        return 1
    if both["separated"]["fires"]:
        print("FAILED:CNL-0026-probe2 check fired on separated (false positive)")
        return 1
    if not both["fused"]["fires"]:
        print("FAILED:CNL-0026-probe2 check silent on fused (false negative)")
        return 1

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    fused_pub = S.publish_fused(list(fx["juror_ballots"]), fx["judge_value"])
    if fused_pub["outcome"] != S.REJECT:
        print("FAILED:CNL-0026-probe2 fused fixture did not follow the judge", fused_pub)
        return 1
    if fused_pub["dissent_preserved"] is True:
        print("FAILED:CNL-0026-probe2 fused fixture preserved dissent")
        return 1

    stored = doc.get("live", {}).get("both_states") or {}
    if stored.get("silent_on_separated") is not True or stored.get("fires_on_fused") is not True:
        print("FAILED:CNL-0026-probe2 artifact both-states drift", stored)
        return 1
    if doc.get("live", {}).get("verbatim_fused") != S.verbatim_line(both["fused"]):
        print("FAILED:CNL-0026-probe2 verbatim fused drift")
        return 1
    if doc.get("live", {}).get("verbatim_separated") != S.verbatim_line(both["separated"]):
        print("FAILED:CNL-0026-probe2 verbatim separated drift")
        return 1

    neg = doc.get("negative_control") or {}
    want = S.live_measurement()["negative_control_verbatim"]
    if neg.get("verbatim") != want:
        print("FAILED:CNL-0026-probe2 negative control verbatim drift")
        print("want", want)
        print("got", neg.get("verbatim"))
        return 1
    print(neg["verbatim"])

    review = doc.get("reviewer") or {}
    if review.get("executed_both_states") is not True:
        print("FAILED:CNL-0026-probe2 reviewer did not execute the control")
        return 1
    if review.get("independent") is not True:
        print("FAILED:CNL-0026-probe2 reviewer not independent")
        return 1

    evidence = doc.get("evidence") or []
    if len(evidence) < 3:
        print("FAILED:CNL-0026-probe2 evidence too thin")
        return 1
    for i, row in enumerate(evidence):
        rok, rwhy = A.resolve_anchor(
            REPO, str(row.get("path") or ""), int(row.get("line") or 0), str(row.get("snippet") or "")
        )
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:CNL-0026-probe2 unresolved anchor")
            return 1

    spec = doc.get("spec_anchor") or {}
    if "11342" not in str(spec.get("required_path") or ""):
        print("FAILED:CNL-0026-probe2 spec 11342 not cited")
        return 1
    if spec.get("present_on_this_estate") is True:
        print("FAILED:CNL-0026-probe2 claimed missing spec file is present")
        return 1

    hung = S.hung_control()
    print(
        f"hung separated={hung['separated_outcome']} fused={hung['fused_outcome']} "
        f"pass={hung['pass']}"
    )
    if not hung["pass"]:
        print("FAILED:CNL-0026-probe2 hung control")
        return 1

    print(
        "both_states silent_on_separated="
        f"{both['silent_on_separated']} fires_on_fused={both['fires_on_fused']}"
    )
    print("SUCCESS:CNL-0026-probe2 negative control and both-states re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
