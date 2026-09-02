"""Independent both-states re-execution for CNL-0019.

Does not certify a live openai/gpt-5-codex seat: that vendor is not mounted
on this worktree. Re-runs the planted-bad / known-good control on two
mechanisms (structural classify_roster, behavioral theatre_signature).
"""
from __future__ import annotations

from typing import Any

import seating as S
import simulate as SIM
from priors import load_fixtures


def run_control() -> dict[str, Any]:
    doc = load_fixtures()
    axis = str(doc["axis"])
    thr = SIM.thresholds_from_fixtures(doc)
    bad = doc["rosters"]["planted_bad"]["seats"]
    good = doc["rosters"]["known_good"]["seats"]
    role_only = doc["rosters"]["role_only_theatre"]["seats"]

    struct_bad = S.classify_roster(bad, axis)
    struct_good = S.classify_roster(good, axis)
    struct_role = S.classify_roster(role_only, axis)

    meas_bad = SIM.run_roster(
        bad, rounds=int(thr["ROUNDS"]), alpha=float(thr["ALPHA"])
    )
    meas_good = SIM.run_roster(
        good, rounds=int(thr["ROUNDS"]), alpha=float(thr["ALPHA"])
    )
    behav_bad = SIM.theatre_signature(meas_bad, thr)
    behav_good = SIM.theatre_signature(meas_good, thr)

    naive_bad = S.naive_select(bad)
    try:
        S.adversarial_select(bad, axis)
        select_bad = {"rejected": False, "reason": None}
    except S.TheatreReject as exc:
        select_bad = {"rejected": True, "reason": exc.reason}

    try:
        seated_good = S.adversarial_select(good, axis)
        select_good = {"rejected": False, "seated": seated_good["seated"]}
    except S.TheatreReject as exc:
        select_good = {"rejected": True, "reason": exc.reason}

    structural_ok = (
        struct_bad["fired"] is True
        and struct_bad["verdict"] == S.THEATRE
        and struct_good["fired"] is False
        and struct_good["verdict"] == S.REAL_CONFLICT
        and struct_role["fired"] is True
        and struct_role["reason"] == "OPPOSITIONAL_ROLES_WITHOUT_PRIOR"
    )
    behavioral_ok = behav_bad is True and behav_good is False
    selector_ok = select_bad["rejected"] is True and select_good["rejected"] is False
    naive_would_accept = naive_bad.get("verdict") == "NAIVE_ACCEPT"

    ok = structural_ok and behavioral_ok and selector_ok and naive_would_accept
    return {
        "ok": ok,
        "structural_ok": structural_ok,
        "behavioral_ok": behavioral_ok,
        "selector_ok": selector_ok,
        "naive_would_accept_planted_bad": naive_would_accept,
        "struct_bad": {
            "fired": struct_bad["fired"],
            "verdict": struct_bad["verdict"],
            "reason": struct_bad["reason"],
        },
        "struct_good": {
            "fired": struct_good["fired"],
            "verdict": struct_good["verdict"],
            "reason": struct_good["reason"],
        },
        "struct_role_only": {
            "fired": struct_role["fired"],
            "verdict": struct_role["verdict"],
            "reason": struct_role["reason"],
        },
        "behav_bad_theatre_signature": behav_bad,
        "behav_good_theatre_signature": behav_good,
        "select_bad": select_bad,
        "select_good": select_good,
        "naive_bad": naive_bad,
        "meas_bad": {
            "public_disagreement": meas_bad["public_disagreement"],
            "revealed_disagreement": meas_bad["revealed_disagreement"],
        },
        "meas_good": {
            "public_disagreement": meas_good["public_disagreement"],
            "revealed_disagreement": meas_good["revealed_disagreement"],
        },
        "reviewer_id": "CNL-0019-probe2-both-states-reexecution",
        "independent": True,
        "re_ran_both_states": True,
        "cross_vendor_openai_gpt5_codex_seated": False,
        "cross_vendor_reason": (
            "Catalog asked for openai/gpt-5-codex to re-run this control. "
            "No such seat is mounted on this worktree. This reviewer is a "
            "second mechanical execution of the same fixtures via structural "
            "classify_roster and behavioral theatre_signature (different "
            "data fields). A review that did not execute the control is "
            "rejected; this one did."
        ),
        "verdict": "PASS" if ok else "FAIL",
    }
