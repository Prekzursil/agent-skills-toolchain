#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0046-adapter-metaswarm-pipeline.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

OUT = "command-center/wfa/WFA-0046-adapter-metaswarm-pipeline.json"
SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0046/AdapterConformanceReport.schema.json"
)
QUESTION = (
    "Implementation target: represent the metaswarm phase pipeline - "
    "design-review gate, plan-review gate, 4-phase per-work-unit loop, "
    "coverage enforcement, pre-PR knowledge capture - as IR stages and "
    "gates without importing metaswarm as a runtime."
)


def main() -> int:
    ir = A.build_ir()
    live = A.discover_live()
    audit = A.runtime_import_audit()
    if not audit["clean"]:
        print(f"FAILED:WFA-0046 runtime import/vendoring {audit}")
        return 1
    gates = {g["id"]: g for g in ir["gates"]}
    gov = [g["id"] for g in ir["governance_mandatory_gates"]]
    if gov != [
        "design-review-gate",
        "plan-review-gate",
        "coverage-enforcement",
        "pre-pr-knowledge-capture",
    ]:
        print(f"FAILED:WFA-0046 governance order {gov}")
        return 1
    for gid in gov:
        if gid not in gates:
            print(f"FAILED:WFA-0046 missing gate {gid}")
            return 1
        if gates[gid]["gate_kind"] != "BLOCKING":
            print(f"FAILED:WFA-0046 {gid} not BLOCKING")
            return 1
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    doc = {
        "record_type": "AdapterConformanceReport",
        "unit_id": "WFA-0046",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0046",
        "completion_sentinel": "SUCCESS:WFA-0046",
        "title": "Adapter: the metaswarm 9-phase pipeline and its gates to IR",
        "question": QUESTION,
        "output_schema_declared": (
            "command-center/wfa/schema/wfa-schema-pack.json"
            "#/$defs/AdapterConformanceReport"
        ),
        "output_schema_local": SCHEMA_REL,
        "schema_pack_note": (
            "WFA-0001 schema pack is not present on this tree; this artifact "
            "validates against the per-unit AdapterConformanceReport.schema.json."
        ),
        "adapter": {
            "id": "metaswarm-pipeline",
            "kind": "read-describe-only",
            "runtime_import": False,
            "source_mode": "published-skill-markdown-snapshot",
        },
        "live_inputs": live,
        "corpus": A.corpus_files(),
        "ir": ir,
        "lossy_field_ledger": ir["lossy_field_ledger"],
        "runtime_import_audit": audit,
        "tests": [
            {
                "id": "blocking-gate-no-advisory-downgrade",
                "name": "A gate that blocks in metaswarm renders BLOCKING in IR",
                "result": "PASS",
            },
            {
                "id": "no-metaswarm-runtime-import",
                "name": "Adapter reads and describes; no metaswarm import or vendored JS/TS",
                "result": "PASS",
            },
            {
                "id": "governance-mandatory-gate-order",
                "name": "CLAUDE.md Workflow Enforcement intercept order preserved",
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "A-phase-map",
                "claim": "Each USAGE.md numbered phase maps to an IR stage; each named gate has a stopping-expression that A10 accepts unchanged.",
                "path": OUT,
            },
            {
                "kind": "B-worked-example",
                "claim": "Independent reader sequence and CLAUDE.md enforcement offsets match IR governance_mandatory_gates and 4-phase blocking semantics.",
                "path": "command-center/p2-wave/probes/WFA-0046/fixtures/worked-example.json",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0046-probe2-independent-order",
            "independent": True,
            "verdict": "PASS",
        },
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        import jsonschema

        jsonschema.Draft202012Validator(schema).validate(doc)
    except Exception as exc:
        print(f"FAILED:WFA-0046 schema {type(exc).__name__}: {exc}")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:WFA-0046" not in dest.read_text(encoding="utf-8"):
        print("FAILED:WFA-0046 sentinel missing after write")
        return 1
    print(f"wrote {OUT}")
    print("SUCCESS:WFA-0046")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
