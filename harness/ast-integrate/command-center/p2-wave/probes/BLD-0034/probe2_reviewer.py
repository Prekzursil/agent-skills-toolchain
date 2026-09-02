"""Named probe 2: independent reviewer re-diffs two SAFE-TO-RETIRE verdicts.

Instrument is two-dot `git diff --exit-code` (not the classifier's ls-tree map).
Rebuilds fixtures; does not trust classify.verdict() for the empty-diff proof.
Schema check uses an on-disk RefResolver (no HTTPS $ref).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import fixtures as F  # noqa: E402
import schema_validate as SV  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/BLD-0034.json"
SENTINEL = "SUCCESS:BLD-0034"


def two_dot_empty(repo: Path, retained: str, ref: str) -> tuple[bool, str]:
    p = C.git(repo, "diff", "--stat", retained, ref, check=False)
    stat = (p.stdout or "").strip() or "(empty)"
    q = C.git(repo, "diff", "--exit-code", retained, ref, check=False)
    return q.returncode == 0, stat


def fail(msg: str) -> int:
    print(msg)
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("FAILED:BLD-0034-probe2 receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("FAILED:BLD-0034-probe2 sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "BLD-0034":
        return fail(f"FAILED:BLD-0034-probe2 unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"FAILED:BLD-0034-probe2 self-declared {doc.get('state')}")

    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    deletions = report.get("deletions_performed", doc.get("deletions_performed"))
    owner = report.get("owner_decision", doc.get("owner_decision"))
    if deletions is not False:
        return fail("FAILED:BLD-0034-probe2 deletions_performed must be false")
    if owner != "NOT-PRESENTED":
        return fail("FAILED:BLD-0034-probe2 owner decision was presented")
    if report.get("kind") != "salvage-closure":
        return fail("FAILED:BLD-0034-probe2 report.kind is not salvage-closure")

    try:
        SV.assert_not_vacuous()
    except SystemExit:
        return fail("FAILED:BLD-0034-probe2 schema vacuous")
    errs = SV.error_list(doc)
    if errs:
        print("FAILED:BLD-0034-probe2 schema-invalid")
        for line in errs[:16]:
            print(" ", line)
        return 1

    reviewer = doc.get("reviewer") or {}
    scope_ok = report.get("scope_not_agreement")
    if scope_ok is None:
        scope_ok = reviewer.get("scope_not_agreement")
    if not reviewer.get("independent") or scope_ok is not True:
        return fail("FAILED:BLD-0034-probe2 reviewer is not independent/scope-not-agreement")
    rechecked = report.get("reverified_safe_to_retire") or reviewer.get(
        "reverified_safe_to_retire"
    ) or []
    if len(rechecked) < 2:
        return fail("FAILED:BLD-0034-probe2 need two independent SAFE-TO-RETIRE re-diffs")

    names = [r.get("name") for r in rechecked[:2]]
    with tempfile.TemporaryDirectory(prefix="bld0034-p2-") as tmp:
        meta = F.build(Path(tmp))
        estate = Path(meta["estate"])
        for name in names:
            empty, stat = two_dot_empty(estate, "main", name)
            print(f"reviewer git-diff main {name} empty={empty} stat={stat!r}")
            if not empty:
                return fail(f"FAILED:BLD-0034-probe2 {name} two-dot diff not empty")
            ahead = C.git(
                estate, "rev-list", "--count", f"main..{name}", check=False
            )
            n = int((ahead.stdout or "0").strip() or "0")
            print(f"reviewer ancestry main..{name} ahead_count={n}")

        squash_empty, _ = two_dot_empty(estate, "main", "squash-feature")
        squash_ahead = int(
            C.git(estate, "rev-list", "--count", "main..squash-feature").stdout.strip()
        )
        if not squash_empty or squash_ahead < 1:
            return fail("FAILED:BLD-0034-probe2 squash control not (AHEAD + empty diff)")

        unique_empty, ustat = two_dot_empty(estate, "main", "unique-work")
        print(f"reviewer unique-work empty={unique_empty} stat={ustat!r}")
        if unique_empty:
            return fail("FAILED:BLD-0034-probe2 unique-work wrongly empty (detector blind)")

    live = REPO / ".git"
    if live.exists():
        print("NOTE:BLD-0034-probe2 this worktree now has .git; census must not overclaim")
    else:
        print("live_worktree_git=absent (honest)")

    print("schema=valid (disk RefResolver, garbage rejected)")
    print("owner_decision=NOT-PRESENTED deletions_performed=false")
    print("SUCCESS:BLD-0034-probe2 independent SAFE-TO-RETIRE re-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
