#!/usr/bin/env python3
"""Probe 1: instantiate the flagship against fixture tasks.

Records roster, protocol schedule, voting method and stopping expression.
Checks explanation completeness, one-step override, legal false-positive,
and non-editable dial rejection.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import composer as C  # noqa: E402

ARTIFACT = (
    REPO
    / "command-center/design/council/CNL-0116-general-purpose-auto-composed-council-preset-the-flagship.md"
)
TASKS = HERE / "fixtures" / "tasks.json"


def main() -> int:
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    fail = False

    canonical = next(t for t in tasks if t["id"] == "T-PROD-GNG")
    inst = C.compose(canonical["text"])
    fp = C.fingerprint(inst)
    recorded = doc["worked_example"]["fingerprint"]
    print(
        json.dumps(
            {
                "task_id": canonical["id"],
                "roster": inst["roles"],
                "protocol_schedule": inst["protocol_schedule"],
                "voting_method": inst["voting"],
                "stopping_expression": inst["stopping"]["expression"],
                "stopping": inst["stopping"],
                "risk_tier": inst["charter"]["risk_tier"],
                "explanation_count": len(inst["explanation"]),
                "override_path": inst["one_step_override_path"],
            },
            sort_keys=True,
        )
    )
    if fp != recorded:
        print(f"FAILED:CNL-0116-probe1 fingerprint drift {fp} != {recorded}")
        fail = True
    if inst["charter"]["risk_tier"] != canonical["expect_risk"]:
        print(f"FAILED:CNL-0116-probe1 risk {inst['charter']['risk_tier']}")
        fail = True
    if "Operator" not in inst["roles"]:
        print("FAILED:CNL-0116-probe1 expected Operator on production go/no-go")
        fail = True
    if "Legal" in inst["roles"]:
        print("FAILED:CNL-0116-probe1 Legal false-positive on T-PROD-GNG")
        fail = True
    missing = C.check_integrity(inst)
    if missing:
        print(f"FAILED:CNL-0116-probe1 integrity {missing}")
        fail = True
    # every non-default voting/schedule/stop dial has a reason
    by = {e["dial"]: e for e in inst["explanation"]}
    for dial in ("charter.risk_tier", "voting.rule", "stopping.expression"):
        if not str(by.get(dial, {}).get("reason") or "").strip():
            print(f"FAILED:CNL-0116-probe1 missing reason {dial}")
            fail = True

    # one-step override: lock voting.rule, record before/after
    over = C.compose(canonical["text"], override={"voting.rule": "majority"})
    if over["voting"]["rule"] != "majority":
        print("FAILED:CNL-0116-probe1 override did not apply")
        fail = True
    if not over["overrides"] or over["overrides"][0]["dial"] != "voting.rule":
        print("FAILED:CNL-0116-probe1 override not recorded")
        fail = True
    if over["overrides"][0].get("recorded") is not True:
        print("FAILED:CNL-0116-probe1 override recorded flag")
        fail = True
    if over["protocol_schedule"] != inst["protocol_schedule"]:
        print("FAILED:CNL-0116-probe1 override leaked into unlocked schedule")
        fail = True
    print(
        f"override voting.rule majority recorded={over['overrides'][0]['recorded']} "
        f"path={over['one_step_override_path']}"
    )

    # named-preset exit
    named = C.compose(canonical["text"], named_preset="C-M01")
    if named.get("flagship_used") is not False or named.get("path") != "named-preset":
        print(f"FAILED:CNL-0116-probe1 named preset path {named}")
        fail = True

    # non-editable dial
    try:
        C.compose(canonical["text"], override={"default_binding": "static"})
        print("FAILED:CNL-0116-probe1 non-editable dial was accepted")
        fail = True
    except C.ComposerError as exc:
        print(f"non-editable rejected: {exc}")

    # legal both-states
    legal = C.compose(next(t for t in tasks if t["id"] == "T-LEGAL")["text"])
    csv = C.compose(next(t for t in tasks if t["id"] == "T-CSV")["text"])
    if "Legal" not in legal["roles"]:
        print("FAILED:CNL-0116-probe1 T-LEGAL missing Legal")
        fail = True
    if "Legal" in csv["roles"]:
        print("FAILED:CNL-0116-probe1 T-CSV seated Legal (false positive)")
        fail = True
    print(
        f"legal_true_positive={('Legal' in legal['roles'])} "
        f"legal_false_positive={('Legal' in csv['roles'])} "
        f"csv_risk={csv['charter']['risk_tier']}"
    )

    # silent unrecorded override must fail integrity
    mutant = deepcopy(inst)
    mutant["voting"] = dict(mutant["voting"])
    mutant["voting"]["rule"] = "majority"
    mutant["overrides"] = [{"dial": "voting.rule", "value": "majority", "recorded": False}]
    fired = C.check_integrity(mutant)
    silent_ok = any(e == "unrecorded-override" for e in fired)
    clean = C.check_integrity(inst)
    print(f"silent_override_fired={silent_ok} clean_integrity={clean}")
    if not silent_ok or clean:
        print("FAILED:CNL-0116-probe1 silent-override both-states")
        fail = True

    if fail:
        print("FAILED:CNL-0116-probe1 instantiate")
        return 1
    print("SUCCESS:CNL-0116-probe1 instantiate fixture task, explanations, one-step override")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
