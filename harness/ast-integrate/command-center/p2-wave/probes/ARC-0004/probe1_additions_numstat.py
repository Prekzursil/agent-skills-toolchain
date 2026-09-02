#!/usr/bin/env python3
"""Probe 1: three real additions measured with git diff --no-index --numstat."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import curve as C  # noqa: E402
import diffstat as D  # noqa: E402
import estate as E  # noqa: E402

OUT = HERE / "probe1-additions.raw.json"
KIND_TO_TEST = {
    "skill": "skill",
    "workflow_blueprint": "workflow_blueprint",
    "council_preset": "council_preset",
}


def main() -> int:
    snaps = E.build_snapshots()
    t0 = snaps["t0"]
    labels = [
        ("skill", snaps["t1"], E.ADDITIONS[0]),
        ("workflow_blueprint", snaps["t2"], E.ADDITIONS[1]),
        ("council_preset", snaps["t3"], E.ADDITIONS[2]),
    ]
    prev = t0
    additions = []
    for kind, tree, spec in labels:
        num = D.git_numstat(prev, tree)
        if num["files_touched"] < 1 or num["review_surface_lines"] < 1:
            print("FAILED:ARC-0004-probe1 empty numstat")
            return 1
        additions.append(
            {
                "kind": KIND_TO_TEST[kind],
                "id": spec["id"],
                "path": spec["rel"],
                "files_touched": num["files_touched"],
                "lines_inserted": num["lines_inserted"],
                "lines_deleted": num["lines_deleted"],
                "review_surface_lines": num["review_surface_lines"],
                "paths": [r["path"] for r in num["rows"]],
                "numstat_rows": num["rows"],
                "raw_numstat": num["raw"],
            }
        )
        prev = tree

    headline = D.git_numstat(t0, snaps["t3"])
    same = D.git_numstat(t0, t0)
    if same["files_touched"] != 0 or same["review_surface_lines"] != 0:
        print("FAILED:ARC-0004-probe1 t0-vs-t0 not silent")
        return 1
    if headline["files_touched"] < 1 or headline["review_surface_lines"] < 1:
        print("FAILED:ARC-0004-probe1 t0-vs-t3 empty (bad-state detector silent)")
        return 1
    c0 = C.snapshot_curve(t0)
    c3 = C.snapshot_curve(snaps["t3"])
    if c0["capability_count"] < 3 or c3["capability_count"] != c0["capability_count"] + 3:
        print("FAILED:ARC-0004-probe1 capability count")
        return 1
    if c0["bytes_total"] < 1 or c3["bytes_total"] <= c0["bytes_total"]:
        print("FAILED:ARC-0004-probe1 bytes did not grow")
        return 1

    payload = {
        "probe": "probe1-additions-numstat",
        "tool": "git-diff-no-index-numstat",
        "host_candidates": E.host_candidates(),
        "t0": str(t0),
        "t3": str(snaps["t3"]),
        "additions": additions,
        "headline_t0_t3": {
            "files_touched": headline["files_touched"],
            "lines_inserted": headline["lines_inserted"],
            "lines_deleted": headline["lines_deleted"],
            "review_surface_lines": headline["review_surface_lines"],
            "raw_numstat": headline["raw"],
        },
        "totals": {
            "files_touched": sum(a["files_touched"] for a in additions),
            "lines_inserted": sum(a["lines_inserted"] for a in additions),
            "lines_deleted": sum(a["lines_deleted"] for a in additions),
            "review_surface_lines": sum(a["review_surface_lines"] for a in additions),
        },
        "curve_t0": c0,
        "curve_t3": c3,
        "tokenizer": C.tokenizer_spec(),
        "both_states": {
            "good_t0_t3_files": headline["files_touched"],
            "good_t0_t3_review": headline["review_surface_lines"],
            "bad_t0_t0_files": same["files_touched"],
            "bad_t0_t0_review": same["review_surface_lines"],
            "fired_on_empty": True,
            "silent_on_identical": True,
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tot = payload["totals"]
    print(
        "additions=3"
        + f" files_touched={tot['files_touched']}"
        + f" ins={tot['lines_inserted']}"
        + f" del={tot['lines_deleted']}"
        + f" review={tot['review_surface_lines']}"
        + f" t0_t3_files={headline['files_touched']}"
        + f" t0_t3_review={headline['review_surface_lines']}"
        + f" t0_caps={c0['capability_count']}"
        + f" t3_caps={c3['capability_count']}"
        + f" t0_tokens={c0['a1_always_loaded_tokens']}"
        + f" t3_tokens={c3['a1_always_loaded_tokens']}"
        + f" tokenizer={c0['tokenizer']['id']}"
        + " git_add=False git_commit=False"
    )
    print("SUCCESS:ARC-0004-probe1 three real additions via git numstat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
