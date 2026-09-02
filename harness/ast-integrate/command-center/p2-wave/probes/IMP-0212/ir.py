"""Shared constants and IR helpers for the IMP-0212 workflow-forge."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

ALLOWED_TOOLS = frozenset(
    {
        "repo-scan",
        "json-write",
        "json-transform",
        "contract-gate",
        "stage-splice",
        "compose",
        "hermetic-emulate",
        "receipt-emit",
    }
)

EMULATABLE_CAPABILITIES = frozenset(
    {
        "read-local",
        "write-local",
        "transform-json",
        "validate-schema",
        "simulate-hermetic",
    }
)

UNEMULATABLE_CAPABILITIES = frozenset(
    {
        "live-network",
        "live-spawn",
        "paid-model-call",
    }
)

OPERATOR_RANK = {
    "ADOPT": 0,
    "ADAPT": 1,
    "MERGE": 2,
    "COMPOSE": 3,
    "BUILD": 4,
}

UNIT = "IMP-0212"


def clone(doc: Any) -> Any:
    return deepcopy(doc)


def fingerprint(wf: dict) -> str:
    """Canonical stage-graph digest. Used to prove MERGE is not a silent parent copy."""
    core = {
        "id": wf.get("id"),
        "stages": [
            {
                "id": s.get("id"),
                "kind": s.get("kind"),
                "inputs": list(s.get("inputs") or []),
                "outputs": list(s.get("outputs") or []),
                "tool": s.get("tool"),
                "capability": s.get("capability"),
            }
            for s in (wf.get("stages") or [])
        ],
        "initial_inputs": list(wf.get("initial_inputs") or []),
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
