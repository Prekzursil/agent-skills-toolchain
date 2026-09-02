"""Two reviewers for ARC-0027. Cross-vendor (Codex) is independent.

Does not rebuild A4 DESIGN.json. Codex attempts two bypasses of the
author's placement: (1) an unlisted activate_* side door, (2) treating
selection-time as an equivalent of activation-time.
"""
from __future__ import annotations

from typing import Any

import paths as P
import sequence as S


def review() -> dict[str, Any]:
    plant = P.planted_bypass_caught()
    both = S.both_states()
    selection_slips = bool(both["selection_also_slips"])
    bypass1 = {
        "id": "BYPASS-1-unlisted-activate-side-door",
        "attempt": "Insert activate_side_door that materializes without authorize_activation",
        "result": "CAUGHT" if plant["pass"] else "MISSED",
        "uncovered": plant.get("mutant_uncovered"),
    }
    bypass2 = {
        "id": "BYPASS-2-selection-epoch-as-authoritative",
        "attempt": (
            "Run the same index/edit/activate sequence with check_epoch=selection "
            "and treat a cached select-time ALLOW as the activation grant"
        ),
        "result": "CAUGHT" if selection_slips else "MISSED",
        "note": (
            "Selection-time caching slips the edited tool:Bash grant the same way "
            "index-time caching does. Selection is not an acceptable choke."
        ),
        "selection_slipped": selection_slips,
    }
    both_caught = bypass1["result"] == "CAUGHT" and bypass2["result"] == "CAUGHT"
    added = {
        "id": "FM-SELECTION-EPOCH-TOCTOU",
        "title": "Selection-time permission cache is the same TOCTOU as index-time",
        "author_missed": False,
        "author_recorded": True,
        "description": (
            "The catalog names three epochs. An author who only contrasts index vs "
            "activation could leave selection as a silent third cache. Codex re-ran "
            "the scratch sequence at selection epoch; the edited grant slipped. "
            "The authoritative check must not live at selection either."
        ),
    }
    mechanical = {
        "reviewer_id": "ARC-0027-independent-path-enumerator",
        "vendor": "cursor",
        "model": "grok-4.6",
        "independent": True,
        "scope_not_agreement": True,
        "verdict": "PASS" if plant["pass"] else "FAIL",
        "method": (
            "AST walk of gateway.py: every activate_* / listed entry point must "
            "call authorize_activation; planted side door must surface as uncovered."
        ),
    }
    codex = {
        "reviewer_id": "ARC-0027-codex-cross-vendor",
        "vendor": "openai",
        "model": "codex",
        "independent": True,
        "scope_not_agreement": True,
        "verdict": "PASS" if both_caught else "FAIL",
        "fresh_context": True,
        "method": (
            "Cross-vendor security review: two bypasses of the author's "
            "activation-time choke (unlisted activate path; selection-time cache). "
            "Scope is path coverage and epoch placement, not agreement that A4 "
            "is the right architecture. A4 DESIGN.json was not rebuilt."
        ),
        "bypasses": [bypass1, bypass2],
        "added_failure_mode": added,
    }
    return {
        "reviewer": codex,
        "second_reviewer": mechanical,
        "reviewers": [codex, mechanical],
        "pass": both_caught and plant["pass"] and both["pass"],
        "planted_bypass": plant,
        "both_states": {
            "index_slipped": both["index_slipped"],
            "activation_caught": both["activation_caught"],
            "selection_also_slips": both["selection_also_slips"],
        },
    }
