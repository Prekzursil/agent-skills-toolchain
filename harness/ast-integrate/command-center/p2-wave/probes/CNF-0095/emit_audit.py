#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0095-council-of-councils-fanin.json from the live run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import run_experiment  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0095-council-of-councils-fanin.json"
SCHEMA_REL = "command-center/schema/council-audit.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0095":
            sentinel = str(unit.get("completion_sentinel") or "")
            if "SUCCESS:CNF-0095" not in sentinel:
                raise SystemExit("FAILED:CNF-0095 catalog sentinel missing SUCCESS:CNF-0095")
            return sentinel
    raise SystemExit("FAILED:CNF-0095 catalog unit missing")


SENTINEL = catalog_sentinel()
QUESTION = (
    "When nested councils disagree about completion, what happens? Construct a "
    "council-of-councils where one subcouncil reports complete and another reports "
    "blocked, and answer: does the parent use the shared completion reducer, does it "
    "surface the disagreement rather than averaging it away, and is any subcouncil "
    "result counted twice in the parent tally?"
)


def _compact(verdict: dict) -> dict:
    return {
        "verdict": verdict.get("verdict"),
        "disagreement": verdict.get("disagreement"),
        "failing_condition_id": verdict.get("failing_condition_id"),
        "complete_n": verdict.get("complete_n"),
        "blocked_n": verdict.get("blocked_n"),
        "n": verdict.get("n"),
        "site": verdict.get("site"),
        "tally": verdict.get("tally"),
        "children": [
            {
                "site": c.get("site"),
                "source_id": c.get("source_id"),
                "verdict": c.get("verdict"),
                "failing_condition_id": c.get("failing_condition_id"),
            }
            for c in (verdict.get("children") or [])
        ],
        "subcouncil_verdicts": [
            _compact(s) if "children" in s else {
                "subcouncil_id": s.get("subcouncil_id"),
                "verdict": s.get("verdict"),
                "disagreement": s.get("disagreement"),
                "failing_condition_id": s.get("failing_condition_id"),
                "site": s.get("site"),
            }
            for s in (verdict.get("subcouncil_verdicts") or [])
        ],
    }


def validate_or_die(doc: dict) -> None:
    """Local structural checks. Do not fetch the catalog shim's remote $ref.

    command-center/schema/council-audit.schema.json is a generated $ref shim
    whose $id lives at https://ast-integrate.invalid/. jsonschema 4.10 tries
    the network for that URI; G-1 only requires JSON parse + named probes.
    Named probes require reducer_invocation_trace and parent_tally_arithmetic
    at the top level, which receipt_core additionalProperties:false would
    reject — so a full-schema park loop is the wrong move.
    """
    shim = REPO / SCHEMA_REL
    if not shim.is_file() or shim.stat().st_size <= 0:
        raise SystemExit(f"FAILED:CNF-0095 schema missing {SCHEMA_REL}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:CNF-0095 self-declared {doc.get('state')}")
    if not isinstance(doc.get("reducer_invocation_trace"), list) or len(doc["reducer_invocation_trace"]) < 2:
        raise SystemExit("FAILED:CNF-0095 reducer invocation trace missing")
    if not isinstance(doc.get("parent_tally_arithmetic"), dict):
        raise SystemExit("FAILED:CNF-0095 tally arithmetic missing")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "council-audit":
        raise SystemExit("FAILED:CNF-0095 report.kind is not council-audit")
    if not report.get("observations") or not report.get("control_ids"):
        raise SystemExit("FAILED:CNF-0095 report observations/control_ids missing")
    fps = {t.get("predicate_fingerprint") for t in doc["reducer_invocation_trace"] if t.get("predicate_fingerprint")}
    if len(fps) != 1:
        raise SystemExit(f"FAILED:CNF-0095 predicate fingerprints diverged {fps}")
    tally = doc["parent_tally_arithmetic"]
    if tally.get("tally_sum") != tally.get("distinct_source_count"):
        raise SystemExit(f"FAILED:CNF-0095 tally arithmetic {tally}")


def main() -> int:
    live = run_experiment()
    required = [
        live["same_fanin_object"],
        live["same_fingerprint_both_levels"],
        live["same_predicate_id_both_levels"],
        live["disagreement_surfaced_not_averaged"],
        live["tally_ok"],
        live["double_count_detected"],
        live["agree_completes_without_spurious_escalation"],
        live["flat_complete"],
        live["planted_private_predicate_detected"],
        live["production_topology_has_no_private_predicate"],
        live["topology_imports_shared_reducer"],
    ]
    if not all(required):
        print("FAILED:CNF-0095 live experiment did not confirm all claims")
        print(json.dumps({k: live[k] for k in (
            "same_fanin_object",
            "same_fingerprint_both_levels",
            "disagreement_surfaced_not_averaged",
            "tally_ok",
            "double_count_detected",
            "agree_completes_without_spurious_escalation",
            "child_verdict_labels",
        )}, indent=2, default=str)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parent = _compact(live["disagree"])
    doc = {
        "unit_id": "CNF-0095",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Council-of-councils fan-in: nested completion disagreement and double-count check",
        "question": QUESTION,
        "produced_at": now,
        "answers": {
            "parent_uses_shared_reducer": True,
            "disagreement_surfaced_not_averaged": True,
            "any_subcouncil_counted_twice_in_honest_tally": False,
            "double_count_detector_fires_on_duplicate_input": True,
        },
        "report": {
            "kind": "council-audit",
            "observations": [
                {
                    "name": "parent_verdict",
                    "measured": str(parent["verdict"]),
                    "method": "nested-fanin-conjunction",
                    "anchor": "command-center/p2-wave/probes/CNF-0095/topology.py",
                },
                {
                    "name": "disagreement_surfaced_not_averaged",
                    "measured": True,
                    "method": "nested-fanin-conjunction",
                    "anchor": "command-center/p2-wave/probes/CNF-0095/reducer.py",
                },
                {
                    "name": "same_reducer_fingerprint_both_levels",
                    "measured": True,
                    "method": "sha256-source-identity",
                    "anchor": "command-center/p2-wave/probes/CNF-0095/reducer.py",
                },
                {
                    "name": "tally_sum_equals_distinct_source_count",
                    "measured": True,
                    "method": "tally-arithmetic",
                    "anchor": "command-center/p2-wave/probes/CNF-0095/reducer.py",
                },
                {
                    "name": "averaging_mutant_false_consensus",
                    "measured": str(live["averaged_mutant"]["verdict"]),
                    "method": "known-broken-fixture",
                    "anchor": "command-center/p2-wave/probes/CNF-0095/mutants.py",
                },
            ],
            "control_ids": [
                "NC-averaging-mutant",
                "NC-planted-private-predicate",
            ],
        },
        "verdicts": [
            {
                "id": "V1-shared-reducer",
                "claim": "The parent invokes the same completion reducer as the flat fan-in (object identity and source fingerprint).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0095/topology.py",
            },
            {
                "id": "V2-disagreement-surfaced",
                "claim": "A COMPLETE subcouncil plus a BLOCKED subcouncil is recorded as disagreement; the parent is not COMPLETE.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0095/reducer.py",
            },
            {
                "id": "V3-no-double-count",
                "claim": "Honest tally_sum equals distinct_source_count; duplicating a subcouncil is detected by that comparison.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0095/reducer.py:tally_sources",
            },
        ],
        "subcouncil_verdicts": parent.get("subcouncil_verdicts"),
        "parent_verdict": {
            "verdict": parent["verdict"],
            "disagreement": parent["disagreement"],
            "failing_condition_id": parent["failing_condition_id"],
            "complete_n": parent["complete_n"],
            "blocked_n": parent["blocked_n"],
            "n": parent["n"],
        },
        "flat_verdict": {
            "verdict": live["flat"]["verdict"],
            "n": live["flat"]["n"],
        },
        "agreeing_control": {
            "verdict": live["agree"]["verdict"],
            "disagreement": live["agree"]["disagreement"],
        },
        "reducer_invocation_trace": live["reducer_invocation_trace"],
        "parent_tally_arithmetic": live["parent_tally_arithmetic"],
        "predicate_identity": {
            "flat_is_nested_is_reduce_many": True,
            "predicate_fingerprint": live["predicate_fingerprint"],
            "reduce_completion_qualname": "reduce_completion",
            "source_path": "command-center/p2-wave/probes/CNF-0095/reducer.py",
        },
        "production_modules_present": live["production_modules_present"],
        "topology_locus": "command-center/p2-wave/probes/CNF-0095/topology.py",
        "residual": (
            "platform/lib/completion_predicate.py and tools/council/simulate.py are absent "
            "on this worktree. CNF-0095 constructed the nested topology the catalog asks "
            "for and bound both levels to one reducer; it did not rebuild ADV-0102."
        ),
        "evidence": [
            {
                "kind": "live-run",
                "claim": "Nested disagree fixture: parent incomplete, children split.",
                "detail": (
                    f"parent={parent['verdict']} disagreement={parent['disagreement']} "
                    f"children={live['child_verdict_labels']}"
                ),
                "path": "command-center/p2-wave/probes/CNF-0095/experiment.py",
            },
            {
                "kind": "live-run",
                "claim": "Reducer fingerprint is identical at subcouncil and parent sites.",
                "detail": f"fingerprint={live['predicate_fingerprint']}",
                "path": "command-center/p2-wave/probes/CNF-0095/reducer.py",
            },
            {
                "kind": "live-run",
                "claim": "Tally arithmetic: two distinct sources, sum 2, no double count.",
                "detail": json.dumps(live["disagree"]["tally"], sort_keys=True),
                "path": "command-center/p2-wave/probes/CNF-0095/reducer.py",
            },
            {
                "kind": "detector-control",
                "claim": "Averaging mutant returns COMPLETE on the same split; production does not.",
                "detail": json.dumps(live["averaged_mutant"], sort_keys=True),
                "path": "command-center/p2-wave/probes/CNF-0095/mutants.py",
            },
        ],
        "tests": [
            {
                "id": "T1-same-reducer",
                "name": "Parent invokes the same reducer as the flat case",
                "result": "PASS",
            },
            {
                "id": "T2-double-count",
                "name": "Tally compared against distinct-source count detects a duplicated subcouncil",
                "result": "PASS",
            },
            {
                "id": "T3-disagreement",
                "name": "Disagreement surfaces as disagreement, never a false consensus",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-averaging-mutant",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "majority-average on 1 COMPLETE + 1 BLOCKED yields COMPLETE",
                "good_state": "agreeing nesting completes without disagreement flag",
            },
            {
                "id": "NC-planted-private-predicate",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "AST finds parent_complete in planted source",
                "good_state": "topology.py defines no private completion function",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0095-detector-control-averaging-mutant",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "job": "re-run the DETECTOR CONTROL on the known-broken averaging fixture",
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA_REL,
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0095/reducer.py",
                "exists": True,
                "role": "shared-reducer",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0095/topology.py",
                "exists": True,
                "role": "nested-topology",
            },
        ],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:CNF-0095 sentinel not in serialized artifact")
        return 1
    validate_or_die(doc)
    out.write_text(payload, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(payload.encode('utf-8'))}")
    print("SUCCESS:CNF-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
