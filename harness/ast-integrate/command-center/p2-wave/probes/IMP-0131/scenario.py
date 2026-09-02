"""Shared fixture for IMP-0131 probes."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parents[3]
SPEC_ROOT = REPO / "tools" / "agentspec"
if str(SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(SPEC_ROOT))

from agentspec.checkpoint import run_workflow  # noqa: E402
from agentspec.spec import HumanCheckpoint  # noqa: E402

PAUSE_TOKEN = "ckpt-imp0131-alpha"
CHECKPOINT_ID = "owner-gate"
PROMPT_REF = "prompt.owner.continue-or-abort"


@dataclass(frozen=True, slots=True)
class WorkUnit:
    """Linear dispatch step for the pause/resume probes (not spec.WorkUnit)."""

    id: str
    payload: str


@dataclass(frozen=True, slots=True)
class Workflow:
    """Linear mix of WorkUnit and HumanCheckpoint in run order."""

    id: str
    nodes: tuple[WorkUnit | HumanCheckpoint, ...]


def sample_workflow(
    *,
    default_if_unanswered: str | None = "approve",
    extra_after: bool = True,
) -> Workflow:
    nodes: list[WorkUnit | HumanCheckpoint] = [
        WorkUnit(id="unit-alpha", payload="alpha-body-v1"),
        WorkUnit(id="unit-beta", payload="beta-body-v1"),
        HumanCheckpoint(
            id=CHECKPOINT_ID,
            prompt_ref=PROMPT_REF,
            allowed_responses=("approve", "abort"),
            default_if_unanswered=default_if_unanswered,
            pause_token=PAUSE_TOKEN,
        ),
    ]
    if extra_after:
        nodes.append(WorkUnit(id="unit-gamma", payload="gamma-body-v1"))
    return Workflow(id="wf-imp0131-checkpoint", nodes=tuple(nodes))


def run_sample(store: Path, **kwargs):
    return run_workflow(sample_workflow(), store, **kwargs)
