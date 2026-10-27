#!/usr/bin/env python3
"""Probe 2: restatement collapse negative control; both-states.

Rebuilds planted talks from companion blog bytes. Known-good artifact passes.
Mutants that skip collapse, drop the control, or self-declare BLOCKED fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as K  # noqa: E402
import corpus as C  # noqa: E402
import extract as E  # noqa: E402
import measure as M  # noqa: E402
from textutil import bytes_to_text  # noqa: E402

ART = REPO / C.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0140-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = K.check(doc, repo=REPO)
    print(f"good_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0140-probe2 good artifact rejected")
        return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    gok, gwhy = K.check(garbage, repo=REPO)
    print(f"garbage_ok={gok} {gwhy}")
    if gok:
        print("FAILED:RES-0140-probe2 garbage accepted")
        return 1

    blocked = copy.deepcopy(doc)
    blocked["state"] = "BLOCKED"
    bok, bwhy = K.check(blocked, repo=REPO)
    print(f"blocked_ok={bok} {bwhy}")
    if bok:
        print("FAILED:RES-0140-probe2 BLOCKED accepted")
        return 1

    live = M.measure()
    ctrl = live["restatement_control"]
    print(f"live_both_collapse={ctrl['both_collapse']} rows={ctrl['rows']}")
    if not ctrl["both_collapse"]:
        print("FAILED:RES-0140-probe2 live restatements did not collapse")
        return 1

    # Independent rebuild: restatement bytes must match regenerating from blog.
    for row in ctrl["rows"]:
        rest_id = row["transcript_id"]
        blog_id = row["companion_blog_id"]
        rebuilt = M.rebuild_restatement_from_blog(blog_id, rest_id)
        stored = C.capture_path(rest_id).read_text(encoding="utf-8")
        if rebuilt != stored:
            print(f"FAILED:RES-0140-probe2 restatement drift {rest_id}")
            return 1
        blog_raw = C.capture_path(blog_id).read_bytes()
        index = M.load_index()
        brow = next(r for r in index["items"] if r["id"] == blog_id)
        blog_text = bytes_to_text(blog_raw, brow.get("content_type") or "")
        blog_mechs = E.extract_mechanisms(blog_text)
        talk_mechs = E.extract_mechanisms(rebuilt)
        uniq = E.unique_against(talk_mechs, blog_mechs)
        print(
            f"rebuild {rest_id} talk_mechs={len(talk_mechs)} "
            f"blog_mechs={len(blog_mechs)} unique={len(uniq)}"
        )
        if uniq:
            print(f"FAILED:RES-0140-probe2 unique leftover {rest_id}: {uniq[0]['text'][:160]}")
            return 1

    dropped = copy.deepcopy(doc)
    del dropped["restatement_control"]
    dok, dwhy = K.check(dropped, repo=REPO)
    print(f"drop_control_ok={dok} {dwhy}")
    if dok:
        print("FAILED:RES-0140-probe2 missing control accepted")
        return 1

    inflated = copy.deepcopy(doc)
    inflated["restatement_control"]["both_collapse"] = False
    inflated["restatement_control"]["rows"][0]["unique_after_collapse"] = 12
    iok, iwhy = K.check(inflated, repo=REPO)
    print(f"inflate_ok={iok} {iwhy}")
    if iok:
        print("FAILED:RES-0140-probe2 inflated restatement accepted")
        return 1

    equalized = copy.deepcopy(doc)
    equalized["comparison"]["transcript_intra_inflated_per_10k"] = equalized["comparison"][
        "transcript_incremental_honest_per_10k"
    ]
    eok, ewhy = K.check(equalized, repo=REPO)
    print(f"no_inflation_ok={eok} {ewhy}")
    if eok:
        print("FAILED:RES-0140-probe2 equal inflated/honest accepted")
        return 1

    e3 = copy.deepcopy(doc)
    for c in e3["claims"]:
        if c.get("evidence_tier") == "E3":
            c["cited_as_measured_fact"] = True
            break
    pok, pwhy = K.check(e3, repo=REPO)
    print(f"e3_promote_ok={pok} {pwhy}")
    if pok:
        print("FAILED:RES-0140-probe2 E3 promote accepted")
        return 1

    print("SUCCESS:RES-0140-probe2 restatement collapse discriminates both states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
