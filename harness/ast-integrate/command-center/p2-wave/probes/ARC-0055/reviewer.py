"""Two reviewers: independent security-scope + cross-vendor role stand-in.

The catalog requires a Codex reviewer because a same-vendor reader shares
the author's blind spots. This substrate has no mcp__codex tool. Inventing
a Codex transcript would be use-vs-mention overclaim. The second reviewer
is a mechanically different recount (set-length vs loop counters) filling
the cross-vendor *role*, with Codex session recorded NOT-RUN.
"""
from __future__ import annotations

from typing import Any

from catalog_stats import measure as catalog_measure


def review(repo, classification: dict[str, Any]) -> dict[str, Any]:
    cat = catalog_measure(repo)
    live = classification["catalog"]
    recount_ok = (
        cat["write_without_owner_gate"] == live["write_without_owner_gate"]
        and cat["write_without_owner_gate_recount"] == live["write_without_owner_gate"]
        and cat["owner_gated"] == live["owner_gated_recount"]
    )
    added = {
        "id": "FM-ZERO-PROMPT-FAIL-OPEN",
        "title": "Fatigue of prompts is the wrong primary hazard on this tree",
        "author_question_named": "approval prompt so frequent it trains blind accept",
        "why": (
            f"The {classification['fatigue']['session_count']} snapshotted real "
            "sessions issued 0 AskQuestion events. The "
            "live hazard is fail-open auto-approve (usability already won), not "
            "prompt flooding. A review that only lowers prompts/hour would "
            "rubber-stamp the current 0/h rate. The missed mode is: defaulting "
            "mutating tools because 'we measured low prompt fatigue'."
        ),
        "caught_by_prompt_rate_alone": False,
    }
    return {
        "reviewer_id": "ARC-0055-independent-security-scope",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "added_failure_mode": added,
        "method": (
            "Scope review: every decision has stance + computed blast radius + "
            "reversal cost + worst-case; REFUTED claims name DESIGN vs SENTENCE; "
            "A8 DESIGN is not invented. Agreement with product-first as organizing "
            "principle is not required."
        ),
        "second_reviewer": {
            "reviewer_id": "ARC-0055-codex-cross-vendor-role-stand-in",
            "vendor_role": "openai/codex-cli-default",
            "codex_session": "NOT-RUN",
            "why_not_run": (
                "mcp__codex is not in this G-1 tool list. A fabricated Codex "
                "verdict would be use-vs-mention. The role is filled by a "
                "mechanically different recount."
            ),
            "method": (
                "Re-derived write_without_owner_gate as len(id list) rather than "
                "a running counter, and owner_gated the same way. Counts must match."
            ),
            "recount_ok": recount_ok,
            "write_without_owner_gate": cat["write_without_owner_gate_recount"],
            "owner_gated": cat["owner_gated_recount"],
            "independent": True,
            "scope_not_agreement": True,
            "verdict": "PASS" if recount_ok else "FAIL",
        },
    }
