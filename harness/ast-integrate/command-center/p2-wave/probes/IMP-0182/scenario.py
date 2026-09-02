#!/usr/bin/env python3
"""Host, matching donor, and contract-mismatch donor for IMP-0182.

Linear three-stage pipelines. The splice replaces the middle (extract) slot.
Matching donor: same I/O types, higher f1, different body (not a no-op).
Mismatch donor: middle stage consumes pixels, which the predecessor does not
produce — a neighbour-contract failure, not a performance failure.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

HOST_INDEX = 1
DONOR_INDEX = 1


def _stage(
    sid: str,
    kind: str,
    inputs: list[tuple[str, str]],
    outputs: list[tuple[str, str]],
    op: str,
    *,
    quality: float | None = None,
    threshold: float | None = None,
    metric: str | None = None,
    score: float | None = None,
    run_id: str | None = None,
    capability: str = "pure-transform",
) -> dict[str, Any]:
    body: dict[str, Any] = {"op": op, "from": inputs[0][0], "to": outputs[0][0]}
    if quality is not None:
        body["quality"] = quality
    if threshold is not None:
        body["threshold"] = threshold
    stage: dict[str, Any] = {
        "id": sid,
        "kind": kind,
        "capability": capability,
        "inputs": [{"name": n, "type": t} for n, t in inputs],
        "outputs": [{"name": n, "type": t} for n, t in outputs],
        "body": body,
        "source_anchor": f"IMP-0182/fixtures:{sid}",
    }
    if metric is not None and score is not None:
        stage["performance"] = {
            "metric": metric,
            "score": score,
            "benchmark_run_id": run_id or f"bench-{sid}",
        }
    return stage


def host_workflow() -> dict[str, Any]:
    return {
        "id": "wf.host.extract-v1",
        "licence": "Apache-2.0",
        "version": "1.0.0",
        "entry": [{"name": "raw", "type": "bytes"}],
        "exit": [{"name": "verdict", "type": "boolean"}],
        "stages": [
            _stage(
                "ingest",
                "ingest",
                [("raw", "bytes")],
                [("doc", "document")],
                "parse",
                metric="latency_ms",
                score=12.0,
                run_id="host-ingest-1",
            ),
            _stage(
                "extract",
                "extract",
                [("doc", "document")],
                [("score", "number")],
                "extract",
                quality=0.62,
                metric="f1",
                score=0.62,
                run_id="host-extract-1",
            ),
            _stage(
                "decide",
                "gate",
                [("score", "number")],
                [("verdict", "boolean")],
                "decide",
                threshold=0.35,
                metric="accuracy",
                score=0.71,
                run_id="host-decide-1",
                capability="gate",
            ),
        ],
    }


def matching_donor() -> dict[str, Any]:
    """Better extract (f1 0.88) with the same neighbour contract as host.extract."""
    return {
        "id": "wf.donor.extract-v2",
        "licence": "Apache-2.0",
        "version": "2.0.0",
        "entry": [{"name": "raw", "type": "bytes"}],
        "exit": [{"name": "verdict", "type": "boolean"}],
        "stages": [
            _stage(
                "ingest",
                "ingest",
                [("raw", "bytes")],
                [("doc", "document")],
                "parse",
                metric="latency_ms",
                score=9.0,
                run_id="donor-ingest-1",
            ),
            _stage(
                "extract_v2",
                "extract",
                [("doc", "document")],
                [("score", "number")],
                "extract",
                quality=0.88,
                metric="f1",
                score=0.88,
                run_id="donor-extract-2",
            ),
            _stage(
                "decide",
                "gate",
                [("score", "number")],
                [("verdict", "boolean")],
                "decide",
                threshold=0.40,
                metric="accuracy",
                score=0.80,
                run_id="donor-decide-1",
                capability="gate",
            ),
        ],
    }


def mismatch_donor() -> dict[str, Any]:
    """Middle stage consumes pixels. Predecessor emits document. Must refuse."""
    donor = matching_donor()
    donor["id"] = "wf.donor.pixels-mismatch"
    donor["stages"][1] = _stage(
        "classify",
        "vision",
        [("image", "pixels")],
        [("score", "number")],
        "classify_image",
        metric="f1",
        score=0.99,
        run_id="donor-classify-1",
        capability="pure-transform",
    )
    return donor


def successor_mismatch_donor() -> dict[str, Any]:
    """Middle stage emits pixels. Successor requires number. Must refuse."""
    donor = matching_donor()
    donor["id"] = "wf.donor.successor-mismatch"
    donor["stages"][1] = _stage(
        "render",
        "render",
        [("doc", "document")],
        [("image", "pixels")],
        "extract",
        quality=0.91,
        metric="f1",
        score=0.91,
        run_id="donor-render-1",
    )
    return donor


def initial_env() -> dict[str, Any]:
    return {"raw": b"workflow-foundry-splice-corpus-v1"}


def write_fixtures(directory: Path | None = None) -> dict[str, str]:
    directory = directory or FIX
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "host.json": host_workflow(),
        "donor_match.json": matching_donor(),
        "donor_mismatch.json": mismatch_donor(),
        "donor_successor_mismatch.json": successor_mismatch_donor(),
    }
    written: dict[str, str] = {}
    for name, doc in files.items():
        path = directory / name
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        written[name] = str(path)
    return written
