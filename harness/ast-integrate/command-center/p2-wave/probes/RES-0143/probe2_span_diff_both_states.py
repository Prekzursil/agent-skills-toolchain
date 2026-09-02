#!/usr/bin/env python3
"""Probe 2: independent span-diff + both-states mutation + fabricator control.

Does not use protocol.TEMPLATES. Required slots of a TRANSFORMABLE claim must
be contiguous source spans. Stripping the when-clause must refuse; injecting a
specified anecdote into a vague control must transform. A fabricating always-
claim protocol transforms the vague control; this protocol must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from audit import audit_transform, extra_tokens, fabricate, is_contiguous_span  # noqa: E402
from corpus import GOLD_INJECT, NEGATIVE_CONTROLS, STRIP_GOLD_TO_VAGUE  # noqa: E402
from measure import measure  # noqa: E402
from protocol import DISPOSITION_NO, DISPOSITION_OK, transform  # noqa: E402

UNIT = "RES-0143"


def main() -> int:
    m = measure()
    span_errors: list[str] = []
    n_ok = 0
    for row in m["rows"]:
        if row["live_disposition"] != DISPOSITION_OK:
            continue
        n_ok += 1
        src = row["text"]
        pre = row["precondition"] or ""
        obs = row["observable"] or ""
        if not is_contiguous_span(src, pre):
            span_errors.append(f"{row['id']}:precondition")
        if not is_contiguous_span(src, obs):
            span_errors.append(f"{row['id']}:observable")
        if extra_tokens(src, pre) or extra_tokens(src, obs):
            span_errors.append(f"{row['id']}:extra-tokens")
        aud = audit_transform(src, transform(src))
        if not aud["ok"]:
            span_errors.append(f"{row['id']}:audit:{aud['errors']}")

    gold = GOLD_INJECT
    stripped = transform(STRIP_GOLD_TO_VAGUE)
    stripped_refuses = stripped["disposition"] == DISPOSITION_NO
    injected = transform(gold)
    injected_ok = injected["disposition"] == DISPOSITION_OK
    vague = NEGATIVE_CONTROLS[0]["text"]
    honest_vague = transform(vague)
    honest_refuses_vague = honest_vague["disposition"] == DISPOSITION_NO
    fab = fabricate(vague)
    fabricator_claims_vague = fab["disposition"] == DISPOSITION_OK
    fab_audit = audit_transform(vague, fab)
    fabricator_fails_audit = not fab_audit["ok"]

    invented = transform(gold)
    if invented.get("claim"):
        invented["claim"]["precondition"] = invented["claim"]["precondition"] + " on Node-99"
        invented["precondition"] = invented["claim"]["precondition"]
    invented_audit = audit_transform(gold, invented)
    invented_caught = not invented_audit["ok"]

    both_states = stripped_refuses and injected_ok
    payload = {
        "probe": "probe2-span-diff-both-states",
        "unit_id": UNIT,
        "transformable_audited": n_ok,
        "span_errors": span_errors,
        "strip_gold_to_vague": {
            "input": STRIP_GOLD_TO_VAGUE,
            "disposition": stripped["disposition"],
            "refuses": stripped_refuses,
        },
        "inject_gold": {
            "disposition": injected["disposition"],
            "transforms": injected_ok,
        },
        "both_states": both_states,
        "fabricator": {
            "claims_vague_control": fabricator_claims_vague,
            "fails_independent_audit": fabricator_fails_audit,
            "honest_protocol_refuses_vague": honest_refuses_vague,
        },
        "invented_token_Node99_caught": invented_caught,
        "invented_audit_errors": invented_audit.get("errors"),
        "pass": False,
    }
    payload["pass"] = bool(
        n_ok >= 1
        and not span_errors
        and both_states
        and fabricator_claims_vague
        and fabricator_fails_audit
        and honest_refuses_vague
        and invented_caught
        and m["negative_controls"]["all_not_transformable"]
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:RES-0143-probe2 span-diff/both-states/fabricator")
        return 1
    print(
        "SUCCESS:RES-0143-probe2 spans are source-substrings; strip refuses; "
        "inject transforms; fabricator caught on vague control"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
