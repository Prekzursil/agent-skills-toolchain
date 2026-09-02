"""Implementation search over a recorded index.

Absence is a finding only after a search that can find a known-present
implementation. Probes re-run this engine; they do not trust artifact flags.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constants import (
    CONTROL_MECH_ID,
    CONTROL_KNOWN_IMPL,
    INDEX_REL,
    MAJOR_FRAMEWORKS,
    PLANTED_ABSENT_ID,
    REPO,
    STAR_FLOOR,
)


def load_index(path: Path | None = None) -> dict[str, Any]:
    p = path or (REPO / INDEX_REL)
    return json.loads(p.read_text(encoding="utf-8"))


def is_popular(hit: dict[str, Any]) -> bool:
    fw = hit.get("first_class_api_in")
    if isinstance(fw, str) and fw.lower() in MAJOR_FRAMEWORKS:
        return True
    stars = hit.get("stars")
    return isinstance(stars, int) and stars >= STAR_FLOOR


def search_mechanism(mechanism_id: str, index: dict[str, Any] | None = None) -> dict[str, Any]:
    idx = index if index is not None else load_index()
    queries = list((idx.get("queries") or {}).get(mechanism_id) or [])
    hits = [
        h
        for h in (idx.get("hits") or [])
        if isinstance(h, dict) and h.get("mechanism_id") == mechanism_id
    ]
    popular = [h for h in hits if is_popular(h)]
    if not queries:
        verdict = "search-not-performed"
        performed = False
    elif popular:
        verdict = "popular-implementation-found"
        performed = True
    else:
        verdict = "no-popular-implementation"
        performed = True
    return {
        "mechanism_id": mechanism_id,
        "performed": performed,
        "queries": queries,
        "hit_count": len(hits),
        "popular_hit_count": len(popular),
        "hits": [
            {
                "name": h.get("name"),
                "url": h.get("url"),
                "kind": h.get("kind"),
                "stars": h.get("stars"),
                "first_class_api_in": h.get("first_class_api_in"),
                "popular": is_popular(h),
            }
            for h in hits
        ],
        "verdict": verdict,
        "popularity_rule": (
            f"first-class API in {sorted(MAJOR_FRAMEWORKS)} OR dedicated repo "
            f"stars >= {STAR_FLOOR}"
        ),
    }


def detector_control(index: dict[str, Any] | None = None) -> dict[str, Any]:
    idx = index if index is not None else load_index()
    present = search_mechanism(CONTROL_MECH_ID, idx)
    absent = search_mechanism(PLANTED_ABSENT_ID, idx)
    names = " ".join(str(h.get("name") or "") for h in present.get("hits") or [])
    found_known = (
        present["verdict"] == "popular-implementation-found"
        and CONTROL_KNOWN_IMPL in names
        and present["popular_hit_count"] >= 1
    )
    silent_on_absent = (
        absent["performed"] is True
        and absent["verdict"] == "no-popular-implementation"
        and absent["popular_hit_count"] == 0
        and absent["hit_count"] == 0
    )
    passed = bool(found_known and silent_on_absent)
    return {
        "id": "known-existing-implementation",
        "control_mechanism_id": CONTROL_MECH_ID,
        "known_existing_implementation": CONTROL_KNOWN_IMPL,
        "found_known": found_known,
        "planted_absent_id": PLANTED_ABSENT_ID,
        "silent_on_absent": silent_on_absent,
        "before_absence_claimed": True,
        "passed": passed,
        "present_search": {
            "verdict": present["verdict"],
            "popular_hit_count": present["popular_hit_count"],
            "queries": present["queries"],
        },
        "absent_search": {
            "verdict": absent["verdict"],
            "hit_count": absent["hit_count"],
            "queries": absent["queries"],
        },
        "result": "PASS" if passed else "FAIL",
    }
