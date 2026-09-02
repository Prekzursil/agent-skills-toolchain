#!/usr/bin/env python3
"""Probe 1: parse every job/step, needs-graph vs independent topo, matrix, 60 test stages.

Mechanically independent of probe 2 (runtime API graph / fail-fast). Re-runs
the adapter on live YAML. Does not rewrite the conformance artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import translate  # noqa: E402
from emit_report import (  # noqa: E402
    CONTROL,
    ESTATE,
    OUT,
    SENTINEL,
    graph_proof,
    matrix_proof,
    required_optional_proof,
)
from rebuild_estate import main as rebuild_estate  # noqa: E402

ART = REPO / OUT


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0052-probe1 {msg}")
    return 1


def main() -> int:
    rebuild_estate()
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    g = graph_proof(CONTROL / "needs-dag.yml")
    if not g.get("pass"):
        return fail(f"needs-dag graph {g}")
    m = matrix_proof(CONTROL / "matrix.yml")
    if not m.get("pass"):
        return fail(f"matrix {m}")
    r = required_optional_proof(CONTROL / "required-optional.yml")
    if not r.get("pass"):
        return fail(f"required-optional {r}")

    estate = list(sorted(ESTATE.glob("*.yml")))
    if len(estate) < 7:
        return fail(f"estate yaml count {len(estate)}")
    quality = None
    for path in estate:
        gp = graph_proof(path)
        if not gp.get("pass"):
            return fail(f"estate graph {path.name} {gp}")
        ir = translate(path, REPO, "probe1")
        if path.name == "quality.yml":
            quality = ir
        jobs = ir.get("stages") or []
        if not jobs:
            return fail(f"no jobs translated {path.name}")
        for job in jobs:
            if not (job.get("source_anchor") or {}).get("json_pointer"):
                return fail(f"job missing source_anchor {path.name} {job.get('id')}")
            for child in job.get("children") or []:
                if not (child.get("source_anchor") or {}).get("json_pointer"):
                    return fail(f"step missing source_anchor {job.get('id')} {child.get('id')}")

    tests = (quality or {}).get("declared_ci_test_stages") or []
    if len(tests) != 60:
        return fail(f"declared CI test stages {len(tests)} expected 60")
    art_count = ((doc.get("tests_required") or {}).get("declared_ci_test_stages_are_ir_stages") or {}).get(
        "count"
    )
    if art_count != 60:
        return fail(f"artifact test count {art_count}")
    if not g.get("extractors_agree"):
        return fail("needs extractors disagreed")
    if not m.get("undercount_if_unexpanded"):
        return fail("unexpanded matrix did not under-count")
    print(
        json.dumps(
            {
                "probe": "probe1-parse-needs-topo",
                "unit_id": "WFA-0052",
                "estate_workflows": len(estate),
                "declared_ci_test_stages": len(tests),
                "needs_dag_pass": True,
                "matrix_expanded": m.get("expanded_jobs"),
                "matrix_unexpanded": m.get("unexpanded_jobs"),
                "required_optional_not_flattened": r.get("not_flattened"),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"estate={len(estate)} tests=60 needs_pass=True matrix {m.get('unexpanded_jobs')}->{m.get('expanded_jobs')}"
    )
    print("SUCCESS:WFA-0052-probe1 parse needs-graph independent topo matrix required-context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
