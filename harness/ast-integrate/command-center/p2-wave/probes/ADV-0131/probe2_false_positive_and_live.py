#!/usr/bin/env python3
"""Probe 2: false-positive control + known live instance.

Independent of probe 1. A pair that looks contradictory (same metric, two
numbers) but names two different denominators must NOT be reported. A naive
number-only matcher must still fire, so the control is discriminating.
The known live 17-DECISION-LOG.md:175 instance must appear in the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
from scenario import FP_SUBJECT, write_false_positive, write_known_live  # noqa: E402

ART = D.REPO / D.OUTPUT_REL


def main() -> int:
    with TemporaryDirectory(prefix="adv-0131-probe2-fp-") as td:
        root = Path(td)
        write_false_positive(root)
        claims = D.extract_numeric(root, root)
        pairs = D.mine(root, root)
        reported = [p for p in pairs if p["subject_id"] == FP_SUBJECT]
        naive = [p for p in D.naive_numeric_pairs(claims) if p["subject_id"] == FP_SUBJECT]
        print(
            f"fp_reported={len(reported)} naive_would_report={len(naive)} "
            f"denoms={[c.get('denom') for c in claims]}"
        )
        if reported:
            print("FAILED:ADV-0131-probe2 false-positive control was reported")
            return 1
        if not naive:
            print("FAILED:ADV-0131-probe2 naive matcher did not fire; control is vacuous")
            return 1

    with TemporaryDirectory(prefix="adv-0131-probe2-live-") as td:
        root = Path(td)
        write_known_live(root)
        pairs = D.mine(root, root)
        known = [
            p
            for p in pairs
            if p["exclusivity_reason"] == "present-tense-versus-resolved"
        ]
        print(
            f"known_live n={len(known)} line={[p['left']['line'] for p in known]} "
            f"bare={[(p.get('mechanical') or {}).get('bare_m_nn_count') for p in known]}"
        )
        if not known:
            print("FAILED:ADV-0131-probe2 known live instance not found")
            return 1
        p0 = known[0]
        if p0["left"]["line"] != 175:
            print(f"FAILED:ADV-0131-probe2 expected line 175 got {p0['left']['line']}")
            return 1
        if D.CANON_LOG not in (p0.get("verbatim_anchors") or []):
            print("FAILED:ADV-0131-probe2 canonical 17-DECISION-LOG.md:175 missing")
            return 1
        if (p0.get("mechanical") or {}).get("bare_m_nn_count") != 0:
            print("FAILED:ADV-0131-probe2 architecture bare M-NN count is not zero")
            return 1

    if not ART.is_file():
        print("FAILED:ADV-0131-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if D.SENTINEL not in text:
        print("FAILED:ADV-0131-probe2 sentinel-absent")
        return 1
    if "17-DECISION-LOG.md:175" not in text:
        print("FAILED:ADV-0131-probe2 artifact missing known live anchor")
        return 1
    art_fp = [
        p
        for p in (doc.get("pairs") or [])
        if isinstance(p, dict) and p.get("subject_id") == FP_SUBJECT
    ]
    print(f"artifact_fp_pairs={len(art_fp)} reported_flag={doc.get('false_positive_control', {}).get('reported')}")
    if art_fp or doc.get("false_positive_control", {}).get("reported") is True:
        print("FAILED:ADV-0131-probe2 artifact contains the false-positive control")
        return 1
    for p in doc.get("pairs") or []:
        anchors = p.get("verbatim_anchors") or []
        left = (p.get("left") or {}).get("anchor")
        right = (p.get("right") or {}).get("anchor")
        if len(anchors) < 2 or not left or not right:
            print("FAILED:ADV-0131-probe2 pair missing two verbatim file:line anchors", p.get("id"))
            return 1
        if ":" not in str(left) or ":" not in str(right):
            print("FAILED:ADV-0131-probe2 anchors are not file:line", left, right)
            return 1
    if not doc.get("known_live_instance", {}).get("found"):
        print("FAILED:ADV-0131-probe2 artifact known_live_instance.found is false")
        return 1

    print("SUCCESS:ADV-0131-probe2 false-positive absent; known live 17-DECISION-LOG.md:175 present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
