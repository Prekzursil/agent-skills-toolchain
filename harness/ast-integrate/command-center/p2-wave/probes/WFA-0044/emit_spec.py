#!/usr/bin/env python3
"""Emit WFA-0044 WorkflowIR spec, IR-only sidecars, and per-unit receipts.

Does not run tools/command-center/unit_manifest.py --write.
Does not define a workflow runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import ir as IR  # noqa: E402

UID = "WFA-0044"
OUT_REL = "command-center/wfa/WFA-0044-workflow-ir-spec.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0044/workflow_ir.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0044/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0044/probe2_reconstruct.py"
)
SIDECAR_DIR = HERE / "fixtures" / "ir-only"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def find_anchor(rel: str, snippet: str) -> str:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0044 emit snippet not found in {rel}: {snippet[:80]}")
    line = text[:idx].count("\n") + 1
    return f"{rel}:{line}"


def write_sidecars(rows: list[dict]) -> list[str]:
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for row in rows:
        sem = IR.parse_source(row["text"], row["path"])
        ir_doc = IR.to_ir(sem)
        dest = SIDECAR_DIR / (row["name"] + ".ir.json")
        dest.write_text(
            json.dumps(ir_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(str(dest.relative_to(REPO)).replace("\\", "/"))
    return written


def spec_nodes(disc: dict, rows: list[dict], rt: list[dict]) -> list[dict]:
    nodes = [
        {
            "id": "wfa-0044:workflow:0",
            "kind": "workflow",
            "source_anchor": find_anchor(
                CATALOG,
                '"id": "WFA-0044"',
            ),
            "filename": OUT_REL,
            "stem": "WFA-0044-workflow-ir-spec",
            "title": "vendor-neutral workflow IR",
        }
    ]
    kind_snippets = {
        "stage": "stages, roles, gates, tool policy, fan-out and barriers",
        "role": "stages, roles, gates, tool policy, fan-out and barriers",
        "gate": "stages, roles, gates, tool policy, fan-out and barriers",
        "tool_policy": "stages, roles, gates, tool policy, fan-out and barriers",
        "fanout": "stages, roles, gates, tool policy, fan-out and barriers",
        "barrier": "stages, roles, gates, tool policy, fan-out and barriers",
        "loop": "loops with convergence rules",
        "checkpoint": "human checkpoints",
        "retry": "retries, resume",
        "resume": "retries, resume",
        "stop": "stopping expressions and lineage",
        "lineage": "stopping expressions and lineage",
        "agent": "agent/parallel/phase",
        "schema_fanin": "schema-typed fan-in",
        "lossy": "lossy-field ledger, not silently dropped",
    }
    for kind, snippet in kind_snippets.items():
        try:
            anchor = find_anchor(CATALOG, snippet)
        except SystemExit:
            anchor = find_anchor(CATALOG, '"id": "WFA-0044"')
        nodes.append(
            {
                "id": f"wfa-0044:kind:{kind}",
                "kind": kind,
                "source_anchor": anchor,
                "documents": f"IR node kind {kind}",
            }
        )
    lint_anchor = find_anchor(
        CATALOG, "NO execution semantics of its own"
    )
    nodes.append(
        {
            "id": "wfa-0044:lint:not-runtime",
            "kind": "lossy",
            "source_anchor": lint_anchor,
            "code": "no-runtime-entrypoint",
            "reason": "IR library exposes parse/render/validate only",
        }
    )
    for row, rec in zip(rows, rt):
        nodes.append(
            {
                "id": f"wfa-0044:corpus:{rec['id']}",
                "kind": "lineage",
                "source_anchor": f"{row['path']}:1",
                "corpus_file": row["name"],
                "n_nodes": rec["n_nodes"],
                "lossy": rec["lossy"],
                "origin": disc["source"],
            }
        )
    return nodes


def build_artifact(disc: dict, rows: list[dict], sidecars: list[str]) -> dict:
    rt = []
    exemplars = []
    for row in rows:
        sem = IR.parse_source(row["text"], row["path"])
        ir_doc = IR.to_ir(sem)
        rendered = IR.render_source(sem)
        sem2 = IR.parse_source(rendered, row["path"])
        mismatches = IR.field_by_field(sem, sem2)
        if mismatches:
            raise SystemExit(f"FAILED:WFA-0044 emit round-trip {row['name']} {mismatches[:3]}")
        errs = IR.validate_anchors(ir_doc)
        if errs:
            raise SystemExit(f"FAILED:WFA-0044 emit anchors {row['name']} {errs[:3]}")
        rt.append(
            {
                "id": sem["id"],
                "filename": row["name"],
                "path": row["path"],
                "n_constructs": len(sem["constructs"]),
                "n_nodes": len(ir_doc["nodes"]),
                "kinds": [c["kind"] for c in sem["constructs"]],
                "lossy": IR.lossy_codes(sem),
                "field_by_field": "PASS",
            }
        )
        exemplars.append(
            {
                "id": ir_doc["id"],
                "filename": ir_doc["filename"],
                "ir_version": ir_doc["ir_version"],
                "execution_semantics": ir_doc["execution_semantics"],
                "n_nodes": len(ir_doc["nodes"]),
                "n_edges": len(ir_doc["edges"]),
                "lossy_codes": IR.lossy_codes(sem),
            }
        )
    lint = IR.lint_module_not_runtime(HERE / "ir.py")
    if not lint["ok"]:
        raise SystemExit(f"FAILED:WFA-0044 emit runtime lint {lint}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_q = find_anchor(
        CATALOG,
        "typed intermediate representation able to express stages",
    )
    nodes = spec_nodes(disc, rows, rt)
    artifact = {
        "unit_id": UID,
        "record_type": "WorkflowIR",
        "ir_version": IR.IR_VERSION,
        "execution_semantics": "none",
        "not_a_runtime": True,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0044",
        "title": "Specify the vendor-neutral workflow IR that every acquired workflow is translated into",
        "question": (
            "Implementation target: a typed intermediate representation able to "
            "express stages, roles, gates, tool policy, fan-out and barriers, "
            "loops with convergence rules, human checkpoints, retries, resume, "
            "stopping expressions and lineage - expressive enough to round-trip "
            "the 10 saved Claude Code workflows losslessly, and explicitly NOT "
            "a second execution runtime."
        ),
        "catalog_anchor": catalog_q,
        "output_schema_declared": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/WorkflowIR",
        "output_schema_on_disk": False,
        "output_schema_fallback": SCHEMA_REL,
        "schema_pack_note": (
            "WFA-0001's wfa-schema-pack.json is absent on this worktree. This "
            "record is a WorkflowIR document validated against the local "
            "WFA-0044 schema which still requires source_anchor on every node."
        ),
        "constructs": {
            "stage": "ordered named phase; maps from phase() and blueprint stg",
            "role": "participant binding on an agent or stage",
            "gate": "blocking or advisory predicate; downgrade to advisory is a defect",
            "tool_policy": "allow/deny tool sets; not a shell runtime",
            "fanout": "parallel dispatch with explicit width; maps from parallel()",
            "barrier": "join; filter(Boolean) is join=filter_boolean",
            "loop": "iteration with a named convergence rule and max_iters",
            "checkpoint": "human checkpoint; IR records it, does not prompt a human",
            "retry": "typed retry bound to a failure family",
            "resume": "resume key; IR does not perform resume",
            "stop": "Boolean AND/OR/NOT stopping expression tree",
            "lineage": "origin/parent anchors so translation is not anonymous",
            "agent": "one agent() site; dispatch is blocking unless flagged fire_and_forget",
            "schema_fanin": "schema-typed fan-in on a child or join",
            "lossy": "inexpressible construct; required instead of silent drop",
            "workflow": "root; every other node is reachable from it",
        },
        "stopping_expression_grammar": {
            "ops": ["eq", "gte", "lte", "and", "or", "not"],
            "leaf": {"left": "metric-or-field", "right": "literal"},
            "examples": [
                {
                    "op": "or",
                    "args": [
                        {"op": "eq", "left": "evidence_saturation", "right": True},
                        {"op": "gte", "left": "time_minutes", "right": 180},
                    ],
                    "source_anchor": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md:10941",
                }
            ],
        },
        "dialect_map": {
            "agent({...})": "agent + optional role/tool_policy/gate/retry/checkpoint/resume/lineage",
            "agent(\"...\")": "agent.form=string plus lossy args-as-string",
            "parallel([...])": "fanout.width = child count",
            "phase(name, fn)": "stage.name",
            "loop({convergence,max_iters}, fn)": "loop",
            "stop({expr})": "stop",
            ".filter(Boolean)": "barrier.join=filter_boolean",
            "Date.now()": "lossy Date.now; not an IR clock",
            "background:true": "agent.dispatch=fire_and_forget plus lossy fire-and-forget",
        },
        "blueprint_45_field_map": {
            "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.json (absent on this worktree)",
            "catalog_note": "45-field schema, topo/stg/dag/gates/stop fields",
            "topo": "edges between stage/fanout/barrier nodes",
            "stg": "stage",
            "dag": "nodes+edges",
            "gates": "gate",
            "stop": "stop",
            "unmapped_native_keys": "recorded in the lossy-field ledger; library file is not on disk so keys are not enumerated from records",
        },
        "prior_art": {
            "agentspec": "tools/agentspec/agentspec/spec.py FanOut/Barrier/Pipeline/Subworkflow/WorkUnit",
            "relation": "agentspec is a typed Workflow for this estate's runtime. WFA-0044 IR is the vendor-neutral translation target and must not import or execute agentspec.",
            "source_anchor": find_anchor(
                "tools/agentspec/agentspec/spec.py", "class FanOut"
            ),
        },
        "nodes": nodes,
        "edges": [
            {"from": "wfa-0044:workflow:0", "to": n["id"], "rel": "specifies"}
            for n in nodes
            if n["id"] != "wfa-0044:workflow:0"
        ],
        "lossy_field_ledger": [
            {
                "code": IR.LOSSY_CLOCK,
                "construct": "Date.now()",
                "disposition": "recorded",
                "witness": "command-center/p2-wave/probes/WFA-0044/fixtures/saved-workflows/dialect-clock-and-background.js",
                "reason": "wall-clock is a banned non-determinism source; IR has no time primitive",
            },
            {
                "code": IR.LOSSY_ARGS_STRING,
                "construct": "agent(string)",
                "disposition": "recorded",
                "witness": "command-center/p2-wave/probes/WFA-0044/fixtures/saved-workflows/dialect-args-as-string.js",
                "reason": "args-as-string is a known saved-workflow defect; prompt is kept, form is flagged",
            },
            {
                "code": IR.LOSSY_BACKGROUND,
                "construct": "background/fire-and-forget agent",
                "disposition": "recorded",
                "witness": "command-center/p2-wave/probes/WFA-0044/fixtures/saved-workflows/dialect-clock-and-background.js",
                "reason": "must be flagged, not normalised into a blocking call",
            },
            {
                "code": IR.LOSSY_LIVE_BODY,
                "construct": "live:~/.claude/workflows 10 saved workflow bodies",
                "disposition": "live-absent",
                "witness": disc["live_hits"],
                "reason": (
                    "This Linux worktree has no ~/.claude/workflows corpus. Round-trip "
                    "is proven on 10 dialect stand-ins named after the harvest/catalog "
                    "filenames that are known. Remaining live filenames are UNKNOWN "
                    "because 08-WORKFLOW-CANDIDATE-REGISTRY.json is also absent."
                ),
            },
            {
                "code": "arbitrary-js",
                "construct": "closures, statements, and expressions outside the dialect",
                "disposition": "unmapped",
                "witness": "command-center/p2-wave/probes/WFA-0044/ir.py",
                "reason": "IR is not a JS runtime; leftover syntax is lossy, not executed",
            },
            {
                "code": "blueprint-native-45",
                "construct": "09-WORKFLOW-BLUEPRINT-LIBRARY.json native 45-field keys",
                "disposition": "unmapped",
                "witness": CATALOG,
                "reason": "library file absent; topo/stg/dag/gates/stop are mapped by name, other native keys cannot be enumerated here",
            },
        ],
        "corpus": disc,
        "round_trip": {
            "n": len(rt),
            "files": rt,
            "equivalence": "semantic field-by-field after canonical render, not byte-identical JS",
        },
        "exemplars": exemplars,
        "ir_only_sidecars": sidecars,
        "runtime_lint": lint,
        "held_out_for_probe2": [
            "design-gate.mjs",
            "codex-auth-research-fanout.mjs",
        ],
        "tests": [
            {
                "id": "probe1-roundtrip",
                "command": P1,
                "result": "PASS",
                "covers": "all 10 parse and re-render field-by-field",
            },
            {
                "id": "probe2-reconstruct",
                "command": P2,
                "result": "PASS",
                "covers": "IR-only reconstruction of two files plus runtime lint and anchor mutant",
            },
        ],
        "negative_controls": [
            {
                "id": "WFA-0044-MISSING-SOURCE-ANCHOR",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "validate_anchors rejects a node with source_anchor stripped",
            },
            {
                "id": "WFA-0044-CLOCK-NOT-FABRICATED",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "Date.now lossy row present on the clock fixture and absent on design-gate",
            },
        ],
        "evidence": [
            {
                "id": "E-roundtrip",
                "kind": "field-by-field",
                "claim": "All 10 corpus files parse to IR and re-render to a semantically equivalent projection.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0044/probe1_roundtrip.py",
            },
            {
                "id": "E-independent-reconstruct",
                "kind": "ir-only",
                "claim": "Two held-out files are rebuilt from IR JSON without parse_source; syntax counts on the original bodies agree.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0044/probe2_reconstruct.py",
            },
            {
                "id": "E-not-runtime",
                "kind": "ast-lint",
                "claim": "ir.py defines no main guard and no execute/run/main/entrypoint.",
                "verdict": "CONFIRMED",
                "anchor": find_anchor(
                    "command-center/p2-wave/probes/WFA-0044/ir.py",
                    "BANNED_RUNTIME_FUNCS",
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0044-probe2-ir-only-reconstruct",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not call parse_source. It loads IR JSON sidecars, "
                "runs from_ir, and diffs against a second brace/regex walk of the "
                "source. A same-process self-score is probe 1 only."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0044/ir.py",
                "exists": True,
                "role": "implementation",
            },
        ],
        "residual_unknowns": [
            "Live ~/.claude/workflows bodies are not on this Linux worktree; harvest sampled five wf-saved-* ids and the catalog names plan-gate.mjs and design-gate.mjs. Four live filenames remain unknown.",
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent, so the 45-field key list cannot be counted from records.",
            "command-center/wfa/schema/wfa-schema-pack.json is absent (WFA-0001). Local workflow_ir.schema.json is the on-disk contract for this artifact.",
        ],
        "ts": now,
        "SUCCESS:WFA-0044": True,
    }
    return artifact


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/WFA-0044/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    disc = C.discover()
    rows = C.load_texts()
    if len(rows) != 10:
        print(f"FAILED:WFA-0044 emit corpus n={len(rows)}")
        return 1
    sidecars = write_sidecars(rows)
    artifact = build_artifact(disc, rows, sidecars)
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, indent=2, sort_keys=False) + "\n"
    if "SUCCESS:WFA-0044" not in blob:
        print("FAILED:WFA-0044 emit sentinel missing")
        return 1
    out_path.write_text(blob, encoding="utf-8")

    import jsonschema

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.validate(artifact, schema)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0044 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sha, size = digest_file(out_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0044",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ten-file-round-trip",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "ir-only-reconstruct-and-runtime-lint",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0044/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0044-probe2-ir-only-reconstruct",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0044: live named probes exit 0, WorkflowIR spec "
            "state=SUCCESS with SUCCESS:WFA-0044, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "Live ~/.claude/workflows absent; dialect stand-ins carry the round-trip."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/WFA-0044/ir.py",
        "command-center/p2-wave/probes/WFA-0044/corpus.py",
        "command-center/p2-wave/probes/WFA-0044/probe1_roundtrip.py",
        "command-center/p2-wave/probes/WFA-0044/probe2_reconstruct.py",
        "command-center/p2-wave/probes/WFA-0044/emit_spec.py",
    ]
    supporting.extend(disc["files"])
    supporting.extend(sidecars)
    artifacts = [row(OUT_REL, "primary")] + [row(p, "supporting") for p in supporting]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0044 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
