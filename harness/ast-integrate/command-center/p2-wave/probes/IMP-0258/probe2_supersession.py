#!/usr/bin/env python3
"""Probe 2: supersession-marker check (negative control).

A superseded decision returned without its marker must FAIL the check.
The honest retriever must attach the marker, so the same check is silent
on good output (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.precedent import (  # noqa: E402
    check_supersession_markers,
    load_corpus,
    relabel_superseded_as_current,
    retrieve,
    strip_markers,
)

CORPUS = HERE / "fixtures/corpus.json"
QUERY = "Should participant votes be recorded as unsigned strings?"
SUPERSEDED_ID = "C-VOTE-010"
SUCCESSOR_ID = "C-VOTE-011"


def main() -> int:
    corpus = load_corpus(CORPUS)
    hits = retrieve(QUERY, corpus)
    ids = [h.get("council_id") or h.get("id") for h in hits]
    if SUPERSEDED_ID not in ids:
        print(f"FAILED:IMP-0258-probe2 superseded {SUPERSEDED_ID} not retrieved {ids}")
        return 1
    honest = check_supersession_markers(hits, corpus)
    if not honest["ok"] or honest["fires"]:
        print("FAILED:IMP-0258-probe2 honest retrieve failed marker check")
        print(json.dumps(honest, indent=2))
        return 1
    super_hit = next(h for h in hits if (h.get("council_id") or h.get("id")) == SUPERSEDED_ID)
    marker = super_hit["supersession_marker"]
    if marker.get("status") != "SUPERSEDED" or marker.get("superseded_by") != SUCCESSOR_ID:
        print("FAILED:IMP-0258-probe2 superseded hit missing successor marker")
        print(json.dumps(marker, indent=2))
        return 1

    stripped = strip_markers(hits)
    stripped_check = check_supersession_markers(stripped, corpus)
    if not stripped_check["fires"] or stripped_check["ok"]:
        print("FAILED:IMP-0258-probe2 stripped-marker negative control did not fire")
        print(json.dumps(stripped_check, indent=2))
        return 1
    if not any(v["reason"] == "missing-marker" for v in stripped_check["violations"]):
        print("FAILED:IMP-0258-probe2 expected missing-marker violation")
        print(json.dumps(stripped_check, indent=2))
        return 1

    lied = relabel_superseded_as_current(hits)
    lied_check = check_supersession_markers(lied, corpus)
    if not lied_check["fires"] or lied_check["ok"]:
        print("FAILED:IMP-0258-probe2 unmarked-superseded negative control did not fire")
        print(json.dumps(lied_check, indent=2))
        return 1
    if not any(v["reason"] == "unmarked-superseded" for v in lied_check["violations"]):
        print("FAILED:IMP-0258-probe2 expected unmarked-superseded violation")
        print(json.dumps(lied_check, indent=2))
        return 1

    payload = {
        "probe": "probe2-supersession",
        "unit_id": "IMP-0258",
        "query": QUERY,
        "retrieved_ids": ids,
        "honest_ok": honest["ok"],
        "honest_silent_on_good": not honest["fires"],
        "stripped_fires": stripped_check["fires"],
        "stripped_reasons": [v["reason"] for v in stripped_check["violations"]],
        "relabel_fires": lied_check["fires"],
        "relabel_reasons": [v["reason"] for v in lied_check["violations"]],
        "superseded_marker": marker,
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"honest_ok={honest['ok']} stripped_fires={stripped_check['fires']} "
        f"relabel_fires={lied_check['fires']} superseded={SUPERSEDED_ID}->{SUCCESSOR_ID}"
    )
    print("SUCCESS:IMP-0258-probe2 supersession-marker negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
