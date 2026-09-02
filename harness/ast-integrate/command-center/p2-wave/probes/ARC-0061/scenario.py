"""Both-states + extraction-control runner for the duplicate-plane detector."""
from __future__ import annotations

from typing import Any

import compose
import detector


def both_states() -> dict[str, Any]:
    clean = detector.scan(compose.clean_design())
    planted = detector.scan(compose.planted_design())
    naive = detector.scan(compose.naive_union_design())
    empty = detector.scan(compose.empty_design())

    planted_ids = {f["capability"] for f in planted.get("findings") or []}
    naive_ids = {f["capability"] for f in naive.get("findings") or []}

    planted_fires = (
        planted.get("status") == "DUPLICATE"
        and "authorization" in planted_ids
        and int(planted.get("duplicate_count") or 0) >= 1
        and planted.get("extraction_control_ok") is True
    )
    clean_silent = (
        clean.get("status") == "CLEAN"
        and int(clean.get("duplicate_count") or 0) == 0
        and clean.get("extraction_control_ok") is True
    )
    empty_fails = empty.get("status") == "EXTRACTION-FAILED"
    naive_fires = (
        naive.get("status") == "DUPLICATE"
        and "capability-declaration" in naive_ids
        and int(naive.get("duplicate_count") or 0) >= 1
    )
    ok = planted_fires and clean_silent and empty_fails and naive_fires
    return {
        "ok": ok,
        "clean": clean,
        "planted": planted,
        "naive_union": naive,
        "empty": empty,
        "planted_fires": planted_fires,
        "clean_silent": clean_silent,
        "empty_fails_extraction": empty_fails,
        "naive_union_fires": naive_fires,
        "a9_design_present": compose.source_presence()["A9_DESIGN"],
        "source_presence": compose.source_presence(),
    }
