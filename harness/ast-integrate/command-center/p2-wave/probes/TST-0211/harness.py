"""Shared TST-0211 fixture: one secret param + one non-secret param."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.checkpoint import (  # noqa: E402
    ParamSpec,
    RuntimeBinding,
    bind_params,
    serialize_checkpoint,
)

UNIT = "TST-0211"
# Planted fake credential. Not a live key. Unique so a byte scan cannot
# confuse it with unrelated tree text.
CANARY = "tst0211-canary-NOT-A-REAL-SECRET-f8e2c91a4b67"
SECRET_REF = "TST0211_CREDENTIAL_SOURCE"
SECRET_PARAM = "api_token"
PLAIN_PARAM = "deploy_region"
PLAIN_VALUE = "eu-west-1"
ROTATED = "tst0211-rotated-NOT-A-REAL-SECRET-aa11bb22cc33"
WORKFLOW_ID = "wf.tst0211.secret-checkpoint"


def specs() -> tuple[ParamSpec, ParamSpec]:
    return (
        ParamSpec(name=SECRET_PARAM, secret=True, secret_ref=SECRET_REF),
        ParamSpec(name=PLAIN_PARAM, secret=False),
    )


def runtime_bindings() -> dict[str, RuntimeBinding]:
    return bind_params(
        specs(),
        {SECRET_PARAM: CANARY, PLAIN_PARAM: PLAIN_VALUE},
        {SECRET_REF: CANARY},
    )


def honest_checkpoint_bytes() -> bytes:
    bindings = runtime_bindings()
    return serialize_checkpoint(
        workflow_id=WORKFLOW_ID,
        completed_unit_ids=("stage.fetch",),
        receipt_hashes={"stage.fetch": "a" * 64},
        open_nodes=("stage.apply",),
        bindings=bindings,
    )


def naive_checkpoint_bytes() -> bytes:
    """Both-states control: dump every binding value, including the secret."""
    bindings = runtime_bindings()
    doc = {
        "format": "naive.checkpoint.control",
        "workflow_id": WORKFLOW_ID,
        "completed_unit_ids": ["stage.fetch"],
        "receipt_hashes": {"stage.fetch": "a" * 64},
        "open_nodes": ["stage.apply"],
        "param_bindings": {
            name: {"kind": "value", "value": b.value} for name, b in bindings.items()
        },
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
