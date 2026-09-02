#!/usr/bin/env python3
"""Certification path with the independent-confirmation hook bound in front.

A workflow is not certified until admit() returns ACCEPT. The hook is a
call, not a comment: certify() cannot emit CERTIFIED if the gate rejects.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from confirm_hook import VERDICT_ACCEPT, GateResult, admit

STAGES_HOOK = "independent_confirmation_hook"
STAGES_DIGEST = "digest_read"
STAGES_EMIT = "emit_certificate"


def certify(
    workflow: dict[str, Any],
    confirmation: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    """Run certification. The confirmation hook always runs first."""
    stages = [STAGES_HOOK]
    gate: GateResult = admit(confirmation, workflow, Path(root))
    if gate.verdict != VERDICT_ACCEPT:
        return {
            "certified": False,
            "status": "REJECTED",
            "blocked_by": STAGES_HOOK,
            "reason": gate.reason,
            "stages_run": stages,
            "digest_read": gate.digest_read,
            "digest_accepted": gate.digest_accepted,
            "gate": _gate_public(gate),
        }
    if gate.digest_read:
        stages.append(STAGES_DIGEST)
    stages.append(STAGES_EMIT)
    cert = {
        "certified": True,
        "status": "CERTIFIED",
        "workflow_id": workflow.get("workflow_id"),
        "confirmer_id": confirmation.get("confirmer_id")
        or confirmation.get("confirmer_id"),
        "reason": gate.reason,
        "stages_run": stages,
        "digest_read": gate.digest_read,
        "digest_accepted": False,
        "recomputed": gate.recomputed,
        "gate": _gate_public(gate),
    }
    return cert


def _gate_public(gate: GateResult) -> dict[str, Any]:
    return {
        "verdict": gate.verdict,
        "reason": gate.reason,
        "trace": list(gate.trace),
        "paths_existing": list(gate.paths_existing),
        "paths_missing": list(gate.paths_missing),
        "raw_citations": list(gate.raw_citations),
        "digest_read": gate.digest_read,
        "digest_accepted": gate.digest_accepted,
        "independent": gate.independent,
        "recomputed": gate.recomputed,
    }


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="IMP-0202 certification path")
    p.add_argument("--root", required=True)
    p.add_argument("--workflow", required=True)
    p.add_argument("--confirmation", required=True)
    args = p.parse_args()
    root = Path(args.root)
    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    confirmation = json.loads(Path(args.confirmation).read_text(encoding="utf-8"))
    out = certify(workflow, confirmation, root)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out.get("certified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
