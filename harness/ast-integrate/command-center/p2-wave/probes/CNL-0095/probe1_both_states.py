#!/usr/bin/env python3
"""Probe 1: detector-control first, then both-states, FPR as a number, negative control.

Order is load-bearing: a known-present instance is found BEFORE any absence
(SILENT) is reported. A probe that is silent in both states fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import schema_validate as SV  # noqa: E402
from transcript import jaccard, tokens  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0095-premature-convergence-and-forced-re-divergence.md"
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0095-probe1 {msg}")
    return 1


def line(run: dict, det: dict) -> str:
    return D.format_line(run, det)


def main() -> int:
    jp = jaccard(tokens(F.IDEAS["latency"]), tokens(F.LATENCY_PARAPHRASE))
    jo = jaccard(tokens(F.OBJS["latency"]), tokens(F.LATENCY_OBJ_PARAPHRASE))
    print(f"jaccard_idea_paraphrase={jp} jaccard_obj_paraphrase={jo} threshold=0.8")
    if jp < 0.8 or jo < 0.8:
        return fail("paraphrase fixtures do not cluster at Jaccard 0.80; fix fixtures first")

    # Detector-control: known-present BEFORE any absence claim.
    kp_run = F.known_present()
    kp = D.detect(kp_run)
    print("detector_control_first=True")
    print(line(kp_run, kp))
    if not kp["fired"] or kp["status"] != "FIRE":
        return fail("detector-control known-present did not FIRE")
    print("detector_control_found_known_present=True")

    planted = F.planted_bad()
    bad = D.detect(planted)
    print(line(planted, bad))
    if not bad["fired"]:
        return fail("planted-bad did not FIRE")

    good_run = F.known_good()
    good = D.detect(good_run)
    print(line(good_run, good))
    if good["fired"] or good["status"] != "SILENT":
        return fail("known-good was not SILENT")
    if not good.get("absence_claimed"):
        return fail("known-good silence must be an explicit absence claim")

    easy_run = F.easy_met_quota()
    easy = D.detect(easy_run)
    print(line(easy_run, easy))
    if easy["fired"] or easy["status"] != "SILENT":
        return fail("easy-met-quota (round 1, quotas met) was not SILENT")

    late = D.detect(F.round10_premature())
    print(line(F.round10_premature(), late))
    if not late["fired"]:
        return fail("round10-premature did not FIRE (round count leaked into the signal)")

    nc = D.detect(F.no_converge())
    print(line(F.no_converge(), nc))
    if nc["status"] != "NO-CONVERGE" or nc.get("absence_claimed"):
        return fail("no-converge must not be reported as clean silence")

    decoy_easy = D.decoy_round_count(easy_run)
    decoy_late = D.decoy_round_count(F.round10_premature())
    print(f"decoy_round_easy_fired={decoy_easy['fired']} decoy_round_late_fired={decoy_late['fired']}")
    if not decoy_easy["fired"] or decoy_late["fired"]:
        return fail("round-count decoy did not show the FP/FN pair that quota-attainment avoids")

    decoy_ev = D.decoy_event_count(planted)
    print(
        f"decoy_event_planted_fired={decoy_ev['fired']} "
        f"idea_events={decoy_ev.get('idea_events')} objection_events={decoy_ev.get('objection_events')}"
    )
    if decoy_ev["fired"]:
        return fail("event-count decoy should be SILENT on paraphrase-padded planted-bad")

    clean = F.clean_fixtures()
    fp = 0
    for run in clean:
        det = D.detect(run)
        print(f"clean {line(run, det)}")
        if det["fired"]:
            fp += 1
    fpr = fp / len(clean)
    print(f"false_positive_rate={fpr} clean_n={len(clean)} false_positives={fp}")
    if fpr != 0.0:
        return fail(f"FPR is {fpr}, expected 0.0 on the clean set")

    print("negative_control_state=planted-bad")
    print(f"negative_control_action={bad['status']}")
    print(f"negative_control_raw={line(planted, bad)}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0095" not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact-unparseable:{exc}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    body = SV.domain(doc)
    if body.get("false_positive_rate") != fpr:
        return fail("artifact FPR mismatch")
    bs = body.get("both_states") or {}
    if bs.get("planted_bad", {}).get("fired") is not True:
        return fail("artifact planted-bad not fired")
    if bs.get("known_good", {}).get("fired") is not False:
        return fail("artifact known-good not silent")
    dc = body.get("detector_control") or {}
    if dc.get("found") is not True or dc.get("evaluated_before_absence") is not True:
        return fail("artifact detector-control missing")
    if not SCHEMA.is_file():
        return fail("schema missing")
    g_rej = SV.garbage_rejected()
    print(f"garbage_rejected={g_rej}")
    if g_rej != 3:
        return fail(f"schema accepted garbage ({g_rej}/3 rejected)")
    errs = SV.error_messages(doc)
    if errs:
        return fail("schema:" + errs[0])
    print("schema_valid=True")
    print("SUCCESS:CNL-0095-probe1 detector-control both-states FPR negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
