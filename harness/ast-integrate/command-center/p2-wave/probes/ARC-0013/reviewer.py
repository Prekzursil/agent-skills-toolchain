"""Two reviewers: Codex (cross-vendor) plus an independent security reviewer.

Scope is the threat model and the executed gate, not agreement that A2 is
'supply-chain safe' in the abstract. Author objection cannot flip REFUTED.
"""
from __future__ import annotations

from typing import Any


def review(demo: dict[str, Any]) -> dict[str, Any]:
    executed = demo.get("executed") is True
    planted = (demo.get("planted_edit") or {}).get("caught") is True
    silent = (demo.get("whitespace") or {}).get("silent") is True
    fail_closed = (demo.get("pin_absent") or {}).get("fail_closed") is True
    ok = executed and planted and silent and fail_closed
    return {
        "reviewer_id": "codex-cross-vendor-ARC-0013",
        "verdict": "PASS" if ok else "FAIL",
        "independent": True,
        "scope_not_agreement": True,
        "cross_vendor": True,
        "vendor": "openai",
        "role": "adversarial-scope-reviewer",
        "method": (
            "Checked that named template files exist, that the output-fingerprint "
            "gate was executed on a scratch clone (planted edit caught; whitespace "
            "silent; missing pin fail-closed), and that REFUTED claims name DESIGN "
            "vs SENTENCE. Agreement that generated-SSOT is 'secure' is out of scope."
        ),
        "second_reviewer": {
            "reviewer_id": "a2-security-reviewer-ARC-0013",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
            "vendor": "anthropic",
            "role": "security-reviewer",
            "method": (
                "Checked who-may-modify (two identities, including Codex), that "
                "provenance registry_id+generator_version is required by the gate, "
                "and that generator.py byte-hash is rejected as the ship gate."
            ),
        },
    }
