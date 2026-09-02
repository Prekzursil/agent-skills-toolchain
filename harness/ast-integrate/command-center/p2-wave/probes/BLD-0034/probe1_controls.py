#!/usr/bin/env python3
"""Named probe 1: four catalog controls against a fresh fixture estate."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bld0034-p1-") as tmp:
        meta = F.build(Path(tmp))
        result = F.classify_estate(meta)
        F.assert_controls(result, Path(meta["estate"]))
        objs = result["objects"]
        squash = next(o for o in objs if o.get("name") == "squash-feature")
        print("twin=SAFE-TO-RETIRE empty_diff=True")
        print(
            "squash-feature=SAFE-TO-RETIRE "
            f"ancestry_ahead={squash['ancestry']['ahead_count']} "
            f"classified_unmerged={squash['classified_unmerged']}"
        )
        print("stash_identical=STASH-NO-UNIQUE-CONTENT")
        print("stash_push_untracked=STASH-PUSH-SAVED-NOTHING")
        print("foreign=FOREIGN-WORKTREE")
        print("unique-work=RETAIN")
        print("deletions_performed=false")
        print("SUCCESS:BLD-0034-probe1 catalog controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
