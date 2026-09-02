#!/usr/bin/env python3
"""Probe 2: both-states control + independent recount.

Check: abuse detector on pretext_veto_count.
  FIRES on planted-bad serial-vetoer fixture
  SILENT on known-good principled-dissenter fixture

Signal 2 (this probe): recount_pretext recomputes cited_invariant membership
in object.violations and does not read the engine pretext/abuse bits.

Negative control recorded verbatim: what the check does on the state it is
meant to reject (the serial fixture).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import veto as V  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0024-veto-rights-scope-override-path-and-abuse-detection.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0024-probe2 {msg}")
    return 1


def main() -> int:
    good_fx = V.load_fixture("good_principled.json")
    bad_fx = V.load_fixture("bad_serial.json")
    unused_fx = V.load_fixture("unused_right.json")
    scope_fx = V.load_fixture("council_scope.json")
    unauth_fx = V.load_fixture("unauthorized.json")

    good = V.run_fixture(good_fx)
    bad = V.run_fixture(bad_fx)
    unused = V.run_fixture(unused_fx)
    scope = V.run_fixture(scope_fx)
    unauth = V.run_fixture(unauth_fx)

    g_seat = V.target_seat(good_fx)
    b_seat = V.target_seat(bad_fx)
    rec_g = good["recounts"][g_seat]
    rec_b = bad["recounts"][b_seat]
    rec_u = unused["recounts"][V.target_seat(unused_fx)]
    rec_s = scope["recounts"][V.target_seat(scope_fx)]
    rec_a = unauth["recounts"][V.target_seat(unauth_fx)]

    # Cross-check: recount must agree with engine, but was not computed from it.
    eng_g = good["classifications"][g_seat]
    eng_b = bad["classifications"][b_seat]
    if rec_g["pretext_veto_count"] != eng_g["pretext_veto_count"]:
        return fail("recount/engine pretext mismatch on principled")
    if rec_b["pretext_veto_count"] != eng_b["pretext_veto_count"]:
        return fail("recount/engine pretext mismatch on serial")
    if rec_g["signal"] == eng_g["signal"]:
        return fail("signals are not mechanically distinct (same signal label)")

    fired_on_bad = rec_b["abuse"] is True
    silent_on_good = rec_g["abuse"] is False
    print("NEGATIVE_CONTROL_CHECK=abuse_detector(pretext_veto_count>=2)")
    print(
        "REJECT_STATE=serial-vetoer cites preserve-minority-report on five "
        "objects that do not carry dropped-minority-report"
    )
    verbatim_bad = (
        f"fired={rec_b['abuse']} pretext_veto_count={rec_b['pretext_veto_count']} "
        f"accepted={rec_b['accepted']} matched={rec_b['matched_veto_count']} "
        f"signal={rec_b['signal']}"
    )
    verbatim_good = (
        f"fired={rec_g['abuse']} pretext_veto_count={rec_g['pretext_veto_count']} "
        f"accepted={rec_g['accepted']} matched={rec_g['matched_veto_count']} "
        f"signal={rec_g['signal']}"
    )
    print(f"verbatim_bad {verbatim_bad}")
    print(f"verbatim_good {verbatim_good}")
    print(f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}")
    print(
        f"verbatim_unused fired={rec_u['abuse']} accepted={rec_u['accepted']}"
    )
    print(
        "verbatim_council_scope "
        f"status={scope['log'][0]['status']} abuse={rec_s['abuse']}"
    )
    print(
        "verbatim_unauthorized "
        f"status={unauth['log'][0]['status']} abuse={rec_a['abuse']}"
    )

    if not fired_on_bad:
        return fail("check did not FIRE on planted-bad serial fixture")
    if not silent_on_good:
        return fail("check was not SILENT on known-good principled fixture")
    if rec_u["abuse"] is not False:
        return fail("unused right must be silent")
    if rec_s["abuse"] is not False:
        return fail("invalid_scope must not count as abuse")
    if rec_a["abuse"] is not False:
        return fail("unauthorized must not count as abuse")
    if rec_g["accepted"] != rec_b["accepted"]:
        return fail("both-states fixtures must share accepted veto count")

    # Independent of engine pretext bits: recompute membership here inline.
    inline_pretext = 0
    for row in bad["log"]:
        if row.get("status") not in {"applied", "overridden"}:
            continue
        obj = bad["objects"][row["object_id"]]
        token = V.INVARIANT_VIOLATION.get(row["cited_invariant"])
        if token not in list(obj.get("violations") or []):
            inline_pretext += 1
    print(f"inline_membership_pretext_serial={inline_pretext}")
    if inline_pretext != rec_b["pretext_veto_count"]:
        return fail("inline membership recount disagrees with recount_pretext")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        ncs = doc.get("negative_controls") or []
        if not ncs:
            return fail("artifact missing negative_controls")
        nc0 = ncs[0] if isinstance(ncs[0], dict) else {}
        if nc0.get("fired_on_bad_state") is not True:
            return fail("artifact did not record fire-on-bad")
        if nc0.get("silent_on_good_state") is not True:
            return fail("artifact did not record silent-on-good")
        bs = doc.get("both_states") or {}
        if bs.get("fired_on_planted_bad") is not True:
            return fail("artifact.both_states missing fire-on-bad")
        if bs.get("silent_on_known_good") is not True:
            return fail("artifact.both_states missing silent-on-good")
        det = doc.get("detector") or {}
        if det.get("pair_and_gate_rejected") is not True:
            return fail("artifact.detector.pair_and_gate_rejected is not true")
        if len(det.get("signals") or []) < 2:
            return fail("artifact.detector has fewer than two signals")
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("independent") is not True:
            return fail("reviewer.independent is not true")
        recorded_bad = str(nc0.get("verbatim_bad") or "")
        if str(rec_b["pretext_veto_count"]) not in recorded_bad:
            return fail("artifact verbatim_bad drifted from live recount")

    print("SUCCESS:CNL-0024-probe2 both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
