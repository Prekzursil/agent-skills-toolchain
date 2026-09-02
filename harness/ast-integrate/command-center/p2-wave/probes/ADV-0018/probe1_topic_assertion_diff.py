#!/usr/bin/env python3
"""Probe 1: topic-retrieve notes, then assertion-diff against live measurements.

Mechanically different from probe 2 (file-byte frontmatter; no topic search).
Catalog recall control: a known-present fact must be found before absence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sweep import (  # noqa: E402
    OUT_REL,
    REPO,
    UID,
    find_classified,
    run_sweep,
)

ART = REPO / OUT_REL
UNMARKED = "ADV-0018-planted-stale-unmarked"
CURRENT = "ADV-0018-planted-current"
DL_CURRENT = "DL-0001"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    sweep = run_sweep()
    recall = sweep["recall"]
    if not recall["pass"]:
        return fail(recall["detail"])
    unmarked = find_classified(sweep, UNMARKED)
    if unmarked is None:
        return fail(f"{UNMARKED} not retrieved by topic search")
    if not unmarked["is_contradicted"]:
        return fail(f"{UNMARKED} was not assertion-diffed as contradicted")
    if not unmarked["still_recallable_as_truth"]:
        return fail(f"{UNMARKED} should still be recallable (no superseded_by)")
    current = find_classified(sweep, CURRENT)
    if current is None:
        return fail(f"{CURRENT} not retrieved")
    if current["is_contradicted"]:
        return fail(f"{CURRENT} incorrectly flagged as contradicted")
    dl = find_classified(sweep, DL_CURRENT)
    if dl is None:
        return fail(f"{DL_CURRENT} not retrieved from 17-DECISION-LOG.md")
    if dl["is_contradicted"]:
        return fail(f"{DL_CURRENT} current census was contradicted")
    if sweep["measured"]["option_family_m_count"] < 1:
        return fail("live option_family_m_count is zero; census instrument is broken")
    if not sweep["contradicted"]:
        return fail("topic+assertion diff found zero contradicted notes")
    if not sweep["still_recallable"]:
        return fail("no unmarked contradicted note; detector cannot go red")

    payload = {
        "probe": "probe1-topic-assertion-diff",
        "unit_id": UID,
        "pass": True,
        "computed_not_asserted": True,
        "recall_hits": recall["hits"],
        "notes_retrieved": sweep["notes_retrieved"],
        "contradicted_ids": [c["note_id"] for c in sweep["contradicted"]],
        "still_recallable_ids": [c["note_id"] for c in sweep["still_recallable"]],
        "option_family_m_count": sweep["measured"]["option_family_m_count"],
        "collision_count": sweep["measured"]["collision_count"],
        "collision_live": sweep["measured"]["collision_live"],
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable {exc}")
        if not isinstance(doc, dict):
            return fail("artifact not an object")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        tests = {
            t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)
        }
        recall_test = tests.get("recall-control")
        if not recall_test or str(recall_test.get("result") or "").upper() != "PASS":
            return fail("artifact recall-control is not PASS")
        if not (doc.get("targets") or []):
            return fail("artifact has no targets")
        probes = doc.get("named_probes") or []
        if len(probes) < 2:
            return fail("artifact missing both named probes")
        if not any(
            (p.get("raw_output") or "") for p in probes if isinstance(p, dict)
        ):
            return fail("named probes lack raw_output")

    print(
        "recall_ok=True unmarked_contradicted=True current_clean=True "
        f"contradicted={len(sweep['contradicted'])} "
        f"still_recallable={len(sweep['still_recallable'])}"
    )
    print(f"SUCCESS:{UID}-probe1 topic retrieve + assertion diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
