"""Shared IMP-0222 cohort parameters. Probes and the receipt emitter import these."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for _root in (REPO / "tools" / "agentspec", REPO / "tools" / "agentrail"):
    _path = str(_root)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from agentrail.runner import (  # noqa: E402
    COMPLETED,
    TIMEOUT,
    TIMEOUT_TYPED,
    CoupledBarrierRunner,
    IsolatedPipelineRunner,
    assert_no_barrier_past_timeout,
    make_cohort,
    summarize,
)

UNIT_ID = "IMP-0222"
SENTINEL = "SUCCESS:IMP-0222"
RECEIPT_REL = "command-center/receipts/IMP-0222.json"
COHORT_N = 50
HANG_AT = 0
TIMEOUT_S = 0.40
WORK_S = 0.001
HANG_S = 1.20
SLACK_S = 0.35
HANG_ID = f"U-{HANG_AT:04d}"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _units(*, hang: bool):
    return make_cohort(
        COHORT_N,
        hang_at=HANG_AT if hang else None,
        timeout_s=TIMEOUT_S,
        work_s=WORK_S,
        hang_s=HANG_S,
    )


def run_isolated(*, hang: bool):
    return IsolatedPipelineRunner().run_cohort(_units(hang=hang))


def run_coupled_hang():
    return CoupledBarrierRunner().run_cohort(_units(hang=True))


def load_receipt() -> dict:
    path = REPO / RECEIPT_REL
    if not path.is_file() or path.stat().st_size < 200:
        raise FileNotFoundError(f"receipt missing: {RECEIPT_REL}")
    blob = path.read_text(encoding="utf-8")
    doc = json.loads(blob)
    if SENTINEL not in blob:
        raise ValueError("sentinel absent from receipt")
    if doc.get("unit_id") != UNIT_ID:
        raise ValueError(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise ValueError(f"self-declared {doc.get('state')}")
    return doc
