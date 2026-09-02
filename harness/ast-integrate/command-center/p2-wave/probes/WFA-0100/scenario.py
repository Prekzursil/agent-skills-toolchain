#!/usr/bin/env python3
"""Host pipeline and donor stages for WFA-0100 INSERT splice.

Host is a three-stage linear pipeline. The matching donor is a normalize
stage (document -> document) inserted AFTER ingest and BEFORE extract.
That is an insert, not a replace: host stage count grows by one; every
original host stage stays byte-identical.

Unsatisfiable donor: a vision stage that consumes pixels. The insertion
point only offers document. Must refuse; must not coerce pixels<-document.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

INSERT_INDEX = 1
DONOR_INDEX = 0


def _stage(
    sid: str,
    kind: str,
    input_type: str,
    output_type: str,
    in_port: tuple[str, str],
    out_port: tuple[str, str],
    op: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"op": op, "from": in_port[0], "to": out_port[0]}
    if extra:
        body.update(extra)
    return {
        "id": sid,
        "kind": kind,
        "capability": "pure-transform",
        "input_type": input_type,
        "output_type": output_type,
        "inputs": [{"name": in_port[0], "type": in_port[1]}],
        "outputs": [{"name": out_port[0], "type": out_port[1]}],
        "body": body,
        "source_anchor": f"WFA-0100/fixtures:{sid}",
    }


def host_workflow() -> dict[str, Any]:
    return {
        "id": "wf.host.pipeline-v1",
        "kind": "workflow-ir",
        "licence": "Apache-2.0",
        "version": "1.0.0",
        "source_anchor": "WFA-0100/fixtures:host",
        "entry": [{"name": "raw", "type": "bytes"}],
        "exit": [{"name": "verdict", "type": "boolean"}],
        "stages": [
            _stage(
                "ingest",
                "ingest",
                "bytes",
                "document",
                ("raw", "bytes"),
                ("doc", "document"),
                "parse",
            ),
            _stage(
                "extract",
                "extract",
                "document",
                "number",
                ("doc", "document"),
                ("score", "number"),
                "extract",
                extra={"quality": 0.62},
            ),
            _stage(
                "decide",
                "gate",
                "number",
                "boolean",
                ("score", "number"),
                ("verdict", "boolean"),
                "decide",
                extra={"threshold": 0.35},
            ),
        ],
    }


def matching_donor() -> dict[str, Any]:
    """Single normalize stage: document -> document. Fits between ingest and extract."""
    return {
        "id": "wf.donor.normalize-v1",
        "kind": "workflow-ir",
        "licence": "Apache-2.0",
        "version": "1.0.0",
        "source_anchor": "WFA-0100/fixtures:donor-match",
        "entry": [{"name": "doc", "type": "document"}],
        "exit": [{"name": "doc", "type": "document"}],
        "stages": [
            _stage(
                "normalize",
                "transform",
                "document",
                "document",
                ("doc", "document"),
                ("doc", "document"),
                "normalize",
                extra={"unicode": "NFC"},
            )
        ],
    }


def unsatisfiable_donor() -> dict[str, Any]:
    """Consumes pixels. Insertion point offers document. Must refuse."""
    return {
        "id": "wf.donor.pixels-unsat",
        "kind": "workflow-ir",
        "licence": "Apache-2.0",
        "version": "1.0.0",
        "source_anchor": "WFA-0100/fixtures:donor-unsat",
        "entry": [{"name": "image", "type": "pixels"}],
        "exit": [{"name": "score", "type": "number"}],
        "stages": [
            _stage(
                "classify",
                "vision",
                "pixels",
                "number",
                ("image", "pixels"),
                ("score", "number"),
                "classify_image",
            )
        ],
    }


def successor_mismatch_donor() -> dict[str, Any]:
    """Accepts document but emits pixels. Extract still needs document. Refuse on rewire."""
    return {
        "id": "wf.donor.render-mismatch",
        "kind": "workflow-ir",
        "licence": "Apache-2.0",
        "version": "1.0.0",
        "source_anchor": "WFA-0100/fixtures:donor-succ-mismatch",
        "entry": [{"name": "doc", "type": "document"}],
        "exit": [{"name": "image", "type": "pixels"}],
        "stages": [
            _stage(
                "render",
                "render",
                "document",
                "pixels",
                ("doc", "document"),
                ("image", "pixels"),
                "render",
            )
        ],
    }


def declared_insertion() -> dict[str, Any]:
    host = host_workflow()
    donor = matching_donor()
    return {
        "insert_index": INSERT_INDEX,
        "after_stage_id": host["stages"][INSERT_INDEX - 1]["id"],
        "before_stage_id": host["stages"][INSERT_INDEX]["id"],
        "donor_stage_id": donor["stages"][DONOR_INDEX]["id"],
        "expected_order": ["ingest", "wf.donor.normalize-v1::normalize", "extract", "decide"],
    }


def write_fixtures(directory: Path | None = None) -> dict[str, str]:
    directory = directory or FIX
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "host.json": host_workflow(),
        "donor_match.json": matching_donor(),
        "donor_unsat.json": unsatisfiable_donor(),
        "donor_successor_mismatch.json": successor_mismatch_donor(),
        "declared_insertion.json": declared_insertion(),
    }
    written: dict[str, str] = {}
    for name, doc in files.items():
        path = directory / name
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        written[name] = str(path.relative_to(HERE.parents[3]) if HERE.parents[3] in path.parents else path)
    return written
