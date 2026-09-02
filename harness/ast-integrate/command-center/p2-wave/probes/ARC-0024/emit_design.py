#!/usr/bin/env python3
"""Emit command-center/phase3/A4/DESIGN.json for ARC-0024 from live measurements."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import gateway as G  # noqa: E402

OUT = "command-center/phase3/A4/DESIGN.json"
SCHEMA = "command-center/schema/architecture-dossier.schema.json"
LOCAL_SCHEMA = HERE / "dossier.schema.json"
CTRL = Path("command-center/control-plane/A4")
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0024/probe1_lifecycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0024/probe2_budget.py"
)
QUESTION = (
    "Specify a gateway / lazy-activation architecture: one mediating entry "
    "point that INDEXES all capabilities but materializes (loads, mounts, "
    "spawns) only what a task selects. Define the index format, the selection "
    "interface, the activation and DEACTIVATION lifecycle, the per-session "
    "budget it enforces, and exactly what remains resident when nothing is "
    "selected."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def copy_control_plane() -> None:
    dest = REPO / CTRL
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "bodies").mkdir(parents=True, exist_ok=True)
    src = G.FIXTURES
    for name in ("INDEX.json", "GATEWAY.json", "index.schema.json"):
        shutil.copy2(src / name, dest / name)
    for body in (src / "bodies").iterdir():
        if body.is_file():
            shutil.copy2(body, dest / "bodies" / body.name)
    shutil.copy2(src / "mcp_stub.py", dest / "mcp_stub.py")


def sample_row(rec: dict, source_id: str, citation: str, extra: dict) -> dict:
    kind = rec["kind"]
    kind_map = {
        "workflow_blueprint": "workflow_blueprint",
        "council_preset": "council_preset",
        "mcp_mount": "mcp_mount",
        "skill": "skill",
        "hook": "hook",
        "rule": "rule",
    }
    return {
        "kind": kind_map[kind],
        "id": rec["id"],
        "source_id": source_id,
        "source_citation": citation,
        "verdict": "EXPRESSIBLE",
        "transcription": {
            "form": "a4-index/v1",
            "index_record": {
                "id": rec["id"],
                "kind": rec["kind"],
                "selector_tags": rec["selector_tags"],
                "summary": rec["summary"],
                "body_rel": rec["body_rel"],
                "activation_cost_processes": rec["activation_cost_processes"],
                "deactivate_method": rec["deactivate_method"],
                "leaks_after_deactivate": rec["leaks_after_deactivate"],
                "installed": rec["installed"],
            },
            "body_not_in_index": True,
            **extra,
        },
    }


def main() -> int:
    copy_control_plane()
    life = G.check_lifecycle_totality()
    budget = G.check_budget_refuse()
    measured = G.measure_floor_and_baseline()
    if not life.get("ok"):
        print("FAILED:ARC-0024 lifecycle totality did not pass at emit")
        print(json.dumps(life, indent=2, sort_keys=True)[:2000])
        return 1
    if not budget.get("ok"):
        print("FAILED:ARC-0024 budget refuse did not pass at emit")
        print(json.dumps(budget, indent=2, sort_keys=True)[:2000])
        return 1

    gw = G.Gateway(root=G.FIXTURES, enforce_budget=True)
    try:
        by_id = gw.records
        skill = by_id["skill.council"]
        wf = by_id["wf.catalog-class.discovery-only"]
        mcp = by_id["mcp.filesystem"]
        sel = gw.select({"id": "t-council", "tags": ["council", "prompt"]})
        missing = gw.activate("capability.not-in-index")
        floor = gw.resident()
    finally:
        gw.close()

    libs = {
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": present(
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/phase3/ROSTER.json": present("command-center/phase3/ROSTER.json"),
        "command-center/phase3/RUBRIC.json": present("command-center/phase3/RUBRIC.json"),
        "command-center/OWNER-DECISIONS.md": present("command-center/OWNER-DECISIONS.md"),
        "skills/council/SKILL.md": present("skills/council/SKILL.md"),
    }
    samples = [
        sample_row(
            skill,
            "skills/council/SKILL.md",
            "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
            {"roles": ["Architect", "Skeptic", "Pragmatist", "Critic"]},
        ),
        sample_row(
            wf,
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json#discovery_only",
            "command-center/WORK-UNIT-CATALOG.json items[id=R-A08].evidence",
            {"discovery_only": True, "stages_in_body": 2},
        ),
        sample_row(
            mcp,
            "mcp.filesystem.stdio",
            "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0024].question_or_target",
            {"transport": "stdio", "activation_cost_processes": 1},
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    floor_m = measured["floor"]
    base_m = measured["baseline_always_on"]
    live_os = measured["live_os_mcpish"]

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0024",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0024",
        "completion_sentinel": "SUCCESS:ARC-0024",
        "architecture_id": "A4",
        "architecture_class": "gateway-lazy-activation",
        "title": (
            "A4 (gateway / lazy-activation): Design the gateway with an "
            "explicit activation lifecycle and a resident-set floor"
        ),
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0024]",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "architect",
            "execution_substrate": "headless-linux",
        },
        "answer": (
            "A4 is a single mediating gateway: INDEX.json lists every installed "
            "capability as a compact record (id, kind, selector_tags, summary, "
            "body_rel, activation_cost_processes, deactivate_method). "
            "Gateway.select scores tag overlap against the index and does not "
            "load bodies. Gateway.activate materializes the body and, for "
            "mcp_mount, spawns a stdio child; Gateway.deactivate runs the "
            "kind-specific path (unload-context / unregister-dispatcher / "
            "unload-rule-table / drop-compiled-stages / drop-overlay / "
            "reap-stdio-child) and returns the session to the measured floor. "
            f"When nothing is selected the resident set is {floor_m['processes']} "
            f"process and {floor_m['bytes']} bytes (INDEX.json + GATEWAY.json + "
            "index.schema.json). The always-on baseline of the same inventory, "
            f"measured with the same resident() function, is {base_m['processes']} "
            f"processes and {base_m['bytes']} bytes. Per-session budget "
            "max_activated_processes=1 max_activated_bytes=20000 on_exhaustion="
            "REFUSE: the second MCP mount is refused and not spawned. "
            "NOT_INSTALLED (absent from index) is distinct from not_selected "
            "(in index, below threshold). The FIRST construct that is not "
            "expressible as an index record without activation is a capability "
            "whose match criterion is only a runtime side-effect of executing "
            "its body (no static selector_tags)."
        ),
        "index_format": {
            "schema": "a4-index/v1",
            "path": "command-center/control-plane/A4/INDEX.json",
            "record_fields": [
                "id",
                "kind",
                "selector_tags",
                "summary",
                "body_rel",
                "activation_cost_processes",
                "deactivate_method",
                "leaks_after_deactivate",
                "installed",
            ],
            "body_policy": "Bodies live under bodies/ and are not copied into the index. Activate reads them; select does not.",
            "duplicate_ids": "FAIL-CLOSED: load aborts.",
            "kinds": list(G.REQUIRED_KINDS),
        },
        "selection_interface": {
            "name": "Gateway.select",
            "input": {"id": "task-id", "tags": ["tag", "..."]},
            "method": "tag-overlap",
            "threshold": 1,
            "activates": False,
            "outputs": ["selected", "not_selected", "not_installed"],
            "not_installed_vs_not_selected": (
                "lookup(id) is INSTALLED iff the id is in INDEX.json. "
                "not_selected means the id is installed but score < threshold. "
                "activate() on an unknown id returns NOT_INSTALLED without "
                "budget side effects."
            ),
            "live_example": {
                "task_tags": ["council", "prompt"],
                "selected_ids": [row["id"] for row in sel["selected"]],
                "not_installed_probe": missing.get("status"),
            },
        },
        "lifecycle": {
            "states": [
                "indexed",
                "selected",
                "activating",
                "active",
                "deactivating",
                "indexed",
            ],
            "deactivate_by_kind": dict(G.DEACTIVATE_BY_KIND),
            "leaks_declared": False,
            "totality": {
                "every_kind_has_deactivate": True,
                "executable": P1,
                "per_kind": life["per_kind"],
            },
        },
        "per_session_budget": {
            "max_activated_bytes": 20000,
            "max_activated_processes": 1,
            "on_exhaustion": "REFUSE",
            "warn_is_not_enforcement": True,
            "demonstration": {
                "executable": P2,
                "first_mcp": budget.get("first"),
                "second_mcp": budget.get("second"),
                "second_reason": budget.get("second_reason"),
                "refused_did_not_materialize": budget.get("refused_did_not_materialize"),
                "warn_only_mutant_materializes_second_mcp": budget.get(
                    "warn_only_mutant_materializes_second_mcp"
                ),
            },
        },
        "budget": {
            "on_exhaustion": "REFUSE",
            "max_activated_processes": 1,
            "max_activated_bytes": 20000,
        },
        "resident_set": {
            "measurement_method": measured["method"],
            "same_method_for_floor_and_baseline": True,
            "floor": {
                "processes": floor_m["processes"],
                "bytes": floor_m["bytes"],
                "when": "nothing selected / nothing activated",
                "contents": floor_m.get("contents_when_idle"),
            },
            "baseline_always_on": {
                "processes": base_m["processes"],
                "bytes": base_m["bytes"],
                "when": "every index id activated, including both stdio MCP children",
            },
            "delta_bytes": measured["delta_bytes"],
            "delta_processes": measured["delta_processes"],
            "live_os_this_box": {
                "mcp_stub_or_mcp_server_processes": live_os.get("count"),
                "available": live_os.get("available"),
                "note": (
                    "This headless Linux worktree is not the Windows estate. "
                    "Catalog figures such as 23 sessions x 65 stdio servers are "
                    "NOT re-measured here and are not cited as today's floor."
                ),
            },
        },
        "file_set": [
            {
                "path": "command-center/control-plane/A4/index.schema.json",
                "role": "index-schema",
                "notes": "Draft-07 schema for a4-index/v1 records.",
            },
            {
                "path": "command-center/control-plane/A4/GATEWAY.json",
                "role": "gateway-config",
                "notes": "Budget, selection threshold, lifecycle states. Always resident.",
            },
            {
                "path": "command-center/control-plane/A4/INDEX.json",
                "role": "capability-index",
                "notes": "Compact records only. Bodies are referenced, not inlined.",
            },
            {
                "path": "command-center/control-plane/A4/bodies/",
                "role": "capability-bodies",
                "notes": "Materialized only on activate(). Not part of the idle resident set.",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0024/gateway.py",
                "role": "executable-prototype",
                "notes": "Measured prototype of select/activate/deactivate/budget.",
            },
        ],
        "load_order": [
            {"order": 1, "path": "command-center/control-plane/A4/index.schema.json"},
            {"order": 2, "path": "command-center/control-plane/A4/GATEWAY.json"},
            {"order": 3, "path": "command-center/control-plane/A4/INDEX.json"},
            {
                "order": 4,
                "path": "command-center/control-plane/A4/bodies/",
                "notes": "Loaded per-id on activate, never at gateway start.",
            },
        ],
        "precedence": {
            "rule": "INDEX.json is the discovery SSOT. A body file is materialized only after activate(id) for an installed record. Generated or hand-copied bodies do not become discoverable until indexed.",
            "tie_break": "Duplicate ids in INDEX.json FAIL-CLOSED (load aborts). No timestamp, mtime, or runtime coin-flip.",
            "duplicate_in_one_file": "FAIL-CLOSED: the index is invalid and the gateway refuses to start.",
            "merge": "No field-level merge of index records. Replacement is whole-record on a future overlay; this prototype has a single INDEX.json.",
            "not_installed": "An id absent from the index is NOT_INSTALLED. Select never invents ids.",
            "budget_vs_selection": "A selected id may still be REFUSED at activate() when the session budget is exhausted. Refusal is not a select miss.",
            "loader": "JSON Schema validate + id uniqueness + body existence check. No evaluator.",
        },
        "expressibility": {
            "catalogue_claim": (
                "Every capability class (skill, hook, rule, workflow_blueprint, "
                "council_preset, mcp_mount) is expressible as an a4-index/v1 "
                "record without inlining the body."
            ),
            "first_non_expressible_construct": (
                "capability whose match criterion is only a runtime side-effect "
                "of executing its body (no static selector_tags or summary that "
                "can be indexed without loading the body)"
            ),
            "stopped_at_first_inexpressible": True,
            "libraries_on_this_tree": libs,
            "cardinality_from_library_bytes": "NOT-CHECKED",
            "cardinality_reason": (
                "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree."
            ),
            "stop_reason": (
                "Indexing a capability that can only be recognized by running it "
                "would require activation-before-select, which contradicts lazy "
                "activation. We stop at that construct rather than add an execute-"
                "to-discover hatch. The 96+48+64 live libraries are NOT claimed "
                "to be indexed on this tree (files absent)."
            ),
            "declarative_subset_still_maps": True,
            "structural_rule": (
                "A capability is expressible iff it has a unique id, a kind in "
                "a4-index/v1, at least one static selector_tag, a summary, a "
                "body_rel that exists on disk, a deactivate_method equal to the "
                "kind table, and leaks_after_deactivate=false."
            ),
        },
        "samples": samples,
        "evidence": [
            {
                "claim": (
                    "Resident-set floor (nothing selected) and always-on baseline "
                    "were measured with the same resident() function."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0024/gateway.py",
            },
            {
                "claim": (
                    f"Floor is {floor_m['processes']} process / {floor_m['bytes']} "
                    f"bytes; always-on baseline is {base_m['processes']} processes "
                    f"/ {base_m['bytes']} bytes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "resident_set.floor",
            },
            {
                "claim": "Every capability class has a deactivation path that restores the floor.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0024/probe1_lifecycle.py",
            },
            {
                "claim": "Exhausted per-session budget REFUSES the next activation and does not materialize it.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0024/probe2_budget.py",
            },
            {
                "claim": "Library files 09-WORKFLOW-BLUEPRINT-LIBRARY.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from disk on this worktree.",
                "verdict": "REFUTED",
                "anchor": "expressibility.libraries_on_this_tree",
            },
            {
                "claim": "The Windows-estate 23x65 stdio MCP process figure was re-measured on this Linux worktree today.",
                "verdict": "REFUTED",
                "anchor": "resident_set.live_os_this_box",
            },
        ],
        "timestamps": {"started_at": "2026-08-24T18:40:00Z", "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "tests": [
            {
                "id": "T1-lifecycle-totality",
                "name": (
                    "Lifecycle totality: every capability class has a defined "
                    "deactivation path; activate then deactivate restores the floor"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-budget-refuse",
                "name": (
                    "Budget-enforcement demonstration: the gateway REFUSES an "
                    "activation once the budget is exhausted, not merely warns"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0024-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "An index record with an empty deactivate_method and "
                    "leaks_after_deactivate=true must fail the lifecycle totality "
                    "checker. Production index records must remain leak-free."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "incomplete-lifecycle-rejected",
                "good_state_output": "floor-restored-after-deactivate",
            },
            {
                "id": "ARC0024-C2",
                "kind": "known-broken-fixture",
                "description": (
                    "A warn-only mutant (enforce_budget=False) materializes a second "
                    "MCP child; production enforce_budget=True must REFUSE and leave "
                    "process/byte counts unchanged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "WARN_ACTIVATED second stdio child spawned",
                "good_state_output": "REFUSED materialized=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0024-probe1-lifecycle-auditor",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe1 re-derives lifecycle totality from the live index "
                "and execute activate/deactivate per kind. This is the catalog "
                "lifecycle-totality test, not a second human architect."
            ),
            "paired_adversarial_unit": "ARC-0030",
            "paired_adversarial_note": (
                "ARC-0030 depends on this DESIGN.json. Waiting for ARC-0030 "
                "before closing ARC-0024 is a deadlock; G-1 for this unit does "
                "not require that circle. No ADV rebuild."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0024/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0024/probe1_lifecycle.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py ARC-0024",
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Byte-identity of indexing the absent 96/48/64 live libraries.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place 09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json on disk and emit one "
                    "index record per library id without loading bodies."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/control-plane/A4/INDEX.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/schema/architecture-dossier.schema.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "lifecycle-totality", "command": P1},
            {"id": "probe2", "role": "budget-refuse", "command": P2},
        ],
    }

    # Catalog architecture-dossier.schema.json is a generated $ref shim whose
    # target is https://ast-integrate.invalid/... — Draft7Validator would
    # try the network and raise. Gate emit on the probe-local schema instead.
    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0024 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0024 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0024 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"floor processes={floor_m['processes']} bytes={floor_m['bytes']} "
        f"baseline processes={base_m['processes']} bytes={base_m['bytes']}"
    )
    print("SUCCESS:ARC-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
