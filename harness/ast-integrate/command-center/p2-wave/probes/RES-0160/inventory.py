#!/usr/bin/env python3
"""Last two completed mechanism-adoption sweeps on this estate, live-remeasured.

Sweep S-R2 = P2-BUILD ROUND 2 (vacuity guard + key-check schema-document fallback).
Sweep S-R3 = P2-BUILD ROUND 3 (merit-stage schema_doc_verdict + text-artifact gate).

These are the last two sweeps that adopted mechanisms into command-center/ready_units.py
and left durable reports. Cost lines were not recorded; the gate therefore cannot ADOPT
any of them retroactively. That is the honest reading, not a blessing of what shipped.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

META = "https://json-schema.org/draft/2020-12/schema"
KEYED_GARBAGE = {"$schema": META, "totally": "unrelated", "passing_tests": 999999}
UNKEYED_GARBAGE = {"totally": "unrelated", "passing_tests": 999999}
R2_SILENT_CONTROL = {"type": 123, "required": "not-an-array"}
CONTROL_VACUOUS = (
    "command-center/p2-wave/fixtures/ready-units/IMP-0433-state-SUCCESS-mutant.json"
)


def _load_ready_units():
    path = REPO / "command-center/ready_units.py"
    spec = importlib.util.spec_from_file_location("ready_units_res0160", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:RES-0160 cannot load command-center/ready_units.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ready_units_res0160"] = mod
    spec.loader.exec_module(mod)
    return mod


def live_remeasure() -> dict:
    ru = _load_ready_units()
    pre_keyed = bool(ru._pre_r3_schema_doc(KEYED_GARBAGE))
    pre_unkeyed = bool(ru._pre_r3_schema_doc(UNKEYED_GARBAGE))
    pre_silent = bool(ru._pre_r3_schema_doc(R2_SILENT_CONTROL))
    new_keyed_ok, new_keyed_stage = ru.schema_doc_verdict(KEYED_GARBAGE)
    new_unkeyed_ok, new_unkeyed_stage = ru.schema_doc_verdict(UNKEYED_GARBAGE)
    looks_keyed = bool(ru.looks_like_schema_doc(KEYED_GARBAGE))

    unit = {"completion_sentinel": "SUCCESS:RES-0160"}
    thin = "SUCCESS:RES-0160\n" + ("x" * 50)
    blob = "x" * 2000
    text_thin_ok, text_thin_why = ru.text_artifact_verdict(unit, thin)
    text_blob_ok, text_blob_why = ru.text_artifact_verdict(
        unit, "SUCCESS:RES-0160\n" + blob
    )

    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by_id = {u["id"]: u for u in catalog.get("work_units") or [] if isinstance(u, dict)}
    mutant = dict(by_id.get("IMP-0433") or {})
    resolver = ru._load_resolver()
    vacuous_before = None
    vacuous_after = None
    vacuous_why = None
    if mutant and (REPO / CONTROL_VACUOUS).is_file():
        mutant["output_path"] = CONTROL_VACUOUS
        vacuous_before = bool(ru._prefix_predicate(mutant, resolver))
        got, why = ru.artifact_delivered(mutant, resolver)
        vacuous_after = bool(got)
        vacuous_why = why

    still = {
        "condition_4b": callable(getattr(ru, "_fallback_contract", None))
        and callable(getattr(ru, "contract_discriminates", None)),
        "schema_doc_verdict": callable(getattr(ru, "schema_doc_verdict", None)),
        "looks_like_schema_doc": callable(getattr(ru, "looks_like_schema_doc", None)),
        "pre_r3_repro": callable(getattr(ru, "_pre_r3_schema_doc", None)),
        "text_artifact": callable(getattr(ru, "text_artifact_verdict", None)),
        "schema_doc_controls": bool(getattr(ru, "_SCHEMA_DOC_CONTROLS", None)),
    }

    return {
        "pre_r3_keyed_garbage_accepted": pre_keyed,
        "pre_r3_unkeyed_garbage_accepted": pre_unkeyed,
        "pre_r3_silent_control_accepted": pre_silent,
        "schema_doc_verdict_keyed": {
            "ok": bool(new_keyed_ok),
            "stage": new_keyed_stage,
        },
        "schema_doc_verdict_unkeyed": {
            "ok": bool(new_unkeyed_ok),
            "stage": new_unkeyed_stage,
        },
        "looks_like_schema_doc_keyed": looks_keyed,
        "text_thin": {"ok": bool(text_thin_ok), "why": text_thin_why},
        "text_blob": {"ok": bool(text_blob_ok), "why": text_blob_why},
        "old_nonjson_suffix_would_accept": True,
        "vacuous_mutant": {
            "pre_4b": vacuous_before,
            "artifact_delivered": vacuous_after,
            "why": vacuous_why,
            "fixture": CONTROL_VACUOUS,
        },
        "still_callable": still,
        "resolver_loaded": resolver is not None,
    }


def historical_records(live: dict | None = None) -> list[dict]:
    """Reconstructed adoption records. Cost lines are ABSENT: they were not written."""
    live = live or live_remeasure()
    vac = live["vacuous_mutant"]
    still = live["still_callable"]

    r2_4b_metric = None
    if vac["pre_4b"] is not None and vac["artifact_delivered"] is not None:
        r2_4b_metric = {
            "id": "vacuous-contract-state-SUCCESS-mutant-delivered",
            "before": vac["pre_4b"],
            "after": vac["artifact_delivered"],
            "direction": "true_to_false",
            "notes": (
                "Live remesure of CONTROL VACUOUS: pre-4b predicate vs "
                "artifact_delivered on IMP-0433-state-SUCCESS-mutant.json"
            ),
        }

    return [
        {
            "mechanism_id": "R2-condition-4b-vacuity-guard",
            "sweep": "S-R2",
            "sweep_title": "P2-BUILD ROUND 2",
            "locus": "command-center/ready_units.py:artifact_delivered condition 4b",
            "still_in_use": bool(still["condition_4b"]),
            "named_metric": r2_4b_metric,
            "revert_trigger": {
                "predicate": (
                    "CONTROL VACUOUS (state:=SUCCESS mutant) delivered=True "
                    "under artifact_delivered"
                )
            },
            "owner_visible_cost": None,
            "adoption_note": (
                "Metric and revert trigger are recoverable from the live "
                "--self-test fixture. No owner-visible cost line was recorded."
            ),
        },
        {
            "mechanism_id": "R2-schema-doc-key-fallback",
            "sweep": "S-R2",
            "sweep_title": "P2-BUILD ROUND 2",
            "locus": "command-center/ready_units.py:_pre_r3_schema_doc (R2 live path)",
            "still_in_use": False,
            "named_metric": {
                "id": "rejects_keyed_garbage",
                "before": False,
                "after": (not live["pre_r3_keyed_garbage_accepted"]),
                "direction": "false_to_true",
                "notes": (
                    "Claimed two-sided garbage rejection. Live remesure of the "
                    "R2 instrument accepts KEYED garbage "
                    f"(pre_r3_keyed={live['pre_r3_keyed_garbage_accepted']}), "
                    "so rejects_keyed_garbage after=False."
                ),
            },
            "revert_trigger": {
                "predicate": "keyed garbage + $schema is delivered=True"
            },
            "owner_visible_cost": None,
            "adoption_note": (
                "Superseded by R3 merit stage. The R2 instrument still lives as "
                "_pre_r3_schema_doc for controls, not as the live gate."
            ),
        },
        {
            "mechanism_id": "R2-vacuous-mutant-control-silent",
            "sweep": "S-R2",
            "sweep_title": "P2-BUILD ROUND 2",
            "locus": "looks_like_schema_doc docstring control (unkeyed broken schema)",
            "still_in_use": False,
            "named_metric": {
                "id": "control-reaches-check_schema",
                "before": False,
                "after": live["pre_r3_silent_control_accepted"],
                "direction": "false_to_true",
                "notes": (
                    "R2 control used an unkeyed broken schema, so check_schema "
                    "never ran. Live remesure: "
                    f"pre_r3_silent_accepted={live['pre_r3_silent_control_accepted']}."
                ),
            },
            "revert_trigger": None,
            "owner_visible_cost": None,
            "adoption_note": "A control silent in both states is not an improvement.",
        },
        {
            "mechanism_id": "R3-schema-doc-verdict-merit",
            "sweep": "S-R3",
            "sweep_title": "P2-BUILD ROUND 3",
            "locus": "command-center/ready_units.py:schema_doc_verdict",
            "still_in_use": bool(still["schema_doc_verdict"]),
            "named_metric": {
                "id": "rejects_keyed_garbage",
                "before": (not live["pre_r3_keyed_garbage_accepted"]),
                "after": (
                    live["schema_doc_verdict_keyed"]["ok"] is False
                    and str(live["schema_doc_verdict_keyed"]["stage"]).startswith(
                        "schema-document-vacuous"
                    )
                ),
                "direction": "false_to_true",
                "notes": (
                    "Live remesure: R2 instrument accepts keyed garbage; R3 "
                    f"stage={live['schema_doc_verdict_keyed']['stage']}."
                ),
            },
            "revert_trigger": {
                "predicate": (
                    "schema_doc_verdict(keyed-garbage)[0] is True or stage is "
                    "not schema-document-vacuous"
                )
            },
            "owner_visible_cost": None,
            "adoption_note": (
                "Metric improved and revert trigger is named in --self-test. "
                "No owner-visible cost line was recorded at adoption."
            ),
        },
        {
            "mechanism_id": "R3-text-artifact-sentinel-gate",
            "sweep": "S-R3",
            "sweep_title": "P2-BUILD ROUND 3",
            "locus": "command-center/ready_units.py:text_artifact_verdict",
            "still_in_use": bool(still["text_artifact"]),
            "named_metric": {
                "id": "nonjson-2000x-blob-delivered",
                "before": live["old_nonjson_suffix_would_accept"],
                "after": live["text_blob"]["ok"],
                "direction": "true_to_false",
                "notes": (
                    "Old branch returned (True, 'non-json-present') on suffix. "
                    f"Live text_artifact_verdict on 2000-x blob: ok="
                    f"{live['text_blob']['ok']} why={live['text_blob']['why']}."
                ),
            },
            "revert_trigger": {
                "predicate": (
                    "a 2000-x .md blob with the unit sentinel is delivered"
                )
            },
            "owner_visible_cost": None,
            "adoption_note": (
                "ROUND3 recorded exploited_count 0→0 (neutral on production "
                "false-greens) and SUFFIX_BYPASS_PROVEN True→False. Cost line absent."
            ),
        },
        {
            "mechanism_id": "R3-keyed-garbage-self-test-control",
            "sweep": "S-R3",
            "sweep_title": "P2-BUILD ROUND 3",
            "locus": "command-center/ready_units.py:_SCHEMA_DOC_CONTROLS",
            "still_in_use": bool(still["schema_doc_controls"]),
            "named_metric": {
                "id": "control-reaches-vacuous-stage",
                "before": False,
                "after": str(live["schema_doc_verdict_keyed"]["stage"]).startswith(
                    "schema-document-vacuous"
                ),
                "direction": "false_to_true",
            },
            "revert_trigger": {
                "predicate": (
                    "_SCHEMA_DOC_CONTROLS keyed-garbage case missing or want_stage "
                    "is not schema-document-vacuous"
                )
            },
            "owner_visible_cost": None,
            "adoption_note": "Instrumentation, not a product gem. Still no cost line.",
        },
    ]


def run_backtest() -> dict:
    live = live_remeasure()
    records = historical_records(live)
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import gate as G  # noqa: E402

    pop = G.evaluate_population(records)
    return {
        "sweeps": [
            {
                "id": "S-R2",
                "title": "P2-BUILD ROUND 2",
                "report": "command-center/p2-wave/P2-BUILD-ROUND2.md",
            },
            {
                "id": "S-R3",
                "title": "P2-BUILD ROUND 3",
                "report": "command-center/p2-wave/P2-BUILD-ROUND3.md",
            },
        ],
        "live": live,
        "records": records,
        "population": pop,
    }
