"""IMP-0145 fixture workflow: ten units, frozen param bindings, 40% kill point."""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.resume import Workflow, workflow_from_ids  # noqa: E402

UNIT_IDS = [f"U{i:02d}" for i in range(1, 11)]
PARAM_BINDINGS = {
    "dataset": "hermetic-fixture",
    "mode": "resume-parity",
    "seed": 145,
}
WORKFLOW_ID = "wf.imp0145.resume-state"
SPEC_VERSION = "1"


def workflow() -> Workflow:
    return workflow_from_ids(
        UNIT_IDS,
        workflow_id=WORKFLOW_ID,
        spec_version=SPEC_VERSION,
        param_bindings=PARAM_BINDINGS,
    )


def kill_after_units(n_units: int | None = None) -> int:
    """Floor of 40% of the workflow. For 10 units this is 4."""
    total = n_units if n_units is not None else len(UNIT_IDS)
    killed = math.floor(total * 0.4)
    if killed < 1:
        raise ValueError("workflow too small to kill at 40%")
    return killed
