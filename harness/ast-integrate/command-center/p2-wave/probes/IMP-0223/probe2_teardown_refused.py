"""Named probe 2: teardown refused when content is not proven preserved (both-states).

Signal is teardown refusal (dangerous) vs deletion (harvested). Ancestry is
recorded on a squash-merge+uncommitted remainder and must NOT authorize delete.
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
from gitcrypt_worktree import measure_teardown_both_states  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0223.json"
UID = "IMP-0223"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0223-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0223" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0223-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0223-p2-") as tmp:
        root = Path(tmp)
        repo = create_seeded_repo(root / "repo")
        measured = measure_teardown_both_states(repo, root / "worktrees")

    if not measured.get("pass"):
        print("FAILED:IMP-0223-probe2 live teardown both-states")
        print(json.dumps(measured, indent=2)[:4000])
        return 1

    dangerous = measured["dangerous"]
    squash = measured["squash_unharvested"]
    good = measured["good"]
    if not dangerous.get("refused") or dangerous.get("deleted"):
        print("FAILED:IMP-0223-probe2 dangerous state was not refused")
        return 1
    if not squash.get("refused"):
        print("FAILED:IMP-0223-probe2 squash remainder was not refused")
        return 1
    if not squash.get("naive_ancestry_would_authorize"):
        print("FAILED:IMP-0223-probe2 ancestry mutant did not fire on AHEAD")
        return 1
    if not (squash.get("ancestry") or {}).get("reports_ahead"):
        print("FAILED:IMP-0223-probe2 squash did not report AHEAD")
        return 1
    if (squash.get("ancestry") or {}).get("branch_is_ancestor_of_integration"):
        print("FAILED:IMP-0223-probe2 squash branch is ancestor (unexpected)")
        return 1
    if good.get("refused") or not good.get("deleted"):
        print("FAILED:IMP-0223-probe2 harvested teardown did not delete")
        return 1

    recorded = ((doc.get("evidence_computed") or {}).get("teardown_both_states") or {})
    if recorded.get("dangerous_refused") is not True:
        print("FAILED:IMP-0223-probe2 artifact missing dangerous_refused")
        return 1
    if recorded.get("good_deleted") is not True:
        print("FAILED:IMP-0223-probe2 artifact missing good_deleted")
        return 1
    if recorded.get("squash_reports_ahead") is not True:
        print("FAILED:IMP-0223-probe2 artifact missing squash_reports_ahead")
        return 1
    if recorded.get("ancestry_not_authorization") is not True:
        print("FAILED:IMP-0223-probe2 artifact missing ancestry_not_authorization")
        return 1

    out = {
        "probe": "probe2-teardown-refused",
        "unit_id": UID,
        "dangerous_refused": True,
        "dangerous_deleted": False,
        "squash_reports_ahead": True,
        "naive_ancestry_would_authorize": True,
        "content_refused_unharvested": True,
        "good_deleted": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "dangerous_refused=True squash_ahead=True ancestry_mutant=True "
        "good_deleted=True"
    )
    print("SUCCESS:IMP-0223-probe2 teardown refused unless content proven preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
