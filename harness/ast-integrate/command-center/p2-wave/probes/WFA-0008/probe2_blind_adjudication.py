#!/usr/bin/env python3
"""Probe 2: independent detector-control + contested/collapse honesty.

Re-scores fixtures/detector_control.json without reading cosine or Jaccard
from the artifact first. Confirms disagreements stay CONTESTED. A mutant
that collapses a cosine-only pair must be rejected.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as ADJ  # noqa: E402
import checker as CHK  # noqa: E402
import measures as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json"
CTRL = HERE / "fixtures" / "detector_control.json"


def main() -> int:
    ctrl = json.loads(CTRL.read_text(encoding="utf-8"))
    left = ctrl.get("a") or ctrl.get("a")
    right = ctrl.get("b") or ctrl.get("b")
    a_text = left["text"]
    b_text = right["text"]
    scored = M.score_pair(a_text, b_text)
    blind = ADJ.adjudicate(a_text, b_text)
    expect = ctrl.get("expect") or ctrl.get("expect")
    print(
        f"control lex={scored['lexical_score']} fired={scored['lexical_fired']} "
        f"band={scored['lexical_in_distinct_band']} "
        f"emb={scored['embedding_score']} fired={scored['embedding_fired']} "
        f"blind={blind['verdict']}"
    )
    want_lex = expect.get("lexical_fired", expect.get("lexical_fired"))
    want_emb = expect.get("embedding_fired", expect.get("embedding_fired"))
    want_blind = expect.get("blind_verdict", expect.get("blind_verdict"))
    if scored["lexical_fired"] != want_lex:
        print("FAILED:WFA-0008-probe2 control lexical fire mismatch")
        return 1
    if scored["embedding_fired"] != want_emb:
        print("FAILED:WFA-0008-probe2 control embedding fire mismatch")
        return 1
    if scored["lexical_fired"] or not scored["embedding_fired"]:
        print("FAILED:WFA-0008-probe2 detector did not show both-states on known rewrite")
        return 1
    if not scored["lexical_in_distinct_band"]:
        print("FAILED:WFA-0008-probe2 control lexical score not in 0.05-0.24 band")
        return 1
    if blind["verdict"] != want_blind:
        print("FAILED:WFA-0008-probe2 blind verdict mismatch")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0008-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    ok, why = CHK.scores_present(doc)
    print(f"scores_present={ok} {why}")
    if not ok:
        print("FAILED:WFA-0008-probe2 scores missing")
        return 1
    ok, why = CHK.both_states_full_rewrite(doc)
    print(f"both_states={ok} {why}")
    if not ok:
        print("FAILED:WFA-0008-probe2 both-states")
        return 1
    ok, why = CHK.disagreements_are_contested(doc)
    print(f"contested_honest={ok} {why}")
    if not ok:
        print("FAILED:WFA-0008-probe2 contested honesty")
        return 1
    ok, why = CHK.no_cosine_only_collapse(doc)
    print(f"no_cosine_only_collapse={ok} {why}")
    if not ok:
        print("FAILED:WFA-0008-probe2 cosine-only collapse present")
        return 1

    cosine_only = [
        r
        for r in (doc.get("contested") or [])
        if r.get("embedding_fired") and not r.get("lexical_fired")
    ]
    if not cosine_only:
        print("FAILED:WFA-0008-probe2 no cosine-only CONTESTED pair to mutant")
        return 1
    mutant = copy.deepcopy(doc)
    stolen = dict(cosine_only[0])
    stolen["collapsed_on_cosine_alone"] = True
    mutant.setdefault("collapsed", []).append(stolen)
    mok, mwhy = CHK.no_cosine_only_collapse(mutant)
    print(f"mutant_cosine_only_collapse accepted={mok} {mwhy}")
    if mok:
        print("FAILED:WFA-0008-probe2 cosine-only collapse mutant was accepted")
        return 1

    dropped = copy.deepcopy(doc)
    if "pairwise_scores" in dropped:
        key = "pairwise_scores"
    else:
        key = "pairwise_scores"
    rows = dropped.get(key) or []
    if not rows:
        print("FAILED:WFA-0008-probe2 no pairwise scores")
        return 1
    dropped[key] = [dict(rows[0])] + list(rows[1:])
    del dropped[key][0]["embedding_score"]
    sok, swhy = CHK.scores_present(dropped)
    print(f"mutant_dropped_embedding_score accepted={sok} {swhy}")
    if sok:
        print("FAILED:WFA-0008-probe2 friendlier-score mutant was accepted")
        return 1

    art_rel = "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json"
    raw = ART.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for row in man.get("artifacts") or []:
        if str(row.get("path") or "").replace("\\", "/") == art_rel:
            row["sha256"] = sha
            row["bytes"] = len(raw)
            row["present"] = True
            row["unit_id"] = "WFA-0008"
    man_path.write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    ret_path = HERE / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        ret = json.loads(ret_path.read_text(encoding="utf-8"))
        for row in ret.get("artifacts") or []:
            if str(row.get("path") or "").replace("\\", "/") == art_rel:
                row["sha256"] = sha
                row["bytes"] = len(raw)
        ret_path.write_text(
            json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"manifest_sha256={sha} bytes={len(raw)}")
    print("SUCCESS:WFA-0008-probe2 detector control and contested/collapse honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
