"""Write command-center/phase3/A6/CLAIM-UNDER-TEST.json.

ARC-0038 still owns DESIGN.json. This extract gives ARC-0041 dossier
anchors without rebuilding A6 (no ADV circle).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/phase3/A6/CLAIM-UNDER-TEST.json"

TRUST_BOUNDARY = (
    "A second vendor's output is untrusted DATA and a prompt-injection "
    "carrier, never instructions; Claude-side agents may read it only "
    "after the A6 quarantine envelope is applied."
)
SANITIZE_WHERE = (
    "Sanitization is on the vendor RETURN path after last-message parse "
    "and before any Claude-side agent reads parsed; it is not the inbound "
    "prompt-file transport."
)
NEVER_FORWARD = (
    "An adapter may NEVER forward credentials, raw tool-permission grants, "
    "hook configuration, or absolute paths into credential stores."
)
SILENT_LOSS = (
    "If parsed is forwarded unsanitized, a role-spoof or instruction-override "
    "in a second-vendor last-message is silently treated as instructions."
)
WRONG_LOCUS = (
    "Sanitization happens at the prompt-file transport because the prompt "
    "body never appears on argv."
)


def claim_doc() -> dict:
    return {
        "adv_rebuild_circle": False,
        "architecture_id": "A6",
        "architecture_class": "cross-vendor-adapter",
        "extract_id": "ARC-0041-claim-under-test",
        "not_arc_0038_design": True,
        "a6_design_json_present": False,
        "role": (
            "ARC-0041 claim-under-test extract; ARC-0038 still owns DESIGN.json"
        ),
        "trust_boundary": TRUST_BOUNDARY,
        "sanitize_where": SANITIZE_WHERE,
        "never_forward": NEVER_FORWARD,
        "silent_unobservability": SILENT_LOSS,
        "wrong_locus_sentence": WRONG_LOCUS,
        "unit_id": "ARC-0041",
        "quarantine_before_claude_side_read": True,
        "never_forward_classes": [
            "credentials",
            "raw-tool-permission-grants",
            "hook-configuration",
            "absolute-paths-into-credential-stores",
        ],
    }


def write_claim(repo: Path | None = None) -> Path:
    root = repo or REPO
    path = root / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(claim_doc(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path
