#!/usr/bin/env python3
"""G5b: find the REAL edit-checkpoints index. Round 1 looked at the root and wrongly
reported 'producer wrote no index'; the index lives at CKPT_ROOT/<session_id>/index.ndjson.
My first pass repeated that error, so this probe searches per-session subdirs.

Control: the search must FIND something under at least one candidate root, or it reports
SEARCH-FAILED rather than 'absent'. An absence from a search that has never found anything
is a detector reading, not a measurement.
"""

import json
import os
import sys
from datetime import datetime, timezone

ROOTS = [
    r"C:\Users\Prekzursil\.claude\edit-checkpoints",
    r"C:\Users\Prekzursil\.claude\checkpoints",
    r"C:\Users\Prekzursil\.claude\hooks\edit-checkpoints",
    r"C:\Users\Prekzursil\.claude\.edit-checkpoints",
]


def main():
    res = {"roots": {}, "index_files": [], "total_records": 0}
    found_any_dir = False
    for r in ROOTS:
        info = {"exists": os.path.isdir(r)}
        if info["exists"]:
            found_any_dir = True
            try:
                subs = sorted(os.listdir(r))
                info["entries"] = len(subs)
                info["sample"] = subs[:5]
            except Exception as e:  # noqa: BLE001
                info["error"] = f"{type(e).__name__}"
        res["roots"][r] = info

    # walk for index.ndjson under every existing root
    newest_ts = None
    for r in ROOTS:
        if not os.path.isdir(r):
            continue
        for dirpath, _dirnames, filenames in os.walk(r):
            for fn in filenames:
                if fn == "index.ndjson":
                    p = os.path.join(dirpath, fn)
                    try:
                        with open(p, encoding="utf-8", newline="") as f:
                            lines = [x for x in f.read().splitlines() if x.strip()]
                    except Exception as e:  # noqa: BLE001
                        res["index_files"].append(
                            {"path": p, "error": type(e).__name__}
                        )
                        continue
                    mt = os.path.getmtime(p)
                    res["index_files"].append(
                        {
                            "path": p,
                            "records": len(lines),
                            "mtime_utc": datetime.fromtimestamp(
                                mt, timezone.utc
                            ).isoformat(),
                        }
                    )
                    res["total_records"] += len(lines)
                    if newest_ts is None or mt > newest_ts:
                        newest_ts = mt

    res["session_dirs_with_index"] = len(res["index_files"])
    res["newest_index_mtime_utc"] = (
        datetime.fromtimestamp(newest_ts, timezone.utc).isoformat()
        if newest_ts
        else None
    )
    if newest_ts:
        age_days = (datetime.now(timezone.utc).timestamp() - newest_ts) / 86400.0
        res["newest_index_age_days"] = round(age_days, 2)

    # git stash refs the producer creates
    res["control_search_found_a_root"] = found_any_dir
    res["verdict"] = (
        "SEARCH-FAILED: no candidate root exists; cannot distinguish 'never ran' from 'wrong path'"
        if not found_any_dir
        else (
            "PRODUCER-DARK: roots exist, index frozen"
            if newest_ts
            else "roots exist, no index found"
        )
    )
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
