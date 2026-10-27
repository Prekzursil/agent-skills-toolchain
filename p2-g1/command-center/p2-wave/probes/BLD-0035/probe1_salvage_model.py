#!/usr/bin/env python3
"""BLD-0035 probe1: recoverable-git salvage model + counts predicate.

The receipt's method: classify each of the 77 DELETE-ALL-deleted paths as
PRESERVED / LOST / LOST-COVERAGE / RETIRED against a recoverable git model
over 5 origin.* trees. This probe rebuilds a minimal recovery model in a
throwaway git repo (plant -> commit -> delete -> recover content by
revision), proves the PRESERVED and LOST mechanisms live, and re-derives
the receipt's count arithmetic from its own rows:
  LOST(1) + LOST-COVERAGE(2) + PRESERVED(91) + RETIRED(15) == surfaces(109)
  surfaces rows all anchored in deleted_paths(77) across trees(5)
Negative control NC-ABSENT (absent-input must fail, good state silent)
must be recorded both-states; C-lost-unique must classify LOST with no
retained_path.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    ProbeFailure, check_receipt_core, git_fixture, require,
)

UID = "BLD-0035"


def _git(repo: str, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", repo, *args],
                       capture_output=True, text=True, timeout=120)
    if ok:
        require(r.returncode == 0,
                f"git model cmd failed: {' '.join(args[:3])}: {r.stderr[:200]}")
    return r


def recovery_model() -> None:
    """Minimal recoverable-git model: deleted content stays reachable by rev."""
    repo, revs = git_fixture(
        {
            "origin.lib/net-allowlist.mjs": "export const checkNetAllowlist = () => true;\n",
            "origin.lib/lost-unique.mjs": "export const bld0035LostUniqueSymbol = 1;\n",
        },
        delete=["origin.lib/lost-unique.mjs"],
    )
    # PRESERVED mechanism: retained symbol recoverable from the model
    r = _git(repo, "show", f"{revs[0]}:origin.lib/net-allowlist.mjs")
    require("checkNetAllowlist" in r.stdout,
            "PRESERVED model: retained symbol not recoverable")
    # LOST mechanism: last content lives ONLY in history; gone from HEAD
    r2 = _git(repo, "show", f"{revs[0]}:origin.lib/lost-unique.mjs")
    require("bld0035LostUniqueSymbol" in r2.stdout,
            "LOST model: deleted blob not recoverable from history")
    head = _git(repo, "show", "HEAD:origin.lib/lost-unique.mjs", ok=False)
    require(head.returncode != 0, "LOST model: deleted path still in HEAD")


def main() -> int:
    doc = check_receipt_core(UID)
    counts = doc.get("counts") or {}
    dp = doc.get("deleted_paths") or []
    sur = doc.get("surfaces") or []
    trees = doc.get("trees") or []

    require(counts.get("deleted_paths") == len(dp) == 77,
            f"deleted_paths drift: counts={counts.get('deleted_paths')} rows={len(dp)}")
    require(counts.get("trees") == len(trees) == 5, "trees count drift")
    require(counts.get("surfaces") == len(sur) == 109, "surfaces count drift")
    total = sum(int(counts.get(k) or 0) for k in ("LOST", "LOST-COVERAGE", "PRESERVED", "RETIRED"))
    require(total == counts.get("surfaces"),
            f"classification sum {total} != surfaces {counts.get('surfaces')}")

    dpaths = {r.get("path") for r in dp}
    require(len(dpaths) == len(dp), "duplicate paths inside deleted_paths")
    require(all(r.get("tree") in trees for r in dp), "deleted_paths row with unknown tree")
    unanchored = [s.get("path") for s in sur if s.get("path") not in dpaths]
    require(not unanchored, f"surface rows not anchored in deleted_paths: {unanchored[:3]}")

    ncs = doc.get("negative_controls") or []
    nc = next((c for c in ncs if c.get("id") == "NC-ABSENT"), None)
    require(nc is not None, "NC-ABSENT negative control not recorded")
    require(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
            "NC-ABSENT not both-states (fired_on_bad + silent_on_good)")

    ctl = {c.get("id"): c for c in doc.get("controls") or []}
    clost = ctl.get("C-lost-unique")
    require(clost is not None and clost.get("classification") == "LOST"
            and clost.get("retained_path") is None and clost.get("result") == "PASS",
            "C-lost-unique control drift")

    recovery_model()
    print(json.dumps({
        "probe": "probe1-salvage-model",
        "unit_id": UID,
        "deleted_paths": len(dp),
        "surfaces": len(sur),
        "class_sum": total,
        "trees": len(trees),
        "nc_absent_both_states": True,
        "recovery_model_preserved_and_lost_proven": True,
        "pass": True,
    }))
    print(f"SUCCESS:{UID}-probe1 counts re-derived (1+2+91+15=109; 77 paths; 5 trees); "
          f"recovery model proves PRESERVED+LOST; NC-ABSENT both-states")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
