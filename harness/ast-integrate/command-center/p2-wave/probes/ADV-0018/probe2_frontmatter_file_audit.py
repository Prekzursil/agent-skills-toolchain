#!/usr/bin/env python3
"""Probe 2: file-byte frontmatter audit (superseded_by / valid_as_of).

Mechanically different from probe 1. Does not use topic-search snippets.
Frontmatter is parsed from the note file (or decision-log section bytes).
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
    find_frontmatter,
    run_sweep,
)

ART = REPO / OUT_REL
UNMARKED = "ADV-0018-planted-stale-unmarked"
MARKED = "ADV-0018-planted-stale-marked"
DL_STALE = "DL-0042"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    sweep = run_sweep()
    fm_unmarked = find_frontmatter(sweep, UNMARKED)
    fm_marked = find_frontmatter(sweep, MARKED)
    fm_dl = find_frontmatter(sweep, DL_STALE)
    if fm_unmarked is None:
        return fail(f"{UNMARKED} missing from file-byte frontmatter census")
    if fm_unmarked.get("superseded_by"):
        return fail(f"{UNMARKED} unexpectedly has superseded_by")
    if fm_unmarked.get("from_file_not_snippet") is not True:
        return fail("frontmatter not marked as file-derived")
    if fm_marked is None:
        return fail(f"{MARKED} missing from file-byte frontmatter census")
    if not fm_marked.get("superseded_by"):
        return fail(f"{MARKED} file bytes lack superseded_by")
    if fm_dl is None:
        return fail(f"{DL_STALE} missing from 17-DECISION-LOG.md file parse")
    if not fm_dl.get("superseded_by"):
        return fail(f"{DL_STALE} file section lacks superseded_by")

    unmarked_cls = find_classified(sweep, UNMARKED)
    marked_cls = find_classified(sweep, MARKED)
    dl_cls = find_classified(sweep, DL_STALE)
    if unmarked_cls is None or not unmarked_cls["still_recallable_as_truth"]:
        return fail("unmarked contradicted note not classified still-recallable")
    if marked_cls is None or not marked_cls["is_contradicted"]:
        return fail("marked stale note not contradicted")
    if marked_cls["still_recallable_as_truth"]:
        return fail("marked stale note must not be still-recallable-as-truth")
    if dl_cls is not None and dl_cls["still_recallable_as_truth"]:
        return fail("DL-0042 has superseded_by so must not be unmarked-recallable")

    payload = {
        "probe": "probe2-frontmatter-file-audit",
        "unit_id": UID,
        "pass": True,
        "computed_not_asserted": True,
        "instrument": "file-byte-frontmatter",
        "not_from_search_snippet": True,
        "unmarked_superseded_by": fm_unmarked.get("superseded_by"),
        "marked_superseded_by": fm_marked.get("superseded_by"),
        "dl0042_superseded_by": fm_dl.get("superseded_by"),
        "still_recallable_ids": [c["note_id"] for c in sweep["still_recallable"]],
        "marked_contradicted_ids": [c["note_id"] for c in sweep["marked_contradicted"]],
        "frontmatter_rows": len(sweep["frontmatter_rows"]),
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable {exc}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        audit = doc.get("frontmatter_audit") or {}
        if audit.get("from_file_not_snippet") is not True:
            return fail("artifact frontmatter_audit.from_file_not_snippet is not true")
        still = list(audit.get("still_recallable_ids") or [])
        if not still:
            still = [
                r.get("note_id")
                for r in (doc.get("still_recallable_notes") or [])
                if isinstance(r, dict)
            ]
        if UNMARKED not in still:
            return fail("artifact omitted unmarked still-recallable note")
        if MARKED in still:
            return fail("artifact listed superseded note as still-recallable")

    print(
        "file_frontmatter=True unmarked_pointer=None "
        f"marked_pointer={fm_marked.get('superseded_by')} "
        f"dl0042_pointer={fm_dl.get('superseded_by')}"
    )
    print(f"SUCCESS:{UID}-probe2 file-byte frontmatter audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
