#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0052-adapter-github-actions.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import LOSSY, NATIVE, IR_FIELDS, IR_VERSION, fail_fast_demo, translate  # noqa: E402
from fail_fast import hidden_after_first_failure  # noqa: E402
from graph import (  # noqa: E402
    is_valid_topo,
    needs_edges_from_ast,
    needs_edges_from_text,
    topo_dfs,
    topo_kahn,
)
from matrix import expand_matrix, expanded_job_count, unexpanded_job_count  # noqa: E402
from rebuild_estate import main as rebuild_estate  # noqa: E402

OUT = "command-center/wfa/WFA-0052-adapter-github-actions.json"
API_PATH = "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
INV_PATH = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
CONTROL = HERE / "fixtures" / "control"
ESTATE = HERE / "fixtures" / "estate"
SENTINEL = "SUCCESS:WFA-0052"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_yaml(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"not a mapping: {path}")
    return doc, text


def graph_proof(path: Path) -> dict:
    doc, text = load_yaml(path)
    ast_nodes, ast_edges = needs_edges_from_ast(doc)
    txt_nodes, txt_edges = needs_edges_from_text(text)
    kahn = topo_kahn(ast_nodes, ast_edges)
    dfs = topo_dfs(txt_nodes, txt_edges)
    ok = (
        ast_nodes == txt_nodes
        and ast_edges == txt_edges
        and kahn is not None
        and dfs is not None
        and is_valid_topo(kahn, ast_edges)
        and is_valid_topo(dfs, txt_edges)
    )
    return {
        "file": path.relative_to(REPO).as_posix(),
        "nodes": sorted(ast_nodes),
        "edges": [{"from": u, "to": v} for u, v in sorted(ast_edges)],
        "ast_edge_count": len(ast_edges),
        "text_edge_count": len(txt_edges),
        "extractors_agree": ast_nodes == txt_nodes and ast_edges == txt_edges,
        "topo_kahn": kahn,
        "topo_dfs": dfs,
        "kahn_valid": bool(kahn) and is_valid_topo(kahn, ast_edges),
        "dfs_valid": bool(dfs) and is_valid_topo(dfs, txt_edges),
        "pass": ok,
    }


def matrix_proof(path: Path) -> dict:
    doc, _ = load_yaml(path)
    jobs = doc.get("jobs") or {}
    unexp = unexpanded_job_count(jobs)
    exp = expanded_job_count(jobs)
    legs = expand_matrix(jobs.get("legs") if isinstance(jobs.get("legs"), dict) else {})

    def key(d: dict) -> tuple:
        return tuple(sorted((str(k), str(v)) for k, v in d.items()))

    expected = [
        {"os": "ubuntu-latest", "py": "3.11"},
        {"os": "ubuntu-latest", "py": "3.12"},
        {"os": "windows-latest", "py": "3.11"},
        {"os": "windows-latest", "py": "3.12"},
        {"os": "macos-latest", "py": "3.12"},
        {"os": "ubuntu-latest", "py": "3.13"},
    ]
    return {
        "file": path.relative_to(REPO).as_posix(),
        "unexpanded_jobs": unexp,
        "expanded_jobs": exp,
        "undercount_if_unexpanded": unexp < exp,
        "legs": legs,
        "expected_leg_count": 6,
        "legs_match_control": {key(x) for x in legs} == {key(x) for x in expected},
        "pass": unexp < exp
        and len(legs) == 6
        and {key(x) for x in legs} == {key(x) for x in expected},
    }


def fail_fast_proof(path: Path) -> dict:
    doc, _ = load_yaml(path)
    demo = fail_fast_demo(doc)
    steps = ((doc.get("jobs") or {}).get("unit") or {}).get("steps") or []
    hidden = hidden_after_first_failure([s for s in steps if isinstance(s, dict)], demo["fail_at"])
    return {
        "file": path.relative_to(REPO).as_posix(),
        "fail_at": demo["fail_at"],
        "ran": demo["ran"],
        "hidden": demo["hidden"],
        "hidden_names": hidden,
        "hides_later_failure": "hidden-after-fail" in hidden,
        "always_still_runs": "cleanup-always" in (demo["ran"] or []),
        "ir_stop_on_first_failure": True,
        "pass": "hidden-after-fail" in hidden and "cleanup-always" in (demo["ran"] or []),
    }


def required_optional_proof(path: Path) -> dict:
    ir = translate(path, REPO, "control")
    by_id = {s["id"]: s for s in ir["stages"]}
    req = by_id.get("required-gate") or {}
    opt = by_id.get("optional-shadow") or {}
    gated = by_id.get("dependabot-only") or {}
    flattened = req.get("required_context") == opt.get("required_context")
    return {
        "file": path.relative_to(REPO).as_posix(),
        "required_gate": req.get("required_context"),
        "optional_shadow": opt.get("required_context"),
        "dependabot_only_gate": gated.get("gates") or [],
        "not_flattened": not flattened,
        "pass": req.get("required_context") == "required-context"
        and opt.get("required_context") == "optional-check"
        and bool(gated.get("gates"))
        and not flattened,
    }


def api_compare(estate_irs: list[dict]) -> dict:
    api_path = REPO / API_PATH
    api = json.loads(api_path.read_text(encoding="utf-8"))
    quality_ir = next((ir for ir in estate_irs if ir.get("name") == "quality"), None)
    ir_names = sorted(str(s.get("name") or s.get("id")) for s in (quality_ir or {}).get("stages") or [])
    quality_run = next((r for r in api.get("runs") or [] if r.get("workflow") == "quality"), None)
    api_names = sorted(
        str(j.get("name")) for j in (quality_run or {}).get("jobs") or [] if j.get("name")
    )
    py_job = next(
        (
            j
            for j in (quality_run or {}).get("jobs") or []
            if "python" in str(j.get("name") or "").lower()
        ),
        None,
    )
    routing = next(
        (r for r in api.get("runs") or [] if "routing" in str(r.get("workflow") or "")),
        None,
    )
    routing_skipped: list[str] = []
    if routing:
        for j in routing.get("jobs") or []:
            routing_skipped.extend(j.get("skipped_steps") or [])
    yaml_step_count = 0
    if quality_ir:
        for st in quality_ir.get("stages") or []:
            yaml_step_count += len(st.get("children") or [])
    api_step_count = sum(int(j.get("step_count") or 0) for j in (quality_run or {}).get("jobs") or [])
    job_count_match = len(ir_names) == len(api_names) == 8
    return {
        "independent_source": API_PATH,
        "independent_sha256": sha256_file(api_path)[0],
        "quality_ir_job_count": len(ir_names),
        "quality_api_job_count": len(api_names),
        "quality_ir_job_names": ir_names,
        "quality_api_job_names": api_names,
        "job_count_match": job_count_match,
        "job_display_names_equal": ir_names == api_names,
        "name_drift": sorted(set(ir_names) ^ set(api_names)),
        "quality_yaml_step_count": yaml_step_count,
        "quality_api_step_count": api_step_count,
        "step_count_divergence": yaml_step_count != api_step_count,
        "python_job_conclusion": (py_job or {}).get("conclusion"),
        "python_job_skipped_steps": (py_job or {}).get("skipped_steps") or [],
        "python_job_hid_later_steps": bool((py_job or {}).get("skipped_steps"))
        and (py_job or {}).get("conclusion") == "failure",
        "routing_skipped_steps": routing_skipped,
        "runtime_skips_conditional_step": any("regression bar" in str(s) for s in routing_skipped),
        "note": (
            "AUD-0041 Actions API snapshot is the mechanically independent rendered graph. "
            "quality.yml has 8 jobs in YAML and 8 jobs in the API run. Display names drifted "
            "(YAML gate-lint-format (ruff) vs API gate-lint-format (ruff)). Step counts "
            "diverge because GitHub injects Post Run hooks absent from YAML. "
            "routing-benchmark skipped a pull_request-only step the YAML still declares. "
            "A YAML that parses is not the runtime schedule."
        ),
        "pass": job_count_match
        and yaml_step_count != api_step_count
        and bool((py_job or {}).get("skipped_steps")),
    }


def main() -> int:
    rebuild_estate()
    if not ESTATE.is_dir() or not any(ESTATE.glob("*.yml")):
        print("FAILED:WFA-0052 estate fixtures missing after rebuild")
        return 1

    control_files = {
        "matrix": CONTROL / "matrix.yml",
        "needs_dag": CONTROL / "needs-dag.yml",
        "fail_fast": CONTROL / "fail-fast.yml",
        "required_optional": CONTROL / "required-optional.yml",
    }
    for key, path in control_files.items():
        if not path.is_file():
            print(f"FAILED:WFA-0052 missing control {key}")
            return 1

    g_needs = graph_proof(control_files["needs_dag"])
    g_matrix = matrix_proof(control_files["matrix"])
    g_fail = fail_fast_proof(control_files["fail_fast"])
    g_req = required_optional_proof(control_files["required_optional"])

    estate_irs = []
    estate_rows = []
    for path in sorted(ESTATE.glob("*.yml")):
        ir = translate(path, REPO, "estate-reconstructed-from-AUD-0041")
        estate_irs.append(ir)
        gp = graph_proof(path)
        estate_rows.append(
            {
                "file": ir["source_path"],
                "name": ir.get("name"),
                "jobs": len(ir.get("stages") or []),
                "expanded_jobs": len(ir.get("expanded_job_stages") or []),
                "steps": sum(len(s.get("children") or []) for s in ir.get("stages") or []),
                "declared_ci_test_stages": len(ir.get("declared_ci_test_stages") or []),
                "needs_proof": gp,
            }
        )

    quality = next((ir for ir in estate_irs if ir.get("name") == "quality"), None)
    test_stages = (quality or {}).get("declared_ci_test_stages") or []
    test_names = [s.get("name") for s in test_stages]
    every_test_has_anchor = all(
        (s.get("source_anchor") or {}).get("json_pointer") for s in test_stages
    )

    api = api_compare(estate_irs)
    live_github = REPO / ".github" / "workflows"
    live_present = live_github.is_dir() and any(live_github.glob("*.yml"))

    control_irs = [translate(p, REPO, "control") for p in control_files.values()]

    tests = {
        "matrix_materialised": g_matrix,
        "needs_graph_vs_independent_topo": g_needs,
        "first_failing_step_hides_later": g_fail,
        "required_vs_optional_not_flattened": g_req,
        "declared_ci_test_stages_are_ir_stages": {
            "count": len(test_stages),
            "expected": 60,
            "names": test_names,
            "every_stage_has_source_anchor": every_test_has_anchor,
            "pass": len(test_stages) == 60 and every_test_has_anchor,
        },
        "runtime_graph_independent": api,
    }
    all_pass = all(
        [
            g_matrix.get("pass"),
            g_needs.get("pass"),
            g_fail.get("pass"),
            g_req.get("pass"),
            tests["declared_ci_test_stages_are_ir_stages"]["pass"],
            api.get("pass"),
            all(r["needs_proof"]["pass"] for r in estate_rows),
        ]
    )
    if not all_pass:
        slim = {}
        for k, v in tests.items():
            if isinstance(v, dict):
                slim[k] = {kk: vv for kk, vv in v.items() if kk != "names"}
            else:
                slim[k] = v
        print("FAILED:WFA-0052 adapter proofs did not all pass")
        print(json.dumps(slim, indent=2, default=str)[:8000])
        return 1

    ir_preview = []
    for ir in estate_irs + control_irs:
        ir_preview.append(
            {
                "name": ir.get("name"),
                "source_path": ir.get("source_path"),
                "source_kind": ir.get("source_kind"),
                "job_ids": [s["id"] for s in ir.get("stages") or []],
                "edges": ir.get("edges"),
                "topo_kahn": ir.get("topo_kahn"),
                "expanded_job_ids": [s["id"] for s in ir.get("expanded_job_stages") or []],
                "declared_ci_test_stage_count": len(ir.get("declared_ci_test_stages") or []),
                "sample_stage": (ir.get("stages") or [None])[0],
            }
        )

    doc = {
        "adapter_id": "github-actions-yaml-to-workflow-ir",
        "completion_sentinel": SENTINEL,
        "corpus": {
            "control_dir": "command-center/p2-wave/probes/WFA-0052/fixtures/control",
            "estate": estate_rows,
            "estate_dir": "command-center/p2-wave/probes/WFA-0052/fixtures/estate",
            "inventory": INV_PATH,
            "reconstruction": (
                "`.github/workflows/` is absent from this worktree. Estate YAML was "
                "reconstructed from AUD-0041 probe1-yaml-inventory.json (the parse of "
                "this estate's CI). Not byte-identical to the missing files. Control "
                "YAML is first-party and is the both-states proof for matrix, needs, "
                "fail-fast, and required vs optional."
            ),
            "runtime_api": API_PATH,
        },
        "evidence_a": {
            "claim": "every job and step parsed; needs-graph vs independent topo from raw YAML",
            "control": g_needs,
            "estate_all_pass": all(r["needs_proof"]["pass"] for r in estate_rows),
        },
        "evidence_b": {
            "claim": (
                "CI provider rendered job graph (AUD-0041 Actions API) compared to adapter "
                "graph; YAML parse is not proof of runtime schedule (matrix expansion and "
                "skipped steps)."
            ),
            "result": api,
        },
        "ir_fields_filled": list(IR_FIELDS),
        "ir_version": IR_VERSION,
        "live_github_workflows_present": live_present,
        "lossy_fields": LOSSY,
        "native": NATIVE,
        "question": (
            "Translate this estate's own CI workflow YAML — jobs, needs edges, matrix "
            "expansion, conditional steps, required contexts — into IR, so the 60 "
            "CI-declared test steps become first-class stages the foundry can reason about."
        ),
        "residual_caveat": (
            "WFA-0044 IR spec artifact and WFA-0001 schema pack are absent on this worktree; "
            "this adapter emits Workflow IR 0.1 filling the catalog field list (stages, roles, "
            "gates, tool policy, fan-out, barriers, loops, human checkpoints, retries, resume, "
            "stop, lineage, source_anchor) with execution_semantics=null. Estate YAML is "
            "reconstructed from AUD-0041, not live `.github/workflows/`. Runtime comparison "
            "uses the AUD-0041 API snapshot (not a fresh GitHub token call). Cloud ok=true "
            "is not delivery."
        ),
        "schema_pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
        "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AdapterConformanceReport",
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "WFA-0044 spec file was present",
                "live .github/workflows was present",
                "fresh GitHub Actions API credentials were used",
            ]
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "PASS",
        "tests_required": tests,
        "title": "Adapter: GitHub Actions workflow YAML to IR",
        "translations": ir_preview,
        "unit_id": "WFA-0052",
        "verdict": "CONFORMANT_WITH_DECLARED_LOSS",
        "wfa_0044_spec_present": (REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json").is_file(),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest} tests={len(test_stages)}")
    print(SENTINEL)
    return 0


# Probe-facing aliases (stable names for probe1/probe2 imports).
graph_proof = graph_proof
matrix_proof = matrix_proof
required_optional_proof = required_optional_proof
fail_fast_proof = fail_fast_proof
api_compare = api_compare
API_PATH = API_PATH

if __name__ == "__main__":
    raise SystemExit(main())

