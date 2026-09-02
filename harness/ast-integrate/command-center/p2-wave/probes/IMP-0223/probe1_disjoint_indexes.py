"""Named probe 1: concurrent mutators have disjoint staged sets (computed).

Live-reruns `measure_disjoint_indexes` against a throwaway fixture repo.
Does not mutate the estate checkout.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "gitcrypt-worktree"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "tests"))

from fixtures_lib import create_seeded_repo  # noqa: E402
from gitcrypt_worktree import measure_disjoint_indexes  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0223.json"
UID = "IMP-0223"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0223-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UID:
        print("FAILED:IMP-0223-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0223" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0223-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0223-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0223-p1-") as tmp:
        root = Path(tmp)
        repo = create_seeded_repo(root / "repo")
        measured = measure_disjoint_indexes(repo, root / "worktrees")

    if not measured.get("pass"):
        print("FAILED:IMP-0223-probe1 live disjoint measure")
        print(json.dumps({k: v for k, v in measured.items()}, indent=2)[:4000])
        return 1
    if not measured.get("intersection_empty"):
        print("FAILED:IMP-0223-probe1 intersection not empty", measured.get("intersection"))
        return 1
    if not measured.get("indexes_disjoint"):
        print("FAILED:IMP-0223-probe1 indexes not disjoint")
        return 1
    control = measured.get("contamination_control") or {}
    if not control.get("detected"):
        print("FAILED:IMP-0223-probe1 shared-index control did not fire")
        return 1

    recorded = ((doc.get("evidence_computed") or {}).get("disjoint_indexes") or {})
    if recorded.get("intersection_empty") is not True:
        print("FAILED:IMP-0223-probe1 artifact missing intersection_empty")
        return 1
    if recorded.get("contamination_detected") is not True:
        print("FAILED:IMP-0223-probe1 artifact missing contamination control")
        return 1

    out = {
        "probe": "probe1-disjoint-indexes",
        "unit_id": UID,
        "intersection": measured["intersection"],
        "intersection_empty": True,
        "indexes_disjoint": True,
        "contamination_detected": True,
        "staged_a": measured["shard_a"]["staged"],
        "staged_b": measured["shard_b"]["staged"],
        "index_a": measured["shard_a"]["index"],
        "index_b": measured["shard_b"]["index"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "intersection=[] contamination=True indexes_disjoint=True "
        f"staged_a={measured['shard_a']['staged']} staged_b={measured['shard_b']['staged']}"
    )
    print("SUCCESS:IMP-0223-probe1 concurrent mutators disjoint staged sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
