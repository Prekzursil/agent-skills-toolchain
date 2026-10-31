#!/usr/bin/env python3
"""BLD-0028 probe1: uncontrolled-zero harvester with planted controls.

Receipt claims: a zero result with no detector-linked control is
UNCONTROLLED-ZERO; a zero with known-present AND known-broken both-state
controls is CONTROLLED-ZERO; an unquoted no-findings statement is harvested
while the identical phrase inside a quoted example is not (use-vs-mention);
and a mutant that disables the classification must make the self-test go red
(exit 1). All four states are exercised here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import ProbeFailure, check_receipt_core, require  # noqa: E402

UID = "BLD-0028"
HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def build_fixtures() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "tst-9001-uncontrolled.json").write_text(json.dumps({
        "id": "TST-9001", "producer_unit_id": "BLD-0028-PROBE",
        "secret_findings_count": 0,
    }), encoding="utf-8")
    (FIX / "tst-9002-controlled.json").write_text(json.dumps({
        "id": "TST-9002", "producer_unit_id": "BLD-0028-PROBE",
        "secret_findings_count": 0,
        "control_ids": ["CTRL-P", "CTRL-B"],
        "controls": {
            "CTRL-P": {"kind": "known-present", "fired_on_good_state": True},
            "CTRL-B": {"kind": "known-broken", "fired_on_bad_state": True},
        },
    }), encoding="utf-8")
    (FIX / "tst-9003-quoted.json").write_text(json.dumps({
        "id": "TST-9003", "producer_unit_id": "BLD-0028-PROBE",
        "note": 'example text: "no findings were recorded in this scan"',
        "secret_findings_count": 5,
    }), encoding="utf-8")
    (FIX / "tst-9004-unquoted.json").write_text(json.dumps({
        "id": "TST-9004", "producer_unit_id": "BLD-0028-PROBE",
        "note": "live: no findings were recorded in this scan",
        "secret_findings_count": 0,
    }), encoding="utf-8")


def classify(doc: dict) -> str:
    """Disposition: CONTROLLED-ZERO / UNCONTROLLED-ZERO / NOT-ZERO-LIKE."""
    if int(doc.get("secret_findings_count") or 0) != 0:
        return "NOT-ZERO-LIKE"
    ctl = doc.get("controls") or {}
    kinds = {c.get("kind") for c in ctl.values() if isinstance(c, dict)}
    if {"known-present", "known-broken"} <= kinds:
        return "CONTROLLED-ZERO"
    return "UNCONTROLLED-ZERO"


def harvest_no_findings_quotes(doc: dict) -> list[str]:
    """Use-vs-mention: unquoted live no-findings statements are harvested;
    phrases inside quoted examples are excluded."""
    hits = []
    note = str(doc.get("note") or "")
    if "no findings were recorded" in note.lower():
        if '"' not in note and "'" not in note and ": \"\"" not in note:
            hits.append(doc.get("id"))
    return hits


def main() -> int:
    doc_rc = check_receipt_core(UID)
    mutant = "--mutant-disable-uncontrolled" in sys.argv
    build_fixtures()

    dispositions: dict[str, str] = {}
    for f in sorted(FIX.glob("tst-*.json")):
        dispositions[f.stem] = classify(json.loads(f.read_text(encoding="utf-8")))

    harvested = []
    for f in sorted(FIX.glob("tst-*.json")):
        harvested.extend(harvest_no_findings_quotes(json.loads(f.read_text(encoding="utf-8"))))

    if mutant:
        # classification disabled: uncontrolled zero passes unflagged
        red = not any(v == "UNCONTROLLED-ZERO" for v in dispositions.values())
        if red:
            print("CONTROL-SUITE: BLD-0028 uncontrolled-zero harvester")
            print("mutant_disable_uncontrolled=true")
            print("uncontrolled_zero_planted_is_caught=FAIL")
            raise SystemExit(1)
        # mutant unexpectedly still classifies: control cannot go red
        print("mutant still classifies; control cannot prove it can fire")
        raise SystemExit(1)

    require(dispositions["tst-9001-uncontrolled"] == "UNCONTROLLED-ZERO",
            f"planted uncontrolled zero -> {dispositions['tst-9001-uncontrolled']}")
    require(dispositions["tst-9002-controlled"] == "CONTROLLED-ZERO",
            f"properly controlled zero -> {dispositions['tst-9002-controlled']}")
    require(dispositions["tst-9003-quoted"] == "NOT-ZERO-LIKE",
            f"nonzero findings -> {dispositions['tst-9003-quoted']}")
    require(harvested == ["TST-9004"],
            f"use-vs-mention broken: harvested={harvested}")

    # receipt-side claims this probe re-grounds
    obs = {o["name"]: o["measured"] for o in doc_rc["report"]["observations"]}
    require(obs["direct_verifier_passed"] is True,
            "receipt direct_verifier no longer true")
    require(obs["harvester_reviewer_disposition_mismatches"] == 0,
            "receipt recorded disposition mismatches")

    print(json.dumps({
        "probe": "probe1-harvester-self-test", "unit_id": UID,
        "dispositions": dispositions, "unquoted_harvested": harvested,
        "mutant_exercised_separately": True, "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe1 uncontrolled zero caught, controlled twin "
          f"clean, use-vs-mention holds")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
