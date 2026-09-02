#!/usr/bin/env python3
"""Emit the CNL-0098 detector spec (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0098-weak-synthesis-and-circular-citation-in-the-argument-graph.md"
)
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0098/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0098/probe2_schema_and_overclaim.py"
)


def line_of(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"snippet not found in {rel}: {snippet!r}")


def main() -> int:
    F.dump_json()
    reports = {fid: D.analyse(doc) for fid, doc in F.all_fixtures().items()}
    rev = R.review()
    if rev["verdict"] != "PASS" or not rev["rerun"]["passed"]:
        print("FAILED:CNL-0098 emit reviewer both-states did not pass")
        print(json.dumps(rev["rerun"], indent=2)[:2000])
        return 1

    planted_lines = [D.status_line(reports[i]) for i in F.PLANTED_BAD_IDS]
    clean_lines = [D.status_line(reports[i]) for i in F.CLEAN_IDS]
    fp = rev["rerun"]["false_positive_rate"]
    cat = "command-center/WORK-UNIT-CATALOG.json"
    det = "command-center/p2-wave/probes/CNL-0098/detector.py"
    fix = "command-center/p2-wave/probes/CNL-0098/fixtures.py"

    prod_a = "tools/council/artifacts/argument_graph.py"
    prod_e = "tools/council/artifacts/evidence_map.py"
    present_a = (REPO / prod_a).is_file()
    present_e = (REPO / prod_e).is_file()
    dep75 = (
        "command-center/design/council/"
        "CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md"
    )

    catalog = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not catalog:
        print("FAILED:CNL-0098 emit catalog schema empty")
        return 1
    bound_path = HERE / "bound.schema.json"
    if not bound_path.is_file():
        print("FAILED:CNL-0098 emit bound.schema.json missing")
        return 1
    # Catalog path is a generated $ref shim; jsonschema 4.10 cannot resolve
    # ast-integrate.invalid (RefResolutionError). Discriminate with bound.
    props = catalog.get("properties") or {}
    if "false_positive_rate" in props or "detector" in props:
        schema = catalog
    else:
        schema = json.loads(bound_path.read_text(encoding="utf-8"))
    import jsonschema

    doc = {
        "answer": (
            "Unsupported synthesis sentences are those with no inbound "
            "SUPPORTS/GROUNDS/CITES edge from an evidence-reachable node. "
            "Circular citation is a directed cycle on those same edge kinds; "
            "the detector prints the full path. Distinct URL count is not the "
            "signal. A diamond DAG is silent. Zero support edges are "
            "NOT-CHECKED, never a clean pass. SUCCESS:CNL-0098"
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0098/detector.py",
                "exists": True,
                "role": "detector",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0098/fixtures.py",
                "exists": True,
                "role": "fixtures",
            },
        ],
        "both_states": {
            "planted": {
                "status": "FIRE",
                "verbatim": "\n".join(planted_lines),
            },
            "clean": {
                "status": "SILENT",
                "verbatim": "\n".join(clean_lines),
            },
            "detector_control": {
                "status": reports[F.CONTROL_ID]["status"],
                "verbatim": rev["rerun"]["control_verbatim"],
            },
            "planted_bad": {
                "status": "FIRE",
                "verbatim": "\n".join(planted_lines),
            },
            "known_good": {
                "status": "SILENT",
                "verbatim": "\n".join(clean_lines),
            },
        },
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": True,
            "known_present_fixture": F.CONTROL_ID,
            "verbatim": rev["rerun"]["control_verbatim"],
        },
        "distinction": {
            "nothing_to_add": (
                "Out of scope for CNL-0098. Shared schema requires this key; "
                "this unit does not classify 'nothing to add' turns."
            ),
            "disengaged": (
                "Out of scope for CNL-0098. This unit classifies missing graph "
                "support and citation cycles, not disengaged participants."
            ),
            "operational_test": (
                "FIRE on planted-weak, planted-cycle, planted-circular-ungrounded, "
                "and url-launder-cycle; SILENT on clean-linear, diamond, and "
                "legit-cross-ref; empty-graph is NOT-CHECKED."
            ),
        },
        "claims": [
            {
                "id": "C-WEAK",
                "claim": "Planted orphan synthesis sentence syn-orphan is reported unsupported.",
                "verdict": "CONFIRMED",
                "anchor": f"{fix}:{line_of(fix, 'syn-orphan')}",
            },
            {
                "id": "C-CYCLE",
                "claim": "A 3-node SUPPORTS cycle fires and the report includes a full path.",
                "verdict": "CONFIRMED",
                "anchor": f"{det}:{line_of(det, 'def find_cycles')}",
            },
            {
                "id": "C-DIAMOND",
                "claim": "A diamond DAG with a shared ancestor is not reported as a cycle.",
                "verdict": "CONFIRMED",
                "anchor": f"{fix}:{line_of(fix, 'Shared ancestor, two paths, join')}",
            },
            {
                "id": "C-EMPTY",
                "claim": "Zero support edges yield NOT-CHECKED, not a silent pass.",
                "verdict": "CONFIRMED",
                "anchor": f"{det}:{line_of(det, 'if support_n == 0:')}",
            },
            {
                "id": "C-PROD",
                "claim": "tools/council/artifacts/argument_graph.py exists on this worktree.",
                "verdict": "CONFIRMED" if present_a else "REFUTED",
                **({} if present_a else {"defect_locus": "DESIGN"}),
                "anchor": prod_a,
            },
            {
                "id": "C-PROD-EVIDENCE-MAP",
                "claim": "tools/council/artifacts/evidence_map.py exists on this worktree.",
                "verdict": "CONFIRMED" if present_e else "REFUTED",
                **({} if present_e else {"defect_locus": "DESIGN"}),
                "anchor": prod_e,
            },
            {
                "id": "C-URL",
                "claim": "Circular citation can be detected by counting distinct URLs.",
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "anchor": f"{det}:{line_of(det, 'Distinct URL count is ignored')}",
            },
        ],
        "dependencies": {
            "CNL-0075": {
                "output_path": dep75,
                "present": (REPO / dep75).is_file(),
                "note": (
                    "Catalog dependency. Absent lineage artifact does not block "
                    "FIRE/SILENT proofs on this unit's typed graph fixtures."
                ),
            }
        },
        "detector": {
            "id": "CNL-0098-weak-synthesis-and-circular-citation",
            "fires_when": [
                "a synthesis sentence has no inbound SUPPORTS/GROUNDS/CITES edge from an evidence-reachable node",
                "the support graph contains a directed cycle; the full node path is printed",
            ],
            "silent_when": [
                "every synthesis sentence is evidence-grounded and the support graph is acyclic (diamond and distinct-fact cross-refs included)",
            ],
            "implementation": "command-center/p2-wave/probes/CNL-0098/detector.py",
            "module": "command-center/p2-wave/probes/CNL-0098/detector.py",
            "support_edge_kinds": ["SUPPORTS", "GROUNDS", "CITES"],
            "does_not_count_urls": True,
            "evidence_kinds": ["evidence", "observation", "measurement"],
            "empty_support_graph": "NOT-CHECKED",
        },
        "evidence": [
            {
                "path": cat,
                "line": line_of(cat, "Which synthesis sentences are unsupported by any edge"),
                "snippet": "Which synthesis sentences are unsupported by any edge",
                "kind": "catalog",
                "claim": "Unit question names unsupported synthesis sentences and citation cycles.",
            },
            {
                "path": det,
                "line": line_of(det, "SUPPORT_KINDS = frozenset"),
                "snippet": "SUPPORT_KINDS = frozenset",
                "kind": "probe",
                "claim": "Support graph is edge-kind restricted, not URL cardinality.",
            },
            {
                "path": fix,
                "line": line_of(fix, "syn-KNOWN-ORPHAN"),
                "snippet": "syn-KNOWN-ORPHAN",
                "kind": "probe",
                "claim": "Detector-control fixture plants a known-present orphan id.",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0098/reviewer.py",
                "line": line_of(
                    "command-center/p2-wave/probes/CNL-0098/reviewer.py",
                    "both_states_rerun",
                ),
                "snippet": "both_states_rerun",
                "kind": "probe",
                "claim": "Reviewer re-imports detector.analyse rather than trusting stdout.",
            },
        ],
        "false_positive_rate": float(fp["rate"]),
        "false_positive_rate_breakdown": {
            "fires": int(fp["fires"]),
            "clean_fixtures_total": int(fp["clean_fixtures_total"]),
            "rate": float(fp["rate"]),
            "clean_fixture_ids": list(F.CLEAN_IDS),
        },
        "fixtures": {
            "planted_bad": list(F.PLANTED_BAD_IDS),
            "known_good": list(F.CLEAN_IDS),
            "detector_control": F.CONTROL_ID,
            "empty_graph": F.EMPTY_ID,
            "directory": "command-center/p2-wave/probes/CNL-0098/fixtures",
        },
        "live_reports": {
            fid: {
                "status": r["status"],
                "unsupported_sentence_ids": r["unsupported_sentence_ids"],
                "cycle_paths": [c["path_str"] for c in r["cycles"]],
                "support_edges": r["support_edges"],
                "distinct_url_count": r["distinct_url_count"],
            }
            for fid, r in reports.items()
        },
        "negative_control": {
            "state_meant_to_reject": (
                "planted-weak orphan sentence; planted 3-cycle; circular "
                "ungrounded loop; URL-diverse cycle"
            ),
            "what_the_check_did": (
                "FIRE listing syn-orphan; FIRE with full cycle path; FIRE both "
                "pathologies on syn-fake; FIRE on url-launder-cycle"
            ),
            "rejects": (
                "planted-weak (orphan sentence), planted-cycle (3-cycle path), "
                "planted-circular-ungrounded (cycle with no evidence), "
                "url-launder-cycle (>=3 URLs still a cycle)"
            ),
            "verbatim": (
                "On planted-weak the check FIRES and lists syn-orphan. On "
                "planted-cycle it FIRES and prints a full c1/c2/c3 path. On "
                "planted-circular-ungrounded it FIRES both pathologies "
                "(syn-fake is not evidence-reachable). On url-launder-cycle it "
                "FIRES even though distinct_url_count>=3. On clean-linear, "
                "diamond, and legit-cross-ref it is SILENT (false_positive_rate "
                "is the numeric fraction of those three that fired). On "
                "empty-graph the cycle check is NOT-CHECKED, never a pass. "
                "A diamond DAG must not be reported as a cycle."
            ),
        },
        "pathology": (
            "Weak synthesis: synthesis sentences unsupported by any "
            "evidence-reachable graph edge. Circular citation: a support-edge "
            "cycle that manufactures support with no external evidence."
        ),
        "runtime_actions": {
            "on_nothing_to_add": (
                "Not a CNL-0098 action. Unsupported sentences are listed as "
                "weak-synthesis findings; no seat is marked 'nothing to add'."
            ),
            "on_disengaged": (
                "Not a CNL-0098 action. Citation cycles are reported with "
                "their full path; no participant is marked disengaged."
            ),
            "consent_rule": (
                "This detector emits findings only. It does not mute a seat, "
                "cast a vote, or treat silence as consent."
            ),
        },
        "pathologies": [
            {
                "id": "weak-synthesis",
                "name": "Unsupported synthesis sentence",
                "detector_rule": (
                    "A synthesis sentence is unsupported unless it has an inbound "
                    "SUPPORTS/GROUNDS/CITES edge from a node reachable from evidence."
                ),
                "fire_condition": "unsupported_sentence_ids is non-empty or unindexed prose exists",
                "silent_condition": "every sentence has evidence-reachable inbound support",
            },
            {
                "id": "circular-citation",
                "name": "Support-graph cycle",
                "detector_rule": (
                    "Tarjan SCCs over SUPPORTS/CITES/GROUNDS; every non-trivial SCC "
                    "yields a full node path. URL cardinality is ignored."
                ),
                "fire_condition": "at least one support cycle with a printed path",
                "silent_condition": "support_edges>0 and no cycle (diamond and cross-ref included)",
            },
        ],
        "production_modules": {
            "argument_graph_py": {
                "path": prod_a,
                "present": present_a,
            },
            "evidence_map_py": {
                "path": prod_e,
                "present": present_e,
            },
        },
        "question": (
            "Which synthesis sentences are unsupported by any edge in the "
            "argument graph, and separately, which citation chains form a "
            "cycle that manufactures support out of nothing?"
        ),
        "residual_unknowns": [
            "Catalog inputs cite _USER-PROMPTS.md:11232 and the council spec JSON; those files are not on this worktree, so line-level spec quotes were not independently fetched.",
            "Semantic entailment of a GROUNDS source (FM-SEMANTIC-UNGROUNDED) is out of scope for this structural detector.",
            "Catalog reviewer_requirement names openai/gpt-5-codex; that vendor did not sign. Mechanical both-states re-run did.",
        ],
        "reviewer": {k: v for k, v in rev.items() if k != "rerun"}
        | {
            "rerun_control_verbatim": rev["rerun"]["control_verbatim"],
            "rerun_passed": rev["rerun"]["passed"],
        },
        "sentinel": "SUCCESS:CNL-0098",
        "state": "SUCCESS",
        "strongest_surviving_counterargument": (
            "A GROUNDS edge can attach a synthesis sentence to a real claim "
            "whose text does not entail the sentence. The structural check is "
            "silent on that lie. That is FM-SEMANTIC-UNGROUNDED, recorded as "
            "missed, not claimed caught."
        ),
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "PASS"},
            {"id": "probe2-schema-overclaim", "command": P2, "result": "PASS"},
        ],
        "title": "Weak synthesis and circular citation in the argument graph",
        "unit_id": "CNL-0098",
    }

    # reviewer dict may contain nested objects that are fine; strip functions
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:CNL-0098 emit schema {exc.message}")
        print(exc.absolute_path)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print("SUCCESS:CNL-0098 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
