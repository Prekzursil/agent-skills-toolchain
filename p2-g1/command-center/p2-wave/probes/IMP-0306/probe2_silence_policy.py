#!/usr/bin/env python3
"""Named probe 2: unrecorded silence policy must FAIL; late-objection fixture.

Independent of the author's summary. Both states of the negative control run
in this process. Constructor AST is checked so silence_policy has no default.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote.consent import (  # noqa: E402
    ArtifactValidationError,
    ConsentSession,
    LATE_RECORD_AND_IGNORE,
    MODE_CONSENT,
    RESP_CONSENT,
    SILENCE_IS_CONSENT,
    decision_from_events,
    strip_silence_policy,
    validate_artifact,
)

ART = REPO / "command-center" / "receipts" / "IMP-0306.json"
SRC = REPO / "tools" / "council" / "vote" / "consent.py"
FIXTURE = HERE / "fixtures" / "late_objection.json"
WINDOW = {"opens_at": 1000.0, "closes_at": 2000.0, "timezone": "UTC"}
SEATS = [
    {"id": "alice", "veto_right": True},
    {"id": "bob", "veto_right": False},
    {"id": "cara", "veto_right": False},
]


def silence_policy_has_no_default(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "__init__":
            continue
        pos = list(node.args.args)
        n_pos_defaults = len(node.args.defaults)
        if n_pos_defaults:
            for arg, _default in zip(pos[-n_pos_defaults:], node.args.defaults):
                if arg.arg == "silence_policy":
                    return False
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if arg.arg != "silence_policy":
                continue
            if default is None:
                return True
            return False
        names = [a.arg for a in pos] + [a.arg for a in node.args.kwonlyargs]
        return "silence_policy" in names
    return False


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0306-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0306-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0306-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0306" not in text:
        print("FAILED:IMP-0306-probe2 sentinel absent")
        return 1

    source = SRC.read_text(encoding="utf-8")
    if not silence_policy_has_no_default(source):
        print("FAILED:IMP-0306-probe2 silence_policy has a constructor default")
        return 1
    if "silence_policy or SILENCE" in source or "silence_policy or '" in source:
        print("FAILED:IMP-0306-probe2 inferred silence_policy default in source")
        return 1

    good = decision_from_events(
        proposal_id="probe2-good",
        mode=MODE_CONSENT,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=WINDOW,
        participants=SEATS,
        events=[
            {
                "participant_id": "alice",
                "kind": RESP_CONSENT,
                "at": 1100,
                "reason": "explicit",
            }
        ],
        close_at=2000,
        proposal="negative-control good state",
    )
    good_errs = validate_artifact(good)
    if good_errs:
        print(f"FAILED:IMP-0306-probe2 valid artifact rejected {good_errs}")
        return 1

    mutant = strip_silence_policy(good)
    bad_errs = validate_artifact(mutant)
    if not any("unrecorded" in e for e in bad_errs):
        print(f"FAILED:IMP-0306-probe2 unrecorded policy accepted {bad_errs}")
        return 1

    ctor_fired = False
    try:
        ConsentSession(
            proposal_id="probe2-ctor",
            mode=MODE_CONSENT,
            silence_policy="",
            late_objection_policy=LATE_RECORD_AND_IGNORE,
            objection_window=WINDOW,
            participants=SEATS,
        )
    except ArtifactValidationError:
        ctor_fired = True
    if not ctor_fired:
        print("FAILED:IMP-0306-probe2 empty silence_policy constructed")
        return 1

    if not FIXTURE.is_file():
        print("FAILED:IMP-0306-probe2 late_objection.json missing")
        return 1
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = ConsentSession(
        proposal_id=str(fixture["proposal_id"]),
        mode=MODE_CONSENT,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=fixture["objection_window"],
        participants=fixture["participants"],
        proposal=str(fixture.get("proposal") or ""),
    )
    for event in fixture["pre_close_events"]:
        live.respond(
            event["participant_id"], event["kind"], event["at"], event.get("reason")
        )
    closed = live.close(float(fixture["close_at"]))
    late_event = fixture["late_event"]
    late_rec = live.respond(
        late_event["participant_id"],
        late_event["kind"],
        late_event["at"],
        late_event.get("reason"),
    )
    after = live.to_artifact()
    expected = fixture["expected"]
    if after["outcome"] != expected["outcome_after_late"]:
        print(
            "FAILED:IMP-0306-probe2 late fixture outcome "
            f"{after['outcome']} != {expected['outcome_after_late']}"
        )
        return 1
    if bool(late_rec.get("admitted")) != bool(expected["late_admitted"]):
        print(f"FAILED:IMP-0306-probe2 late admitted {late_rec.get('admitted')}")
        return 1
    if closed["outcome"] != expected["outcome_at_close"]:
        print(f"FAILED:IMP-0306-probe2 close outcome {closed['outcome']}")
        return 1

    if "silence_policy" not in text:
        print("FAILED:IMP-0306-probe2 receipt never names silence_policy")
        return 1

    payload = {
        "ast_no_default": True,
        "ctor_empty_policy_fired": ctor_fired,
        "late_admitted": late_rec.get("admitted"),
        "late_fixture_outcome": after["outcome"],
        "mutant_errors": bad_errs,
        "pass": True,
        "probe": "probe2-silence-policy",
        "unit_id": "IMP-0306",
        "valid_artifact_errors": good_errs,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "unrecorded_policy_fails=True valid_artifact_passes=True "
        "late_objection_ignored=True ast_no_default=True"
    )
    print("SUCCESS:IMP-0306-probe2 unrecorded silence policy fails artifact validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
