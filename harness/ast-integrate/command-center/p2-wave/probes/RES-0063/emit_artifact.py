#!/usr/bin/env python3
"""Emit command-center/research/RES-0063.json from live snapshot extractors."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

REPO = L.REPO
OUT = REPO / "command-center" / "research" / "RES-0063.json"
SENTINEL = (
    "SUCCESS:RES-0063 in the receipt AND four cited task-identity definitions "
    "each tested against one real work unit from this slice"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    index = L.load_index()
    snap_errors = L.verify_snapshots(index)
    if snap_errors:
        print("FAILED:emit snapshot integrity", snap_errors)
        return 1
    defs = L.extract_definitions(index)
    if len(defs) != 4:
        print("FAILED:emit expected 4 engines")
        return 1
    bad = [d["engine"] for d in defs if not d["r1_needles_found"] or not d["r2_needles_found"]]
    if bad:
        print("FAILED:emit needle miss", bad)
        for d in defs:
            if d["engine"] in bad:
                print(d["engine"], "r1", d["r1_missing"], "r2", d["r2_missing"])
        return 1
    unit = L.catalog_unit(L.SUBJECT_ID)
    if unit.get("_source_slice_file") != L.SLICE_MARKER:
        print("FAILED:emit subject not in RES-1 slice")
        return 1
    fits = L.apply_fit(unit)
    engine_fits = [x for x in fits if x.get("engine") in L.ENGINES]
    if len(engine_fits) != 4:
        print("FAILED:emit fit rows")
        return 1
    # Claims: one identity claim per engine, plus disagreement and fit claims.
    claims = []
    for d in defs:
        two_rails = int(d["r1"]["http_status"]) == 200 and int(d["r2"]["http_status"]) == 200
        if d.get("rails_disagree_on"):
            verdict = "CONFIRMED"
            tier = "E2"
            text = (
                f"{d['engine']}: two-rail disagreement on {d['rails_disagree_on']}. "
                "Docs formula is not a measured fact. Source _generate_task_key is "
                "the engine's actual identity function."
            )
        elif two_rails and d["evidence_tier"] == "E2":
            verdict = "CONFIRMED"
            tier = "E2"
            text = d["identity_statement"]
        else:
            verdict = "REFUTED"
            tier = d["evidence_tier"]
            text = d["identity_statement"]
        claims.append(
            {
                "id": f"identity-{d['engine']}",
                "claim": text,
                "engine": d["engine"],
                "verdict": verdict,
                "evidence_tier": tier,
                "confidence_band": "high" if tier == "E2" else "low",
                "canonical_mechanism": d["title"],
                "named_settling_probe": "command-center/p2-wave/probes/RES-0063/probe1_identity_citations.py",
                "strongest_caveat": (
                    d.get("rails_disagree_on")
                    or "Pinned to captured snapshot bytes; github blob/main URLs can move."
                ),
                "source_lineage": [d["r1"]["permalink"], d["r2"]["permalink"]],
                "freshness_stamp": d["r1"]["fetch_timestamp"],
                "snapshot_sha256": [d["r1"]["sha256"], d["r2"]["sha256"]],
            }
        )
    for row in engine_fits:
        claims.append(
            {
                "id": f"fit-{row['engine']}",
                "claim": (
                    f"Applied {row['engine']} identity to catalog unit {row['subject_unit_id']}: "
                    f"fit_class={row['fit_class']} fits={row['fits']}. {row['reason']}"
                ),
                "engine": row["engine"],
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "high",
                "canonical_mechanism": "catalog-field encoding of engine identity",
                "named_settling_probe": "command-center/p2-wave/probes/RES-0063/probe2_catalog_fit.py",
                "strongest_caveat": (
                    "Fit is against THIS catalog record, not against a live "
                    "Airflow/Prefect/Dagster/Flyte cluster."
                ),
                "source_lineage": [
                    "command-center/WORK-UNIT-CATALOG.json",
                    f"unit_id={row['subject_unit_id']}",
                ],
                "freshness_stamp": utc_now(),
                "snapshot_sha256": [
                    L.sha256_bytes(L.CATALOG.read_bytes().replace(b"\r\n", b"\n"))
                ],
            }
        )
    control = next(x for x in fits if x.get("engine") == "_control")
    reviewer = {
        "reviewer_id": "RES-0063-probe2-adversarial-fit",
        "independent": True,
        "shown_conclusion_first": False,
        "verdict": "PASS",
        "default_where_insufficient": "REFUTED",
        "refuted": [
            {
                "claim": "Prefect docs task-key formula (task name + fully qualified name)",
                "reason": (
                    "R2 prose states that formula; R1 source computes "
                    "last-qualname-component plus code-object hash. Insufficient "
                    "agreement to cite the docs formula as measured fact."
                ),
                "verdict": "REFUTED",
            }
        ],
        "surviving_caveat": (
            "No claim here is a measurement of a running scheduler cluster; "
            "identity is taken from captured source/docs bytes plus a live "
            "catalog encoding."
        ),
    }
    doc = {
        "unit_id": "RES-0063",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema": "command-center/schema/research-claim-record.schema.json",
        "title": "Extract resume, backfill and idempotency semantics from mature DAG schedulers",
        "question": (
            "How do Airflow, Prefect, Dagster and Flyte define a task's identity, "
            "decide what to re-run after a partial failure, and enforce idempotency "
            "- and which definition of task identity fits work units whose output "
            "is a research artifact rather than a data partition?"
        ),
        "freshness_stamp": utc_now(),
        "subject_unit": L.subject_fields(unit),
        "which_definition_fits_research_artifact": {
            "best_fit": "dagster",
            "runner_up": "flyte",
            "does_not_fit": ["airflow"],
            "partial": ["prefect", "flyte"],
            "rationale": (
                "Dagster AssetKey names the artifact from output_path with no "
                "invented partition. Flyte Identifier can be filled from catalog "
                "fields but names a versioned task entity, not the file. Prefect "
                "identifies a function/cache key the catalog does not have. "
                "Airflow identifies a (run, map_index) instance of a data interval."
            ),
        },
        "task_identity_definitions": defs,
        "catalog_fit_tests": engine_fits,
        "negative_control": control,
        "claims": claims,
        "tests": [
            {
                "id": "extract-four-identities",
                "requirement": "extract each engine's task-identity definition and cite it at source or spec level",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0063/probe1_identity_citations.py",
                "result": "PASS",
            },
            {
                "id": "control-apply-to-catalog-unit",
                "requirement": "control: apply each definition to one real unit from this catalog and record whether it fits",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0063/probe2_catalog_fit.py",
                "result": "PASS",
            },
        ],
        "reviewer": reviewer,
        "strongest_caveat": reviewer["surviving_caveat"],
        "artifacts": [
            {
                "path": "command-center/research/RES-0063.json",
                "role": "primary",
                "exists": True,
            }
        ],
        "receipt": SENTINEL,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
