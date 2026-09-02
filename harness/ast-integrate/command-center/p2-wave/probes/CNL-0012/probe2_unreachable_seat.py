#!/usr/bin/env python3
"""Probe 2: unreachable exact seat LOUD-degrades; silent same-vendor sub is rejected."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import roster as R  # noqa: E402

OUT = HERE / "probe2-unreachable.raw.json"
SPEC = HERE / "fixtures" / "catalog-named-spec.json"
GOOD = HERE / "fixtures" / "estate-good.json"
BAD = HERE / "fixtures" / "estate-unreachable.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    spec = load(SPEC)
    good_estate = load(GOOD)
    bad_estate = load(BAD)

    good = R.resolve_exact(spec, good_estate)
    good_v = R.silent_substitution_violations(spec, good)
    if good["decision"] != "SEATED" or good_v:
        print("FAILED:CNL-0012-probe2 good-estate not silent", good["decision"], good_v)
        return 1
    if good.get("degradations"):
        print("FAILED:CNL-0012-probe2 good-estate emitted degradation")
        return 1
    seated_ids = {s["id"] for s in good["seated"]}
    if seated_ids != {s["id"] for s in spec["seats"]}:
        print("FAILED:CNL-0012-probe2 good-estate roster mismatch")
        return 1

    bad = R.resolve_exact(spec, bad_estate)
    bad_v = R.silent_substitution_violations(spec, bad)
    if bad["decision"] != "REFUSED":
        print("FAILED:CNL-0012-probe2 unreachable did not REFUSE")
        return 1
    if bad["seated"]:
        print("FAILED:CNL-0012-probe2 unreachable seated a partial exact roster")
        return 1
    if bad_v:
        print("FAILED:CNL-0012-probe2 unreachable violations", bad_v)
        return 1
    loud = [d for d in bad["degradations"] if d.get("class") == R.LOUD]
    if len(loud) != len(spec["seats"]):
        print("FAILED:CNL-0012-probe2 expected one LOUD record per unmet seat")
        return 1
    if any(d.get("substituted") for d in loud):
        print("FAILED:CNL-0012-probe2 substitution flag set")
        return 1
    sonnet_seated = [
        s
        for s in (bad.get("seated") or []) + (bad.get("would_have_seated") or [])
        if s.get("model") == "claude-sonnet-4"
    ]
    if sonnet_seated:
        print("FAILED:CNL-0012-probe2 same-vendor sonnet was used as a substitute")
        return 1
    opus_opts = None
    for d in loud:
        if d.get("seat_id") == "seat.anthropic.opus":
            opus_opts = d.get("available_same_vendor") or []
    if not opus_opts:
        print("FAILED:CNL-0012-probe2 opus degradation hid same-vendor options")
        return 1

    planted = R.planted_silent_same_vendor_substitution(spec)
    planted_v = R.silent_substitution_violations(spec, planted)
    if not planted_v:
        print("FAILED:CNL-0012-probe2 detector silent on planted substitution")
        return 1
    if not any(v.startswith("same-vendor-substitution:") or v.startswith("silent-substitution:") for v in planted_v):
        print("FAILED:CNL-0012-probe2 detector missed same-vendor class", planted_v)
        return 1

    doc = {
        "probe": "CNL-0012-probe2-unreachable-seat",
        "good": {
            "decision": good["decision"],
            "violations": good_v,
            "degradations": good["degradations"],
            "seated": good["seated"],
        },
        "unreachable": {
            "decision": bad["decision"],
            "violations": bad_v,
            "degradations": bad["degradations"],
            "seated": bad["seated"],
            "would_have_seated": bad["would_have_seated"],
        },
        "planted_silent_substitution": {
            "violations": planted_v,
            "fired": True,
        },
        "both_states": {
            "fires_on_planted_bad": True,
            "silent_on_known_good": True,
        },
        "negative_control_verbatim": (
            "The check rejects a planted silent same-vendor substitution "
            "(requested claude-opus-4, seated a sonnet-shaped swap, degradations=[]). "
            "It is silent when resolve_exact seats the exact requested vendor+model "
            "on the known-good estate."
        ),
        "pass": True,
    }
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        "good_decision="
        + good["decision"]
        + " good_violations=0"
        + " unreachable_decision="
        + bad["decision"]
        + " loud_records="
        + str(len(loud))
        + " seated_on_unreachable="
        + str(len(bad["seated"]))
        + " planted_violations="
        + str(len(planted_v))
        + " both_states_ok=True"
    )
    print("SUCCESS:CNL-0012-probe2 unreachable-seat loud degrade and refuse silent substitution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
