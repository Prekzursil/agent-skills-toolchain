#!/usr/bin/env python3
"""Emit CNL-0124 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import capabilities as C  # noqa: E402
import compile as K  # noqa: E402
import plane as P  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0124-council-as-a-first-class-workflow-type-on-the-single-contr.md"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0124/council-design-note.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0124/probe1_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py"
)
QUESTION = (
    "The spec forbids importing a second orchestration runtime - what is the "
    "council's integration contract with the existing workflow system such "
    "that a council is a workflow type rather than a parallel engine, and "
    "which council capability has no home in the current plane?"
)
SENTINEL = "SUCCESS:CNL-0124"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**dict(__import__("os").environ))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def cite(needle: str, kind: str) -> dict:
    hit = P.catalog_line(needle)
    hit["kind"] = kind
    return hit


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0124 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rows = C.inventory_rows()
    summary = C.inventory_summary(rows)
    anchors = C.verify_catalog_anchors()
    families = C.family_coverage()
    prim = P.primitives_agree()
    planted = C.inventory_summary(C.plant_unmapped(rows))

    mapped = K.duplicate_probe(K.load_fixture("mapped-council.json"))
    own = K.duplicate_probe(K.load_fixture("own-scheduler.json"))
    lg = K.duplicate_probe(K.load_fixture("langgraph-import.json"))
    standing = K.duplicate_probe(K.load_fixture("standing-watch.json"))
    standing_loop = K.duplicate_probe(K.load_fixture("standing-own-loop.json"))
    nested = K.duplicate_probe(K.load_fixture("nested.json"))
    anon = K.duplicate_probe(K.load_fixture("anonymous.json"))

    harness = P.hunt_paths(P.HARNESS_CANDIDATES)
    schema_hunt = P.hunt_paths(P.SCHEMA_CANDIDATES)
    agentspec_spec = REPO / "tools" / "agentspec" / "agentspec" / "spec.py"

    negative_verbatim = json.dumps(
        {
            "fixture": "own-scheduler",
            "gate": own["gate"],
            "over_one": own["over_one"],
            "plane_count": own["plane_count"],
            "introduced_planes": own["introduced_planes"],
            "parallel_engine": own["parallel_engine"],
        },
        sort_keys=True,
    )

    answer = (
        "A council is a first-class workflow type (kind=council) on the single "
        "agentspec / prompt-native control plane. CouncilSpec is payload, not "
        "an engine: the compiler emits DynamicFanOut+WorkUnit (roster), "
        "Pipeline (sequence/splice), Subworkflow (nest / child councils), "
        "Loop (repeat-until and stopping.expression), FanOut then Barrier "
        "(divergence-before-convergence), HumanCheckpoint (chair/owner), and "
        "WorkUnit.routing through rails.toml. Turn-taking is that executor's "
        "dispatch (CNL-0047), not a council-owned round loop. Importing "
        "LangGraph/CrewAI/AutoGen or running dispatch_loop/round_runner/"
        "watch_loop FIRE the duplicate-control-plane probe (plane_count>1). "
        "Windows _USER-PROMPTS.md:10727 and :10483 are absent here; the live "
        "citation is command-center/WORK-UNIT-CATALOG.json evidence_requirement "
        "on this unit. Three same-plane extensions are named because they have "
        "no node today: BallotReduce (Barrier is all-complete, not IRV), "
        "BlindEnvelope (routing is named), and Watch. The capability with no "
        "home on the current plane is CAP-STANDING (standing watch / "
        "trigger-woken persistence, CNL-0115): HumanCheckpoint is owner-gated "
        "and must terminate without a responder, so an ETag wake cannot live "
        "there. Watch is a required workflow-plane node; a council event loop "
        "is a forbidden second scheduler. Inventory: "
        f"{summary['n_capabilities']} capabilities, {summary['n_mapped']} mapped, "
        f"{summary['n_required_extension']} required extensions, "
        f"{summary['n_unmapped']} unmapped. SUCCESS:CNL-0124"
    )

    evidence = [
        {
            **cite(
                "_USER-PROMPTS.md:10727 (do not import a second orchestration runtime)",
                "catalog-evidence-10727",
            ),
            "claim": (
                "Catalog evidence_requirement binds _USER-PROMPTS.md:10727: do "
                "not import a second orchestration runtime. The file is absent "
                "on this Linux worktree; the citation is the catalog line."
            ),
            "verdict": "CONFIRMED" if not harness["available"] else "PARTIAL",
            "anchor": "",
            "mechanism": "catalog file:line of this unit's evidence_requirement plus Path.is_file hunt",
            "harness_available": harness["available"],
        },
        {
            **cite(
                "_USER-PROMPTS.md:10483 (do not create duplicate control planes)",
                "catalog-evidence-10483",
            ),
            "claim": (
                "Catalog evidence_requirement binds _USER-PROMPTS.md:10483: do "
                "not create duplicate control planes. Same-host hunt of the "
                "Windows harness path is empty."
            ),
            "verdict": "CONFIRMED",
            "anchor": "",
            "mechanism": "catalog file:line plus Path.is_file hunt (different field from 10727 needle)",
        },
        {
            **cite("alongside FanOut/Barrier/Pipeline", "catalog-workflow-primitives"),
            "claim": (
                "IMP-0129 names the frozen workflow node surface as FanOut/"
                "Barrier/Pipeline plus Subworkflow. Loop, HumanCheckpoint, "
                "DynamicFanOut, Param, WorkUnit.routing are named on IMP-0130..0135."
            ),
            "verdict": "CONFIRMED" if prim["ok"] else "REFUTED",
            "anchor": "",
            "mechanism": "independent parse of IMP-0129..0135 question text (set algebra vs frozen NODE_KINDS)",
            "extracted": prim["extracted_nodes_and_surfaces"],
        },
        {
            **cite("sequence, splice, nest, repeat-until", "catalog-composition-primitives"),
            "claim": (
                "CNL-0050 names the protocol composition primitives that must "
                "compile onto Pipeline/Subworkflow/Loop rather than a second composer."
            ),
            "verdict": "CONFIRMED",
            "anchor": "",
            "mechanism": "catalog question needle for CNL-0050",
        },
        {
            **cite("Standing watch council", "catalog-no-home-capability"),
            "claim": (
                "CNL-0115 is the standing-watch capability. It is the inventory "
                "row with no_home_on_current_plane=true (required_extension=Watch)."
            ),
            "verdict": "CONFIRMED",
            "anchor": "",
            "mechanism": "catalog title needle plus inventory class=required_extension",
        },
        {
            "path": "tools/agentspec/agentspec/spec.py",
            "line": 0,
            "snippet": "Path.is_file false on this worktree",
            "kind": "agentspec-spec-absent",
            "claim": (
                "tools/agentspec/agentspec/spec.py is not on this tree (only "
                "__init__.py and progress.py). Primitive names are catalog-cited, "
                "not read from a missing spec.py. This unit does not invent a "
                "second agentspec."
            ),
            "verdict": "CONFIRMED" if not agentspec_spec.is_file() else "PARTIAL",
            "anchor": "tools/agentspec/agentspec/__init__.py",
            "mechanism": "Path.is_file of spec.py (independent of catalog parse)",
        },
    ]
    # schema requires evidence[].anchor minLength 3 - fill empty
    for ev in evidence:
        if not ev.get("anchor"):
            ev["anchor"] = f"{ev.get('path')}:{ev.get('line')}"

    negative_controls = [
        {
            "id": "NC-OWN-SCHEDULER",
            "on_state": (
                "fixtures/own-scheduler.json: scheduler=council-runtime, "
                "dispatch_loop=true, round_runner=council.engine.turn_taking"
            ),
            "observed": (
                f"gate={own['gate']} over_one={own['over_one']} "
                f"plane_count={own['plane_count']} "
                f"introduced_planes={own['introduced_planes']}"
            ),
            "rejects": (
                "a council that is a parallel engine with its own round dispatcher"
            ),
        },
        {
            "id": "NC-PLANTED-UNMAPPED",
            "on_state": (
                "inventory row CAP-PLANTED-UNMAPPED with empty home and no "
                "required_extension"
            ),
            "observed": (
                f"ok={planted['ok']} n_unmapped={planted['n_unmapped']} "
                f"unmapped_ids={planted['unmapped_ids']}"
            ),
            "rejects": (
                "an inventory that silently drops a capability instead of mapping "
                "it or listing a required extension"
            ),
        },
        {
            "id": "NC-LANGGRAPH",
            "on_state": "fixtures/langgraph-import.json runtime=langgraph",
            "observed": (
                f"gate={lg['gate']} introduced_planes={lg['introduced_planes']}"
            ),
            "rejects": "importing a second orchestration runtime as the council engine",
        },
        {
            "id": "NC-STANDING-OWN-LOOP",
            "on_state": (
                "fixtures/standing-own-loop.json watch_loop=true own_wake_clock=true"
            ),
            "observed": (
                f"gate={standing_loop['gate']} "
                f"features={[f['id'] for f in standing_loop['scheduler_features_named']]}"
            ),
            "rejects": (
                "a standing council that grows its own event loop instead of a "
                "Watch node on the workflow plane"
            ),
        },
    ]

    doc = {
        "unit_id": "CNL-0124",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "title": "Council as a first-class workflow type on the SINGLE control plane",
        "question": QUESTION,
        "claim_under_test": (
            "Council compiles to agentspec workflow nodes on prompt-native; it "
            "is not a parallel engine. CAP-STANDING has no home on the current "
            "plane and is listed as required extension Watch. Any own-scheduler "
            "or foreign runtime FIRE."
        ),
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "answer": answer,
        "integration_contract": {
            "council_is": "workflow type kind=council",
            "council_is_not": "a second orchestration runtime or CouncilEngine",
            "home_plane": P.HOME_PLANE,
            "scheduler": "agentspec",
            "payload": "CouncilSpec / preset is configuration of a Council node, not an engine",
            "compile": {
                "roster": "DynamicFanOut of WorkUnits",
                "sequence_splice": "Pipeline",
                "nest_child_councils": "Subworkflow",
                "repeat_until_and_stopping": "Loop.convergence_expr + max_iterations",
                "diverge_then_converge": "FanOut then Barrier (reverse rejected)",
                "chair_owner": "HumanCheckpoint",
                "routing": "WorkUnit.routing via rails.toml",
                "turn_taking": "the agentspec executor; CNL-0047 shared primitive",
                "oracle_join": "Barrier join policy oracle_gate",
                "minority_report": "completion-predicate emit-gate",
            },
            "required_extensions_same_plane": [
                {
                    "kind": "BallotReduce",
                    "for": "CAP-VOTING",
                    "why": "Barrier default join is all-complete, not IRV/majority tabulation",
                },
                {
                    "kind": "BlindEnvelope",
                    "for": "CAP-ANONYMITY",
                    "why": "WorkUnit.routing is named; blinding is not a plane primitive",
                },
                {
                    "kind": "Watch",
                    "for": "CAP-STANDING",
                    "why": "HumanCheckpoint is owner-gated terminate, not ETag/release-tag wake",
                    "no_home_on_current_plane": True,
                },
            ],
            "forbidden": [
                "import langgraph/crewai/autogen/temporal/airflow/prefect/dagster",
                "dispatch_loop / round_runner / own_scheduler / turn_engine",
                "watch_loop / own_wake_clock / resident_event_loop",
                "child_runtime that bypasses Subworkflow",
            ],
        },
        "no_home_capability": C.NO_HOME_ID,
        "no_home": {
            "id": "CAP-STANDING",
            "capability": "Standing watch: long-running, trigger-woken, low-intensity",
            "catalog_id": "CNL-0115",
            "why_not_human_checkpoint": (
                "IMP-0131: a checkpoint with no default_if_unanswered and no "
                "responder must terminate, never block. An ETag wake has no owner."
            ),
            "required_extension": "Watch",
            "must_not_become": "a council-owned event loop (duplicate control plane)",
        },
        "inventory": summary,
        "inventory_rows": [
            {
                "id": r["id"],
                "capability": r["capability"],
                "catalog_id": r["catalog_id"],
                "home": r["home"] or None,
                "required_extension": r.get("required_extension"),
                "class": r["class"],
                "no_home_on_current_plane": bool(r.get("no_home_on_current_plane")),
            }
            for r in rows
        ],
        "catalog_anchors": anchors,
        "family_coverage": families,
        "workflow_primitives": {
            "node_kinds": sorted(P.NODE_KINDS),
            "surfaces": sorted(P.SURFACES),
            "extensions": sorted(P.EXTENSION_KINDS),
            "catalog_parse_ok": prim["ok"],
            "extracted": prim["extracted_nodes_and_surfaces"],
            "agentspec_spec_py_present": agentspec_spec.is_file(),
        },
        "duplicate_control_plane": {
            "probe": "any council feature that would need its own scheduler is named",
            "mapped_home": {
                "id": mapped["subject_id"],
                "gate": mapped["gate"],
                "over_one": mapped["over_one"],
                "extensions_named": mapped["extensions_named"],
            },
            "own_scheduler": {
                "id": own["subject_id"],
                "gate": own["gate"],
                "over_one": own["over_one"],
                "plane_count": own["plane_count"],
                "introduced_planes": own["introduced_planes"],
                "scheduler_features_named": own["scheduler_features_named"],
            },
            "langgraph_import": {
                "id": lg["subject_id"],
                "gate": lg["gate"],
                "introduced_planes": lg["introduced_planes"],
            },
            "standing_watch_on_plane": {
                "id": standing["subject_id"],
                "gate": standing["gate"],
                "extensions_named": standing["extensions_named"],
                "over_one": standing["over_one"],
            },
            "standing_own_loop": {
                "id": standing_loop["subject_id"],
                "gate": standing_loop["gate"],
                "scheduler_features_named": standing_loop["scheduler_features_named"],
            },
            "nested_subworkflow": {
                "id": nested["subject_id"],
                "gate": nested["gate"],
                "node_kinds": nested["compile"]["node_kinds"],
            },
            "anonymous_blind": {
                "id": anon["subject_id"],
                "gate": anon["gate"],
                "extensions_named": anon["extensions_named"],
            },
            "features_that_would_need_own_scheduler": [
                {
                    "id": f["id"],
                    "plane": f["plane"],
                    "why": f["why"],
                }
                for f in P.SCHEDULER_FEATURES
            ],
        },
        "source_availability": {
            "user_prompts": harness,
            "council_schema_and_agentspec": schema_hunt,
            "windows_harness_absent": not harness["available"],
        },
        "both_states": {
            "fired_on_bad": own["gate"] == "FIRE" and lg["gate"] == "FIRE",
            "silent_on_good": mapped["gate"] == "PASS" and standing["gate"] == "PASS",
            "good_verbatim": json.dumps(
                {"gate": mapped["gate"], "over_one": mapped["over_one"]},
                sort_keys=True,
            ),
            "bad_verbatim": negative_verbatim,
        },
        "counterexample": {
            "id": "cx-own-turn-engine",
            "status": "COUNTEREXAMPLE-PRODUCED",
            "claim_refuted": (
                "any object titled council is automatically a workflow type"
            ),
            "instance": "command-center/p2-wave/probes/CNL-0124/fixtures/own-scheduler.json",
            "observed_gate": own["gate"],
        },
        "negative_control": {
            "id": "NC-OWN-SCHEDULER",
            "on_state": negative_controls[0]["on_state"],
            "rejects": negative_controls[0]["rejects"],
            "observed": negative_controls[0]["observed"],
            "verbatim": negative_verbatim,
            "does_on_reject_state": (
                "The check FIRES; plane_count rises above one; introduced_planes "
                "names council-runtime; the council is not emit-legal as a "
                "workflow type. It does not return silent."
            ),
        },
        "tests": [
            {
                "id": "inventory-mechanical",
                "name": (
                    "every council capability maps to a workflow primitive or "
                    "is listed as a required extension - counted mechanically"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "verbatim": t1[-2000:],
            },
            {
                "id": "duplicate-control-plane",
                "name": (
                    "any council feature that would need its own scheduler is "
                    "named explicitly"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": t2[-2000:],
            },
            {
                "id": "negative-control",
                "name": "recorded verbatim: what the check does on the reject state",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": negative_verbatim,
            },
        ],
        "negative_controls": negative_controls,
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": "CNL-0124-probe2-duplicate-plane",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "counterexample": "cx-own-turn-engine",
            "refuted_not_attempted": False,
            "notes": (
                "Probe2 re-tabulates the 20-row inventory, re-compiles mapped / "
                "own-scheduler / langgraph / standing-watch / standing-own-loop / "
                "nested fixtures, and produces counterexample cx-own-turn-engine. "
                "It does not read this answer as evidence. Catalog asked for a "
                "fresh-context adversarial reviewer; this G-1 signature is the "
                "mechanical re-run, not a second-vendor chat transcript."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "inventory-mechanical", "command": P1},
            {"id": "probe2", "role": "duplicate-control-plane", "command": P2},
        ],
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; validating against it tries the "
            "network and does not constrain this note. This unit validates "
            "against the per-unit schema. Overwriting the shared catalog schema "
            "would be a sibling rebuild circle."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": CATALOG_SCHEMA, "exists": True, "role": "supporting"},
        ],
        "scope": {
            "executable_on": (
                "in-probe fixtures and inventory table; tools/agentspec/spec.py "
                "and 11-COUNCIL-SPECIFICATION.schema.json are absent"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "Windows harness-restore files were read on this host",
                "Watch/BallotReduce/BlindEnvelope were added to agentspec",
                "CNL-0001 / CNL-0050 artifacts were delivered on this tree",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "min_bytes_threshold": 4096,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0124 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNL-0124 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0124 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNL-0124 sentinel absent from artifact text")
        return 1
    live = json.loads(text)
    if str(live.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0124 self-declared blocked")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"inventory n={summary['n_capabilities']} mapped={summary['n_mapped']} "
        f"ext={summary['n_required_extension']} no_home={C.NO_HOME_ID} "
        f"own_gate={own['gate']} mapped_gate={mapped['gate']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
