#!/usr/bin/env python3
"""Probe 1: both-direction discriminator + both-states + shrinking-PV control.

Uses the live semantics engine. Exit 0 only if:
  * principled fixture classifies PRINCIPLED and does not fire
  * strategic fixture classifies STRATEGIC and fires
  * PV-basis protocol fires; seated-basis protocol is silent
  * negative non-pivotal generic does not fire
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import semantics as S  # noqa: E402


def run_one(doc: dict) -> dict:
    got = S.resolve(doc["question"], doc["seats"], doc["ballots"])
    abstain = [r for r in got["rows"] if r.get("kind") == "ABSTAIN"]
    cls = abstain[0]["class"] if abstain else None
    return {
        "id": doc["id"],
        "class": cls,
        "strategic_fire": got["strategic_fire"],
        "decision": got["decision"],
        "yes": got["yes"],
        "protocol_fired": got["protocol"]["fired"],
        "protocol_silent": got["protocol"]["silent"],
        "shrinking_trap": got["shrinking_trap"],
        "expect": doc["expect"],
    }


def check(row: dict) -> list[str]:
    exp = row["expect"]
    errs: list[str] = []
    if row["class"] != exp["class"]:
        errs.append(f"class {row['class']} != {exp['class']}")
    if row["strategic_fire"] != exp["strategic_fire"]:
        errs.append(
            f"strategic_fire {row['strategic_fire']} != {exp['strategic_fire']}"
        )
    if row["decision"] != exp["decision"]:
        errs.append(f"decision {row['decision']} != {exp['decision']}")
    if row["yes"] != exp["yes"]:
        errs.append(f"yes {row['yes']} != {exp['yes']}")
    if row["protocol_fired"] != exp["protocol_fired"]:
        errs.append(
            f"protocol_fired {row['protocol_fired']} != {exp['protocol_fired']}"
        )
    return errs


def main() -> int:
    F.dump_fixtures()
    names = [
        "known-good-principled",
        "planted-bad-strategic",
        "planted-bad-present-and-voting",
        "known-good-protocol-seated-basis",
        "negative-nonpivotal-generic",
    ]
    fx = F.all_fixtures()
    rows = [run_one(fx[n]) for n in names]
    all_errs: list[str] = []
    for row in rows:
        errs = check(row)
        status = "OK" if not errs else "FAIL:" + ";".join(errs)
        print(
            f"{row['id']} class={row['class']} fire={row['strategic_fire']} "
            f"decision={row['decision']} proto_fired={row['protocol_fired']} {status}"
        )
        all_errs.extend(f"{row['id']}:{e}" for e in errs)

    good = next(r for r in rows if r["id"] == "known-good-principled")
    bad = next(r for r in rows if r["id"] == "planted-bad-strategic")
    pv = next(r for r in rows if r["id"] == "planted-bad-present-and-voting")
    seated = next(r for r in rows if r["id"] == "known-good-protocol-seated-basis")
    neg = next(r for r in rows if r["id"] == "negative-nonpivotal-generic")

    # Both directions on the discriminator.
    if good["class"] != "PRINCIPLED" or good["strategic_fire"]:
        all_errs.append("direction-principled-failed")
    if bad["class"] != "STRATEGIC" or not bad["strategic_fire"]:
        all_errs.append("direction-strategic-failed")

    # Both-states: FIRES on planted-bad, SILENT on known-good.
    if not bad["strategic_fire"]:
        all_errs.append("both-states-strategic-did-not-fire")
    if good["strategic_fire"]:
        all_errs.append("both-states-principled-was-not-silent")
    if not pv["protocol_fired"]:
        all_errs.append("both-states-pv-protocol-did-not-fire")
    if seated["protocol_fired"]:
        all_errs.append("both-states-seated-protocol-was-not-silent")

    # Negative control: non-pivotal generic must not fire (state the check rejects).
    if neg["strategic_fire"] or neg["class"] != "UNDETERMINED":
        all_errs.append("negative-nonpivotal-misfire")

    trap = bad["shrinking_trap"]
    print(
        "shrinking_trap pv_yes={present_and_voting_yes} pv_den={present_and_voting_den} "
        "pv_two_thirds={present_and_voting_meets_two_thirds} seated_meets={seated_meets_threshold_yes}".format(
            **trap
        )
    )
    print(
        "both_states discriminator planted-bad=FIRE known-good=SILENT "
        f"got_bad={bad['strategic_fire']} got_good={good['strategic_fire']}"
    )
    print(
        "both_states protocol pv=FIRE seated=SILENT "
        f"got_pv={pv['protocol_fired']} got_seated={seated['protocol_fired']}"
    )
    print(
        "negative_control nonpivotal-generic: check SILENT "
        f"(class={neg['class']} fire={neg['strategic_fire']} decision={neg['decision']})"
    )

    out = HERE / "probe1-discriminator.raw.json"
    out.write_text(json.dumps({"rows": rows, "errors": all_errs}, indent=2) + "\n")
    if all_errs:
        print("FAILED:CNL-0066-probe1 " + " | ".join(all_errs))
        return 1
    print("SUCCESS:CNL-0066-probe1 discriminator both-states shrinking-PV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
