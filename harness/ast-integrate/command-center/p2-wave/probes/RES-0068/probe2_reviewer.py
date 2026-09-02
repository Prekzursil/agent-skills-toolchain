#!/usr/bin/env python3
"""Probe 2: adversarial reviewer — both-states, one-rail=E3, Temporal is contrast."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    grade_claim,
    load_harvest_index,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0068-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    idx = load_harvest_index()
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 4:
        return fail("too-few-claims")

    # Known-good: every cited claim is E2 / citable.
    for c in claims:
        g = grade_claim(c, idx)
        if not g["citable_as_measured_fact"]:
            return fail(f"good-state-not-citable:{c.get('claim_id')} {g['problems']}")
    print("both_states good=True (all claims E2 against live bytes)")

    # Known-broken A: drop to one rail => E3, not a measured fact.
    sample = copy.deepcopy(claims[0])
    sample["source_lineage"] = (sample.get("source_lineage") or [])[:1]
    g1 = grade_claim(sample, idx)
    print(f"one_rail tier={g1['tier']} citable={g1['citable_as_measured_fact']}")
    if g1["tier"] != "E3" or g1["citable_as_measured_fact"]:
        return fail("one-rail-must-be-e3")

    # Known-broken B: fabricated quote not in captured bytes.
    broken = copy.deepcopy(claims[0])
    for r in broken.get("source_lineage") or []:
        r["quote"] = "THIS-QUOTE-IS-NOT-IN-ANY-SNAPSHOT-BYTES-RES-0068"
    g2 = grade_claim(broken, idx)
    print(f"fabricated_quote citable={g2['citable_as_measured_fact']} problems={g2['problems']}")
    if g2["citable_as_measured_fact"] or not g2["problems"]:
        return fail("fabricated-quote-silent")

    # Temporal must be contrast, not the named pathology engine.
    named = str(doc.get("named_engine_exhibiting_local_no_timeout_pathology") or "")
    if named == "Temporal":
        return fail("temporal-must-not-be-named-pathology")
    temporal = next(
        (c for c in claims if "Temporal" in str(c.get("engine") or "")),
        None,
    )
    if temporal is None:
        return fail("temporal-claim-missing")
    if temporal.get("matches_local_no_timeout_pathology") is True:
        return fail("temporal-marked-pathology")
    if temporal.get("contrast_engine") is not True:
        return fail("temporal-not-contrast")

    celery = next(
        (c for c in claims if str(c.get("engine") or "").startswith("Celery")),
        None,
    )
    if celery is None or celery.get("matches_local_no_timeout_pathology") is not True:
        return fail("celery-pathology-flag")
    if "No time limit" not in str(celery.get("per_child_timeout") or "") and "No time limit" not in json.dumps(
        celery.get("source_lineage")
    ):
        return fail("celery-no-time-limit-quote-missing")

    rec = doc.get("named_engine_record") or {}
    if "Temporal" not in str(rec.get("contrast_engine") or ""):
        return fail("record-contrast-missing")

    print("fired_on_bad=True silent_on_good=True temporal_is_contrast=True celery_is_pathology=True")
    print("SUCCESS:RES-0068-probe2 reviewer both-states, E3 one-rail, Temporal contrast")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
