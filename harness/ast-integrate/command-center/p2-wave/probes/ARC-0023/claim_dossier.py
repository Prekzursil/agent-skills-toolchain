"""Write command-center/phase3/A3/CLAIM-UNDER-TEST.json.

This is the ARC-0023 claim extract, not ARC-0017 DESIGN.json. It quotes
the live PR-ONLY owner decision and the stopping-condition-13 finding so
the refutation has dossier anchors without rebuilding A3.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = "command-center/phase3/A3/CLAIM-UNDER-TEST.json"

PR_ONLY_LINE = (
    "Release mode is PR-ONLY: propose changes as pull requests, "
    "never a private canary and never a public marketplace release."
)
COND13_FINDING = (
    "program stopping condition 13 (release/canary succeeds) is "
    "unsatisfiable as written under PR-ONLY"
)
CONTROL_PLANE = "the canonical registry index IS the control plane"
SILENT_LOSS = (
    "Public-index correctness is never observed under PR-ONLY because "
    "nothing is ever published; treating the public marketplace as a "
    "live control plane is silent unobservability."
)
SNIPPETS = (PR_ONLY_LINE, COND13_FINDING, CONTROL_PLANE, SILENT_LOSS)


def claim_doc() -> dict:
    return {
        "adv_rebuild_circle": False,
        "architecture_class": "marketplace-first",
        "architecture_id": "A3",
        "control_plane_claim": CONTROL_PLANE,
        "extract_id": "ARC-0023-claim-under-test",
        "local_fixture_observables_without_publish": [
            "install places lockfile-pinned files in a throwaway prefix",
            "upgrade changes the pin and the prefix bytes",
            "rollback restores the previous pin",
            "offline install from export succeeds",
            "missing-blob index fails install",
            "unsigned package is refused",
            "publish_public returns BLOCKED-PR-ONLY",
            "propose_pr leaves the index hash unchanged",
        ],
        "not_arc_0017_design": True,
        "owner_decision_quoted": {
            "decision_line": PR_ONLY_LINE,
            "owner_decisions_md_present": False,
            "requested_path": "command-center/OWNER-DECISIONS.md",
            "source_on_this_tree": (
                "command-center/WORK-UNIT-CATALOG.json owner_questions OQ-3 "
                "answer_detail (OWNER-DECISIONS.md is absent on this worktree)"
            ),
        },
        "public_control_plane_observable_without_publish": False,
        "reachable_under_pr_only": ["pr-diff-index", "local-fixture-lifecycle"],
        "role": (
            "ARC-0023 claim-under-test extract; ARC-0017 still owns DESIGN.json"
        ),
        "silent_unobservability": SILENT_LOSS,
        "stopping_condition_13": {
            "finding": COND13_FINDING,
            "text": "release/canary succeeds",
            "under_pr_only": "UNSATISFIABLE-AS-WRITTEN",
            "why": "PR-ONLY has no canary channel and forbids public marketplace release",
        },
        "unit_id": "ARC-0023",
        "unreachable_under_pr_only": ["private-canary", "public-marketplace"],
    }


def write_claim(repo: Path | None = None) -> Path:
    root = repo or REPO
    path = root / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(claim_doc(), indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    lines = text.splitlines()
    for snippet in SNIPPETS:
        hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
        if len(hits) != 1:
            raise SystemExit(f"FAILED:ARC-0023 claim snippet {snippet!r} hits={hits}")
    return path


if __name__ == "__main__":
    p = write_claim()
    print(f"wrote {OUT} bytes={p.stat().st_size}")
