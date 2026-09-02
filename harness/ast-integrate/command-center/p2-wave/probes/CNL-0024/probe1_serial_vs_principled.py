#!/usr/bin/env python3
"""Probe 1: serial-vetoer vs consistent principled dissenter.

Named discriminating feature: pretext_veto_count (cited invariant not in
object.violations). Raw veto count is the same (5) on both fixtures and MUST
NOT be what separates them.

Signal 1 (this probe): engine classify_seat reading the applied-row pretext bit.
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
    print(f"FAILED:CNL-0024-probe1 {msg}")
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
    g = good["classifications"][g_seat]
    b = bad["classifications"][b_seat]
    u = unused["classifications"][V.target_seat(unused_fx)]
    s = scope["classifications"][V.target_seat(scope_fx)]
    a = unauth["classifications"][V.target_seat(unauth_fx)]

    print(
        json.dumps(
            {
                "discriminating_feature": g["discriminating_feature"],
                "principled": g,
                "serial": b,
                "unused": u,
                "council_scope_status": [row["status"] for row in scope["log"]],
                "unauthorized_status": [row["status"] for row in unauth["log"]],
                "serial_override": bad["overrides"],
            },
            sort_keys=True,
        )
    )

    if g["accepted"] != b["accepted"] or g["accepted"] != 5:
        return fail(
            f"fixtures must share veto count 5; got principled={g['accepted']} serial={b['accepted']}"
        )
    if g["pretext_veto_count"] != 0:
        return fail(f"principled pretext_veto_count={g['pretext_veto_count']} want 0")
    if b["pretext_veto_count"] < 2:
        return fail(f"serial pretext_veto_count={b['pretext_veto_count']} want >=2")
    if g["verdict"] != "SILENT" or g["abuse"] is not False:
        return fail(f"principled not SILENT: {g}")
    if b["verdict"] != "ABUSE" or b["abuse"] is not True:
        return fail(f"serial not ABUSE: {b}")
    if g["matched_veto_count"] != 5:
        return fail("principled must match invariant on every veto")
    if b["matched_veto_count"] != 0:
        return fail("serial must match invariant on zero vetoes")
    if u["abuse"] is not False or u["accepted"] != 0:
        return fail(f"unused veto right must be SILENT: {u}")
    if scope["log"][0]["status"] != "invalid_scope":
        return fail(f"council-scope must be invalid_scope: {scope['log']}")
    if s["abuse"] is not False:
        return fail("invalid_scope must not be classified as abuse")
    if unauth["log"][0]["status"] != "unauthorized":
        return fail(f"missing right must be unauthorized: {unauth['log']}")
    if a["abuse"] is not False:
        return fail("unauthorized must not be classified as serial-abuse")
    if not bad["overrides"] or bad["overrides"][0].get("status") != "overridden":
        return fail(f"serial override did not land: {bad['overrides']}")
    if "opt.budget" not in bad["feasible_options"]:
        return fail("overridden option was not restored to the feasible set")
    if len(bad["feasible_options"]) != 1:
        return fail(f"only the overridden option should return; got {bad['feasible_options']}")

    naive_count_would_fire_on_principled = g["accepted"] >= 2
    if not naive_count_would_fire_on_principled:
        return fail("naive-count control is not live")
    print(
        "naive_veto_count_would_flag_principled="
        f"{naive_count_would_fire_on_principled} "
        "but_pretext_discriminator_silent=True"
    )
    print(
        f"feature=pretext_veto_count principled={g['pretext_veto_count']} "
        f"serial={b['pretext_veto_count']} "
        f"principled_verdict={g['verdict']} serial_verdict={b['verdict']}"
    )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {st}")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNL-0024" not in text:
            return fail("sentinel absent from artifact")
        feat = str(
            (doc.get("abuse_detection") or {}).get("discriminating_feature")
            or ""
        )
        if feat != "pretext_veto_count":
            return fail(f"artifact discriminator mismatch {feat!r}")

    print("SUCCESS:CNL-0024-probe1 serial-vs-principled pretext_veto_count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
