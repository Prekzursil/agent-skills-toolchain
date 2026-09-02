#!/usr/bin/env python3
"""Named probe 2: moderator-capture audit + no-judge mechanical control.

Independent of probe1's summary: rebuilds the frozen transcript, recomputes
the five-judge distribution, then:

* capture moderator must trip BOTH speaking-time and objection-routing
* even moderator must be silent on both
* audit-disabled deletion control must go silent on the capture transcript
* mechanical majority vs each judge: override_rate is measured, not asserted

Split with probe1 is resolved by comparing transcript sha256, never by vote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import council as C  # noqa: E402

OUT = HERE / "probe2-capture-nojudge.raw.json"


def main() -> int:
    even, even_sha = C.freeze_transcript("even")
    cap, cap_sha = C.freeze_transcript("capture")
    swap = C.judge_swap(even)

    even_audit = C.capture_audit(even, enabled=True)
    cap_audit = C.capture_audit(cap, enabled=True)
    disabled = C.capture_audit(cap, enabled=False)

    if cap_audit["fired"] is not True:
        print("FAILED:TST-0268-probe2 capture moderator not detected")
        print(json.dumps(cap_audit, sort_keys=True)[:2000])
        return 1
    if not cap_audit["speaking_time"]["flagged"]:
        print("FAILED:TST-0268-probe2 speaking-time audit silent on capture")
        return 1
    if not cap_audit["objection_routing"]["flagged"]:
        print("FAILED:TST-0268-probe2 objection-routing audit silent on capture")
        return 1
    if even_audit["fired"] is not False:
        print("FAILED:TST-0268-probe2 even moderator falsely flagged")
        return 1
    if even_audit["speaking_time"]["flagged"] or even_audit["objection_routing"]["flagged"]:
        print("FAILED:TST-0268-probe2 even moderator tripped a capture signal")
        return 1
    if disabled["fired"] is not False:
        print("FAILED:TST-0268-probe2 deletion control did not go silent")
        return 1
    if cap_sha == even_sha:
        print("FAILED:TST-0268-probe2 capture transcript identical to even")
        return 1

    nj = C.no_judge_control(even, swap)
    if nj["mechanical_verdict"] != C.mechanical_majority(even):
        print("FAILED:TST-0268-probe2 mechanical mismatch")
        return 1
    # Override rate is a measurement. Fail only if the comparison is unwired:
    # at least one judge in this fixture is designed to override the panel.
    if nj["override_count"] < 1:
        print("FAILED:TST-0268-probe2 all judges echo the panel; override comparison is vacuous")
        return 1
    if nj["panel_echo_count"] < 1:
        print("FAILED:TST-0268-probe2 no judge echoes the panel; comparison is one-sided")
        return 1

    doc = {
        "probe": "probe2_capture_and_nojudge",
        "unit_id": C.UNIT,
        "transcript_sha256": even_sha,
        "capture_transcript_sha256": cap_sha,
        "judge_distribution_recompute": swap["distribution"],
        "agreement_rate_recompute": swap["agreement_rate"],
        "n_judges": swap["n_judges"],
        "capture": {
            "detector_fired": cap_audit["fired"],
            "speaking_time_flag": cap_audit["speaking_time"]["flagged"],
            "objection_routing_flag": cap_audit["objection_routing"]["flagged"],
            "suppressed": C.SUPPRESSED,
            "even_silent": even_audit["fired"] is False,
            "audit": cap_audit,
            "even_audit": even_audit,
        },
        "audit_disabled_control": {
            "fired_on_capture": disabled["fired"],
            "proves_audit_wired": disabled["fired"] is False and cap_audit["fired"] is True,
        },
        "no_judge": nj,
        "spec": C.SPEC_MODERATOR_CAPTURE,
        "pass": True,
    }
    if not doc["audit_disabled_control"]["proves_audit_wired"]:
        print("FAILED:TST-0268-probe2 both-states capture control not discriminating")
        return 1

    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"capture_fired={cap_audit['fired']} even_silent={even_audit['fired'] is False} "
        f"disabled_silent={disabled['fired'] is False} "
        f"mechanical={nj['mechanical_verdict']} override_rate={nj['override_rate']:.3f} "
        f"sha={even_sha[:12]}"
    )
    print("SUCCESS:TST-0268-probe2 capture both-states and no-judge control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
