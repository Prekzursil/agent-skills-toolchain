"""IMP-0209 planted corpus and runtime entry."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    return HERE.parents[4]


REPO = _repo()
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foundry.oracle import check_runtime_receipt  # noqa: E402
from foundry.scout import (  # noqa: E402
    SOURCE_CLASSES,
    WORKFLOW_ID,
    WORKFLOW_PATH,
    run_via_runtime,
)

INCUMBENT_ID = "incumbent-rtv"
KNOWN_GOAL = {
    "goal": "retrieve documents and verify their claims against sources",
    "required_capabilities": ["retrieve", "verify"],
}
ABSENT_GOAL = {
    "goal": "compile LaTeX to PDF with a bibliography — no catalog workflow covers this",
    "required_capabilities": ["latex-build", "bibtex"],
}


def scout(request: dict) -> tuple[dict, dict]:
    return run_via_runtime(request)


def oracle(receipt: dict) -> dict:
    return check_runtime_receipt(
        receipt, expected_workflow_id=WORKFLOW_ID, min_stages=9
    )
