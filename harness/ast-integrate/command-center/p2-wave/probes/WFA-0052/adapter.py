"""GitHub Actions workflow YAML → Workflow IR (catalog WFA-0044 field set).

IR is a typed translation, not a second execution runtime. Every node carries
a source_anchor. Constructs this adapter cannot carry are listed as lossy,
not silently dropped.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fail_fast import apply_first_failure
from graph import needs_edges_from_ast, topo_kahn
from matrix import expand_matrix, leg_suffix, normalize_needs

IR_VERSION = "workflow-ir-0.1-wfa-0052"
NATIVE = "github-actions"

# Catalog WFA-0044 required constructs. Adapter fills these; execution is
# explicitly out of scope (no runtime entrypoint).
IR_FIELDS = (
    "stages",
    "roles",
    "gates",
    "tool_policy",
    "fan_out",
    "barriers",
    "loops",
    "human_checkpoints",
    "retries",
    "resume",
    "stop",
    "lineage",
    "source_anchor",
)

LOSSY = [
    {
        "native": "fromJSON(matrix) / runtime-computed include",
        "reason": "leg set is only known after expression evaluation",
        "disposition": "NON-TRANSFERABLE without a bound github context",
    },
    {
        "native": "branch-protection requiredChecks (repo settings, not YAML)",
        "reason": "required vs optional at merge time lives outside the workflow file",
        "disposition": "YAML continue-on-error / job if preserved; protection API is a second source",
    },
    {
        "native": "injected Post Run / Pre Run hook steps",
        "reason": "Actions runtime injects composite action epilogues not present in YAML",
        "disposition": "recorded as runtime-graph divergence, not invented in IR",
    },
    {
        "native": "secrets / ${{ github.* }} expression values",
        "reason": "IR stores the expression text, never resolved credentials",
        "disposition": "expression kept as gate.expr",
    },
    {
        "native": "reusable workflow outputs and workflow_call secrets:inherit",
        "reason": "callee graph is another YAML document",
        "disposition": "caller jobs.uses recorded; callee not inlined unless the file is in corpus",
    },
]


def load_yaml(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return doc, text


def _anchor(rel: str, pointer: str, **extra: Any) -> dict[str, Any]:
    row = {"file": rel, "json_pointer": pointer, "kind": NATIVE}
    row.update(extra)
    return row


def _tool_policy(step: dict) -> dict[str, Any]:
    if step.get("uses"):
        pol: dict[str, Any] = {"kind": "uses", "uses": str(step.get("uses"))}
        if isinstance(step.get("with"), dict):
            pol["with_keys"] = sorted(str(k) for k in step["with"])
        return pol
    if "run" in step:
        return {
            "kind": "run",
            "shell": step.get("shell") or "default",
            "run_present": bool(str(step.get("run") or "").strip()),
            "run_sha16": _snip_hash(str(step.get("run") or "")),
        }
    return {"kind": "empty"}


def _snip_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _required_context(job: dict, step: dict | None = None) -> str:
    """Preserve required vs optional; do not flatten to a single 'check' bit."""
    if step is not None and step.get("continue-on-error") is True:
        return "optional-check"
    if job.get("continue-on-error") is True:
        return "optional-check"
    return "required-context"


def _stop_block(job: dict) -> dict[str, Any]:
    return {
        "on_first_failure": True,
        "skips_later_steps": True,
        "exceptions": ["if: always()", "if: failure()"],
        "continue_on_error_does_not_stop": True,
        "job_continue_on_error": bool(job.get("continue-on-error")),
    }


def is_declared_ci_test_step(job_id: str, step: dict, index: int) -> bool:
    """The 60 CI-declared test steps live on quality.yml job test-python.

    Checkout / setup-python (including the mid-job 3.12 setup) are not tests.
    """
    if job_id != "test-python":
        return False
    name = str(step.get("name") or "")
    if not name:
        return False
    lowered = name.lower()
    if lowered.startswith("setup python"):
        return False
    if "actions/checkout" in str(step.get("uses") or ""):
        return False
    return True


def translate(path: Path, repo: Path, source_kind: str) -> dict[str, Any]:
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    doc, text = load_yaml(path)
    jobs = doc.get("jobs") if isinstance(doc.get("jobs"), dict) else {}
    nodes, edges = needs_edges_from_ast(doc)
    kahn = topo_kahn(nodes, edges)
    stages: list[dict[str, Any]] = []
    expanded_stages: list[dict[str, Any]] = []
    test_stages: list[dict[str, Any]] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        legs = expand_matrix(job)
        needs = normalize_needs(job.get("needs"))
        stop = _stop_block(job)
        children: list[dict[str, Any]] = []
        steps = job.get("steps") if isinstance(job.get("steps"), list) else []
        for si, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            child = {
                "id": f"{job_id}::step{si}",
                "kind": "stage",
                "role": "ci-step",
                "name": step.get("name") or f"{job_id}-step-{si}",
                "source_anchor": _anchor(rel, f"/jobs/{job_id}/steps/{si}", job_id=job_id, step_index=si),
                "gates": ([{"kind": "if", "expr": str(step.get("if"))}] if step.get("if") else []),
                "tool_policy": _tool_policy(step),
                "fan_out": None,
                "barrier": None,
                "loop": None,
                "human_checkpoint": None,
                "retry": None,
                "resume": None,
                "stop": stop,
                "lineage": {"native": NATIVE, "workflow": doc.get("name"), "job_id": job_id, "step_index": si},
                "required_context": _required_context(job, step),
                "continue_on_error": bool(step.get("continue-on-error")),
            }
            children.append(child)
            if is_declared_ci_test_step(str(job_id), step, si):
                test_stages.append(child)
        job_stage = {
            "id": str(job_id),
            "kind": "stage",
            "role": "ci-job",
            "name": job.get("name") or job_id,
            "source_anchor": _anchor(rel, f"/jobs/{job_id}", job_id=job_id),
            "gates": ([{"kind": "if", "expr": str(job.get("if"))}] if job.get("if") else []),
            "tool_policy": {"kind": "github-hosted-runner", "runs_on": job.get("runs-on")},
            "fan_out": None
            if len(legs) <= 1 and not (isinstance(job.get("strategy"), dict) and job["strategy"].get("matrix"))
            else {
                "kind": "matrix",
                "leg_count": len(legs),
                "unexpanded_would_count": 1,
                "legs": [leg_suffix(leg) for leg in legs],
            },
            "barrier": ({"kind": "matrix-join", "after": str(job_id)} if len(legs) > 1 else None),
            "loop": None,
            "human_checkpoint": None,
            "retry": None,
            "resume": None,
            "stop": stop,
            "lineage": {"native": NATIVE, "workflow": doc.get("name"), "job_id": job_id, "needs": needs},
            "required_context": _required_context(job, None),
            "needs": needs,
            "children": children,
        }
        stages.append(job_stage)
        for li, leg in enumerate(legs):
            expanded_stages.append(
                {
                    "id": str(job_id) if len(legs) == 1 else f"{job_id}__{leg_suffix(leg) or li}",
                    "job_id": str(job_id),
                    "name": job.get("name") or job_id,
                    "matrix": leg,
                    "required_context": job_stage["required_context"],
                    "source_anchor": _anchor(
                        rel, f"/jobs/{job_id}/strategy/matrix", job_id=job_id, leg_index=li
                    ),
                }
            )
    ir = {
        "ir_version": IR_VERSION,
        "kind": "WorkflowIR",
        "native": NATIVE,
        "source_kind": source_kind,
        "source_path": rel,
        "name": doc.get("name"),
        "triggers": doc.get("on"),
        "source_anchor": _anchor(rel, "/"),
        "stages": stages,
        "expanded_job_stages": expanded_stages,
        "edges": [{"from": u, "to": v, "kind": "needs"} for u, v in sorted(edges)],
        "needs_nodes": sorted(nodes),
        "topo_kahn": kahn,
        "roles": sorted({s["role"] for s in stages} | {"ci-step"}),
        "declared_ci_test_stages": test_stages,
        "lossy_fields": LOSSY,
        "execution_semantics": None,
        "note": "IR has no execution runtime; translation only.",
    }
    return ir


def fail_fast_demo(doc: dict) -> dict[str, Any]:
    jobs = doc.get("jobs") or {}
    job = jobs.get("unit") or next(iter(jobs.values()), {})
    steps = job.get("steps") if isinstance(job, dict) else []
    # Planted failure is the first step whose run is `exit 1` or name planted-failure
    fail_at = 0
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            continue
        if st.get("name") == "planted-failure" or str(st.get("run") or "").strip() == "exit 1":
            fail_at = i
            break
    sim = apply_first_failure([s for s in steps if isinstance(s, dict)], fail_at)
    return {
        "fail_at": fail_at,
        "hidden": [s.get("name") for s in sim if not s.get("would_run")],
        "ran": [s.get("name") for s in sim if s.get("would_run")],
        "stop_on_first_failure": True,
    }
