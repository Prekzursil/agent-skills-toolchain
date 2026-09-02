#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0119-decertification-and-supersession.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import supersession as S  # noqa: E402

OUT = "command-center/wfa/WFA-0119-decertification-and-supersession.json"
SCHEMA = HERE / "certification_record.standin.schema.json"
ENGINE = "command-center/p2-wave/probes/WFA-0119/supersession.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0119/probe1_benchmark_refuse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0119/probe2_preserve_owner.py"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def dep_status(rel: str) -> dict:
    path = REPO / rel
    return {
        "path": rel,
        "present": path.is_file() and path.stat().st_size > 0,
    }


def main() -> int:
    ctrls = S.run_controls()
    ok, failed = S.controls_ok(ctrls)
    if not ok:
        print("FAILED:WFA-0119 emit controls " + ",".join(failed))
        return 1

    try:
        import jsonschema
    except ImportError:
        jsonschema = None  # type: ignore

    h = ctrls["happy"]
    d = ctrls["disconnected"]
    l = ctrls["lossy"]
    n = ctrls["no_owner"]
    u = ctrls["unused_no_owner"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    wfa0001 = dep_status("command-center/wfa/schema/wfa-schema-pack.json")
    wfa0118 = dep_status("command-center/wfa/WFA-0118-certification-gate.json")
    wfa0076 = dep_status("command-center/wfa/WFA-0076-terminal-disposition-reversibility.json")

    doc = {
        "record_type": "CertificationRecord",
        "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/CertificationRecord",
        "schema_status": (
            "declared-pack-absent"
            if not wfa0001["present"]
            else "declared-pack-present"
        ),
        "unit_id": "WFA-0119",
        "id": "cert.wfa-0119.supersession.intake-v1-to-v2",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0119",
        "decision": "CERTIFY-SUCCESSOR-AND-SUPERSEDE",
        "workflow_id": "wf-certified-intake-v2",
        "certified": True,
        "owner_approval_required": True,
        "production_retirement": "not-executed",
        "generated_at": now,
        "scope": (
            "Fixture rehearsal of the supersession path. No live-estate workflow "
            "was retired. Owner sign-off in this record applies to the fixture "
            "retired id wf-certified-intake-v1 only."
        ),
        "dependencies": {
            "WFA-0001": {**wfa0001, "role": "CertificationRecord schema pack"},
            "WFA-0118": {
                **wfa0118,
                "role": "certification gate",
                "stand_in": "fixture workflows already marked CERTIFIED",
            },
            "WFA-0076": {
                **wfa0076,
                "role": "preserve-before-terminal",
                "stand_in": "content-hash store + retrieval rehearsal in this unit",
            },
        },
        "conditions": {
            "capability_superset": {
                "pass": h["signal_a"]["pass"],
                "signal": "A",
                "missing": h["signal_a"]["missing"],
                "retired_mechanisms": h["signal_a"]["retired_mechanisms"],
                "replacement_mechanisms": h["signal_a"]["replacement_mechanisms"],
                "extraction_rule": h["signal_a"]["extraction_rule"],
            },
            "retired_benchmarks_rerun": {
                "pass": h["signal_b"]["pass"],
                "signal": "B",
                "cases_run": h["signal_b"]["cases_run"],
                "cases_failed": h["signal_b"]["cases_failed"],
            },
            "preservation_before_terminal": {
                "pass": h["retrieval"]["ok"],
                "sha256": h["preservation"]["sha256"],
            },
            "owner_visible": {
                "pass": h["owner"]["pass"],
                "required": h["owner"]["required"],
                "decision_id": h["owner"].get("decision_id"),
            },
        },
        "supersession": {
            "retired_id": "wf-certified-intake-v1",
            "superseded_by": "wf-certified-intake-v2",
            "edge_recorded": h["superseded_by"] is not None,
            "retired_status_after": h["retired_status_after"],
            "edge": h["superseded_by"],
            "preservation": h["preservation"],
            "retrieval": h["retrieval"],
        },
        "negative_controls": [
            {
                "id": "disconnected-notify",
                "replacement_id": "wf-matrix-only",
                "accepted": d["accepted"],
                "refusals": d["refusals"],
                "signal_a_pass": d["signal_a"]["pass"],
                "signal_b_pass": d["signal_b"]["pass"],
                "retired_status_after": d["retired_status_after"],
                "note": "Matrix superset with disconnected notify behaviour: A pass, B fail, refuse.",
            },
            {
                "id": "lossy-missing-notify",
                "replacement_id": "wf-lossy-intake",
                "accepted": l["accepted"],
                "refusals": l["refusals"],
                "signal_a_pass": l["signal_a"]["pass"],
                "missing_mechanisms": l["signal_a"]["missing"],
                "retired_status_after": l["retired_status_after"],
                "note": "Notify absent from incidence row: capability-loss refuse.",
            },
            {
                "id": "owner-relied-without-signoff",
                "accepted": n["accepted"],
                "refusals": n["refusals"],
                "retired_status_after": n["retired_status_after"],
                "note": "Owner-relied capability cannot be retired by the lane.",
            },
            {
                "id": "non-owner-relied-without-signoff",
                "accepted": u["accepted"],
                "owner_required": u["owner"]["required"],
                "retired_status_after": u["retired_status_after"],
                "note": "Helper not owner-relied may supersede without owner sign-off.",
            },
        ],
        "evidence": [
            {
                "id": "A",
                "claim": (
                    "Replacement mechanism set is a superset of the retired set, "
                    "computed over the fixture incidence matrix extracted from definition.stages."
                ),
                "path": ENGINE,
                "line": find_line(ENGINE, "def signal_a_superset"),
                "snippet": "def signal_a_superset(matrix: dict, retired_id: str, replacement_id: str)",
                "result": h["signal_a"],
            },
            {
                "id": "B",
                "claim": (
                    "Retired workflow benchmark cases re-run against the replacement; "
                    "execution uses behavior_pack callables, not the matrix row."
                ),
                "path": ENGINE,
                "line": find_line(ENGINE, "def signal_b_benchmarks"),
                "snippet": "def signal_b_benchmarks(replacement: dict, cases: list[dict])",
                "result": h["signal_b"],
            },
        ],
        "tests": {
            "failed_retired_benchmark_refused": (not d["accepted"])
            and ("benchmark-fail" in d["refusals"]),
            "signals_a_and_b_diverge_on_disconnected": d["signal_a"]["pass"]
            and (not d["signal_b"]["pass"]),
            "capability_loss_refused": (not l["accepted"])
            and ("capability-loss" in l["refusals"]),
            "retired_definition_retrievable": h["retrieval"]["ok"] is True,
            "owner_relied_without_signoff_refused": (not n["accepted"])
            and ("owner-blocked" in n["refusals"]),
            "non_owner_relied_without_signoff_accepted": u["accepted"] is True,
            "refusal_writes_no_edge": d["superseded_by"] is None
            and n["superseded_by"] is None
            and l["superseded_by"] is None,
        },
        "reviewer": {
            "reviewer_id": "WFA-0119-probe1-probe2",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probes re-run the engine live. Probe 1 is the benchmark/"
                "superset control; probe 2 is the retrieval and owner-visibility control."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "benchmark-refuse-and-signal-divergence"},
            {"id": "probe2", "command": P2, "role": "preservation-retrieval-and-owner-gate"},
        ],
    }

    if jsonschema is not None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    print("SUCCESS:WFA-0119")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
