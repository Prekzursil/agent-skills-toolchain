#!/usr/bin/env python3
"""Probe 1: detector-control first, both-states, FPR as a number, negative control.

Order is load-bearing: a known-present instance is found BEFORE any absence
(SILENT) is reported. A probe silent in both states fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import spec_view as SV  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0086-echo-chamber-measuring-independence-loss.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0086-probe1 {msg}")
    return 1


def main() -> int:
    kp_run = F.known_present()
    kp = D.detect(kp_run)
    print("detector_control_first=True")
    print(D.format_line(kp_run, kp))
    if not kp["fired"] or kp["status"] != "FIRE":
        return fail("detector-control known-present did not FIRE")
    print("detector_control_found_known_present=True")

    planted = F.planted_bad_shared_source()
    bad = D.detect(planted)
    print(D.format_line(planted, bad))
    if not bad["fired"] or not bad.get("s1_shared_retrieval"):
        return fail("planted-bad-shared-source did not FIRE on S1")

    seq = F.planted_bad_sequential()
    seq_d = D.detect(seq)
    print(D.format_line(seq, seq_d))
    if not seq_d["fired"] or not seq_d.get("s2_sequential_copy"):
        return fail("planted-bad-sequential did not FIRE on S2")
    if seq_d.get("s1_shared_retrieval"):
        return fail("sequential fixture must not trip S1 (first passes are independent)")

    good_run = F.known_good_genuine_convergence()
    good = D.detect(good_run)
    print(D.format_line(good_run, good))
    if good["fired"] or good["status"] != "SILENT":
        return fail("known-good was not SILENT")
    if not good.get("absence_claimed"):
        return fail("known-good silence must be an explicit absence claim")

    nc_run = F.no_first_pass()
    nc = D.detect(nc_run)
    print(D.format_line(nc_run, nc))
    if nc["status"] != "INSUFFICIENT" or nc.get("absence_claimed"):
        return fail("no-first-pass must not be reported as clean silence")

    decoy_gen = D.decoy_generation_independence(planted)
    decoy_vote = D.decoy_vote_agreement(good_run)
    print(
        f"decoy_generation_planted_fired={decoy_gen['fired']} "
        f"decoy_vote_known_good_fired={decoy_vote['fired']}"
    )
    if decoy_gen["fired"]:
        return fail("generation-independence decoy should be SILENT on independently-generated shared-source")
    if not decoy_vote["fired"]:
        return fail("vote-agreement decoy should FIRE on genuine convergence (the FP we refuse)")

    clean = F.clean_fixtures()
    fp = 0
    for run in clean:
        det = D.detect(run)
        print(f"clean {D.format_line(run, det)}")
        if det["fired"]:
            fp += 1
    fpr = fp / len(clean)
    print(f"false_positive_rate={fpr} clean_n={len(clean)} false_positives={fp}")
    if fpr != 0.0:
        return fail(f"FPR is {fpr}, expected 0.0 on the clean set")

    print("negative_control_state=planted-bad-shared-source")
    print(f"negative_control_action={bad['status']}")
    print(f"negative_control_raw={D.format_line(planted, bad)}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0086" not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact-unparseable:{exc}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    spec = SV.detector_spec(doc)
    if spec.get("false_positive_rate") != fpr:
        return fail("artifact FPR mismatch")
    bs = spec.get("both_states") or {}
    if bs.get("planted_bad", {}).get("fired") is not True:
        return fail("artifact planted-bad not fired")
    if bs.get("known_good", {}).get("fired") is not False:
        return fail("artifact known-good not silent")
    dc = spec.get("detector_control") or {}
    if dc.get("found") is not True or dc.get("evaluated_before_absence") is not True:
        return fail("artifact detector-control missing")
    if not SCHEMA.is_file():
        return fail("schema missing")
    errs = SV.schema_errors(doc)
    if errs:
        print("schema_errors=" + "; ".join(errs[:8]))
        return fail("artifact schema-invalid")
    print("schema_valid=True")
    print("SUCCESS:CNL-0086-probe1 detector-control both-states FPR negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
