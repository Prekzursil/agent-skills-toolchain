"""Generation-candidate stale check with both states.

A help page is FRESH iff it equals generate_help(entry). Mutating either
side without regenerating MUST be reported STALE. Matching bytes MUST be silent.
"""
from __future__ import annotations

from typing import Any


def generate_help(entry: dict[str, Any]) -> str:
    eid = str(entry.get("id") or "")
    kind = str(entry.get("kind") or "")
    lines = [f"# {eid}", "", f"kind: {kind}", ""]
    stages = entry.get("stages") or []
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            sid = stage.get("id")
            skind = stage.get("kind")
            lines.append(f"stage {sid} ({skind})")
            for item in stage.get("inputs") or []:
                lines.append(f"  in: {item}")
            for item in stage.get("outputs") or []:
                lines.append(f"  out: {item}")
    roles = entry.get("roles")
    if isinstance(roles, list):
        lines.append("roles: " + ", ".join(str(r) for r in roles))
    lines.append("")
    return "\n".join(lines)


def freshness(entry: dict[str, Any], page: str) -> str:
    expected = generate_help(entry)
    if page == expected:
        return "FRESH"
    return "STALE"


def both_states(entry: dict[str, Any]) -> dict[str, Any]:
    good = generate_help(entry)
    bad = good + "hand-edit remainder\n"
    good_verdict = freshness(entry, good)
    bad_verdict = freshness(entry, bad)
    mutated_entry = dict(entry)
    mutated_entry["id"] = str(entry.get("id") or "") + ".mutated"
    stale_after_registry_change = freshness(mutated_entry, good)
    return {
        "silent_on_match": good_verdict == "FRESH",
        "fires_on_page_edit": bad_verdict == "STALE",
        "fires_on_registry_change": stale_after_registry_change == "STALE",
        "good_verdict": good_verdict,
        "page_edit_verdict": bad_verdict,
        "registry_change_verdict": stale_after_registry_change,
        "check": (
            "Regenerate help from the typed registry entry and byte-compare. "
            "Mismatch is STALE, not a legitimate hand-edit."
        ),
    }
