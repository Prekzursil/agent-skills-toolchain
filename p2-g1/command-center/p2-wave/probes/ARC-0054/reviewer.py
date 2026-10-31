"""Independent reliability reviewer for ARC-0054.

Adds one failure mode the author's error-string predicate misses:
a three-part error whose NEXT path does not exist.
Does NOT certify the 47-class enumeration complete; the cited prompt
file is absent.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

ADDED_MODE = {
    "id": "FM-NEXT-ACTION-UNREACHABLE",
    "title": "Error names a next action whose path does not exist",
    "author_missed": True,
    "caught_by_author_error_predicate": False,
    "predicate": "next_action_reachable",
    "artifact_class": "error-string",
    "seeded_classes": ["green-not-live", "overclaim", "use-vs-mention"],
    "description": (
        "error_names_next_action greets any command-like NEXT line as a pass. "
        "NEXT: python3 command-center/phase3/A8/__arc0054_trap_absent_fixture__.json "
        "satisfies that regex while the fixture path is guaranteed absent on any "
        "worktree, so the owner still has no executable next action. "
        "Shape is not reachability."
    ),
    "required_followup": (
        "Resolve every NEXT path against the worktree (or a documented "
        "external command allowlist) before counting the error contract as met."
    ),
}


def seeded_status() -> dict:
    sibling = HERE.parent / "ARC-0005" / "seeded_classes.py"
    names: list[str] = []
    source_status = "ABSENT"
    citation = (
        "command-center/WORK-UNIT-CATALOG.json ARC-0054.inputs cites "
        "_USER-PROMPTS.md:11300-11347; that file is not on this worktree"
    )
    if sibling.is_file():
        ns: dict = {}
        exec(sibling.read_text(encoding="utf-8"), ns)
        classes = ns.get("CLASSES") or []
        names = [str(c.get("id")) for c in classes if isinstance(c, dict)]
        source_status = "RECONSTRUCTED-FROM-ARC-0005"
    return {
        "count": len(names) if names else 47,
        "source_status": source_status,
        "source_citation": citation,
        "ids": names,
    }


def review() -> dict:
    seeded = seeded_status()
    return {
        "reviewer_id": "ARC-0054-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-NEXT-ACTION-UNREACHABLE, which the author's error-shape "
            "predicate misses."
        ),
        "added_failure_mode": ADDED_MODE,
        "seeded_classes": seeded,
        "method": (
            "Reviewed the five catalog-named UX modes against live artifacts: "
            "the G-1 measure error printer, A1 DESIGN workflow stopping, the "
            "2007-row work-unit catalog, a dry-run/apply pair on that workflow, "
            "and repair receipts. Agreement with 'A8 is the right organizing "
            "principle' is not required for PASS; scope is: observable "
            "predicates, both-states, silent-repair NO-OP, one missed mode."
        ),
    }
