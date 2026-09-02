#!/usr/bin/env python3
"""Probe 2: both-states selector control + independent recount.

Mechanically different from probe 1:
  * selector layer (match_task / weight_premium), not evidence_bar()
  * independent recount by counting got==expected in the probe files and
    taking set intersection of domain_tags with task required_tags — no
    call to evidence_bar.

Both-states:
  FIRES on planted-bad (fabricated claim is rejected, no weight premium)
  SILENT on known-good (good claim is weighted, not in rejected)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import expertise as E  # noqa: E402

CLAIMS = HERE / "fixtures" / "claims"
PROBES = HERE / "fixtures" / "probes"
TASK = HERE / "fixtures" / "task-crypto.json"
NOTE = (
    E.REPO
    / "command-center/design/council/CNL-0015-expertise-ranked-selection-representing-expertise-without-.md"
)


def load_claim(name: str) -> dict:
    return E.load_json(CLAIMS / name)


def recount_probe(name: str) -> dict:
    doc = E.load_json(PROBES / name)
    n_v = len(doc.get("verifiable") or [])
    n_c = sum(
        1 for q in (doc.get("verifiable") or []) if q.get("got") == q.get("expected")
    )
    n_b = sum(
        1 for q in (doc.get("baseline") or []) if q.get("got") == q.get("expected")
    )
    ua = doc.get("unanswerable") if isinstance(doc.get("unanswerable"), dict) else {}
    return {
        "n_verifiable": n_v,
        "n_correct": n_c,
        "baseline_correct": n_b,
        "margin": n_c - n_b,
        "unanswerable_got": ua.get("got"),
        "domain_tag": doc.get("domain_tag"),
    }


def main() -> int:
    task = E.load_json(TASK)
    good = load_claim("good-cryptographer.json")
    fabricated = load_claim("fabricated.json")
    tls = load_claim("tls-only.json")
    below = load_claim("below-baseline.json")

    good_pool = E.match_task(task, [good])
    bad_pool = E.match_task(task, [fabricated])
    mixed = E.match_task(task, [good, fabricated, tls, below])

    fired_bad = (
        E.weight_for(bad_pool, "seat.crypto.fabricated", "cryptography") is False
        and "cryptography" in bad_pool["uncovered_tags"]
        and any(r.get("participant_id") == "seat.crypto.fabricated" for r in bad_pool["rejected"])
    )
    silent_good = (
        E.weight_for(good_pool, "seat.crypto.good", "cryptography") is True
        and "cryptography" in good_pool["covered_tags"]
        and not any(r.get("participant_id") == "seat.crypto.good" for r in good_pool["rejected"])
    )
    mixed_ok = (
        E.weight_for(mixed, "seat.crypto.good", "cryptography") is True
        and E.weight_for(mixed, "seat.crypto.fabricated", "cryptography") is False
        and E.weight_for(mixed, "seat.tls.good", "cryptography") is False
        and E.weight_for(mixed, "seat.crypto.below", "cryptography") is False
    )

    rc_good = recount_probe("crypto-good.json")
    rc_below = recount_probe("crypto-below-baseline.json")
    rc_tls = recount_probe("tls-good.json")
    fab_evidence = list(fabricated.get("evidence") or [])
    good_tags = set(good.get("domain_tags") or [])
    tls_tags = set(tls.get("domain_tags") or [])
    required = set(task.get("required_tags") or [])
    good_covers = bool(good_tags & required)
    tls_covers = bool(tls_tags & required)
    fabricated_is_empty = fab_evidence == []
    recount_separates = rc_good["margin"] > 0 and rc_below["margin"] <= 0
    ua_ok = rc_good["unanswerable_got"] == "idk"

    print(
        json.dumps(
            {
                "fired_on_bad": fired_bad,
                "silent_on_good": silent_good,
                "mixed_ok": mixed_ok,
                "good_pool": good_pool,
                "bad_pool": bad_pool,
                "recount_good": rc_good,
                "recount_below": rc_below,
                "recount_tls": rc_tls,
                "good_covers_task": good_covers,
                "tls_covers_task": tls_covers,
                "fabricated_evidence_len": len(fab_evidence),
            },
            sort_keys=True,
        )
    )
    print(
        f"fired_on_bad={fired_bad} silent_on_good={silent_good} mixed_ok={mixed_ok}"
    )
    print(
        f"recount good_margin={rc_good['margin']} below_margin={rc_below['margin']} "
        f"tls_covers={tls_covers} fabricated_empty={fabricated_is_empty}"
    )

    fail = False
    if not (fired_bad and silent_good):
        print("FAILED:CNL-0015-probe2 both-states did not discriminate")
        fail = True
    if not mixed_ok:
        print("FAILED:CNL-0015-probe2 mixed pool leaked weight to a failing claim")
        fail = True
    if not fabricated_is_empty:
        print("FAILED:CNL-0015-probe2 fabricated fixture is not empty-evidence")
        fail = True
    if not recount_separates or not ua_ok:
        print("FAILED:CNL-0015-probe2 recount did not separate good from below-baseline")
        fail = True
    if not good_covers or tls_covers:
        print("FAILED:CNL-0015-probe2 tag-set intersection is wrong")
        fail = True
    if int(rc_good["n_correct"]) != 4 or int(rc_good["baseline_correct"]) != 1:
        print(f"FAILED:CNL-0015-probe2 unexpected good counts {rc_good}")
        fail = True
    if int(rc_tls["n_correct"]) < int(rc_tls["baseline_correct"]):
        print("FAILED:CNL-0015-probe2 tls probe file itself is not discriminating")
        fail = True

    if NOTE.is_file():
        note = json.loads(NOTE.read_text(encoding="utf-8"))
        recorded = (note.get("matching") or {}).get("recorded_counts") or {}
        if recorded:
            if int(recorded.get("good_n_correct") or -1) != int(rc_good["n_correct"]):
                print(
                    f"FAILED:CNL-0015-probe2 note count drift {recorded} vs {rc_good}"
                )
                fail = True
            if int(recorded.get("good_baseline_correct") or -1) != int(
                rc_good["baseline_correct"]
            ):
                print("FAILED:CNL-0015-probe2 note baseline drift")
                fail = True
        if note.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNL-0015-probe2 note self-declared {note.get('state')}")
            fail = True
        sentinel = str(note.get("sentinel") or "")
        if "SUCCESS:CNL-0015" not in sentinel and "SUCCESS:CNL-0015" not in json.dumps(
            note
        ):
            print("FAILED:CNL-0015-probe2 sentinel missing from note")
            fail = True

    if fail:
        print("FAILED:CNL-0015-probe2 both-states / independent recount")
        return 1
    print("SUCCESS:CNL-0015-probe2 both-states control and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
