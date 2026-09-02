"""Best-of-breed fusion with lineage, decomposition and loss control (TST-0317).

A tournament winner fused from several licensed sources must:

* keep the *union* of its sources' capability tokens (``stage:<id>`` and
  ``tool:<name>`` computed from stage declarations) -- any token a source has
  that the fusion lacks is a capability loss and a blocking finding;
* name, on every fused stage, the source it came from and that source's
  license (lineage set-membership);
* decompose back into its sources, which are recorded at fusion time so the
  round trip is real, and those recovered sources must run standalone and be
  re-scorable on the matched case set;
* cover every case any source covers.
"""
from __future__ import annotations

import copy
from typing import Any

from workflow_forge.best_of_breed import fuse_best_of_breed

FUSED_WORKFLOW_ID = "wf.fused.best-of-breed"
CAPABILITY_LOSS = "CAPABILITY_LOSS"
LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"


# --------------------------------------------------------------------------- capabilities
def stage_tokens(stage: dict[str, Any]) -> set[str]:
    tokens = {f"stage:{stage.get('id')}"}
    tokens.update(f"tool:{t}" for t in stage.get("tools") or [])
    return tokens


def capability_tokens(workflow: dict[str, Any]) -> set[str]:
    """Capability set of a workflow, computed from its stage declarations only.

    The top-level ``tools`` list is a summary, not a declaration: a stage that
    is dropped takes its tools with it even if the summary still lists them.
    """
    tokens: set[str] = set()
    for stage in workflow.get("stages") or []:
        if isinstance(stage, dict):
            tokens |= stage_tokens(stage)
    return tokens


def capability_report(sources: list[dict[str, Any]], workflow: dict[str, Any]) -> dict[str, Any]:
    per_source = {str(src["id"]): capability_tokens(src) for src in sources}
    union: set[str] = set()
    for toks in per_source.values():
        union |= toks
    fusion = capability_tokens(workflow)
    difference = sorted(union - fusion)
    lost_by_source = {
        sid: sorted(toks - fusion) for sid, toks in per_source.items() if toks - fusion
    }
    return {
        "per_source": {sid: sorted(toks) for sid, toks in per_source.items()},
        "union": sorted(union),
        "fusion": sorted(fusion),
        "difference": difference,
        "lost_by_source": lost_by_source,
        "empty_difference": not difference,
        "blocking_finding": bool(difference),
        "finding": None if not difference else {
            "code": CAPABILITY_LOSS,
            "message": "fusion lacks capabilities its sources declare: " + ", ".join(difference),
        },
    }


# --------------------------------------------------------------------------- fusion
def _topo_order(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order stages so every consumed artifact is produced first; stable otherwise."""
    produced_by: dict[str, int] = {}
    for idx, st in enumerate(stages):
        for out in st.get("outputs") or []:
            produced_by.setdefault(out, idx)
    remaining = list(range(len(stages)))
    done: set[int] = set()
    ordered: list[dict[str, Any]] = []
    while remaining:
        progressed = False
        for idx in list(remaining):
            deps = {
                produced_by[i]
                for i in stages[idx].get("inputs") or []
                if i in produced_by and produced_by[i] != idx
            }
            if deps <= done:
                ordered.append(stages[idx])
                done.add(idx)
                remaining.remove(idx)
                progressed = True
        if not progressed:  # cycle: keep declared order for what is left
            ordered.extend(stages[i] for i in remaining)
            break
    return ordered


def lineage_integrity(workflow: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    known = {str(s["id"]): s for s in sources}
    fused_stage_ids = [str(st.get("id")) for st in workflow.get("stages") or []]
    named: list[str] = []
    unnamed: list[dict[str, Any]] = []
    licenses: set[str] = set()
    sources_named: list[str] = []
    for st in workflow.get("stages") or []:
        src = st.get("source")
        lic = st.get("license")
        src_ok = isinstance(src, str) and src in known
        lic_ok = isinstance(lic, str) and bool(lic) and known.get(src, {}).get("license") == lic
        if src_ok and lic_ok:
            named.append(str(st.get("id")))
            licenses.add(lic)
            if src not in sources_named:
                sources_named.append(src)
        else:
            unnamed.append({"stage": st.get("id"), "source": src, "license": lic})
    ok = not unnamed and bool(fused_stage_ids)
    return {
        "ok": ok,
        "fused_stage_ids": fused_stage_ids,
        "named_stage_ids": named,
        "unnamed": unnamed,
        "licenses_present": sorted(licenses),
        "sources_named": sources_named,
        "finding": None if ok else {"code": LINEAGE_INCOMPLETE, "unnamed": unnamed},
    }


def fuse_and_record(sources: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Fuse ``sources`` slot-by-slot on ``evidence`` and record lineage.

    The full source definitions are recorded on the result so ``decompose``
    can recover them exactly; every fused stage carries ``source`` and
    ``license``.
    """
    selection = fuse_best_of_breed(sources, evidence)
    if not selection.get("ok"):
        return dict(selection)
    by_id = {str(s["id"]): s for s in sources}
    stages: list[dict[str, Any]] = []
    for row in selection["selection_record"]:
        sid = str(row.get("chosen_source_id") or "")
        src = by_id.get(sid)
        if src is None:
            return {"ok": False, "error": LINEAGE_INCOMPLETE, "slot_id": row.get("slot_id")}
        slot = str(row.get("stage_id") or row.get("slot_id") or "")
        original = next((st for st in src.get("stages") or [] if st.get("id") == slot), None)
        if original is None:
            return {"ok": False, "error": LINEAGE_INCOMPLETE, "slot_id": slot, "source_id": sid}
        fused = copy.deepcopy(original)
        fused["source"] = sid
        fused["license"] = src.get("license")
        fused["evidence_run_id"] = row.get("benchmark_run_id") or row.get("run_id")
        stages.append(fused)
    stages = _topo_order(stages)
    tools: list[str] = []
    for st in stages:
        for t in st.get("tools") or []:
            if t not in tools:
                tools.append(str(t))
    workflow = {
        "id": FUSED_WORKFLOW_ID,
        "stages": stages,
        "tools": tools,
        "stop_rule": {"max_stages": len(stages), "on_error": "halt"},
        "timeout_seconds": sum(int(st.get("timeout_seconds") or 0) for st in stages) or 300,
        "licenses": sorted({str(st.get("license")) for st in stages if st.get("license")}),
    }
    lineage = {
        "sources": copy.deepcopy(sources),
        "source_ids": [str(s["id"]) for s in sources],
        "licenses": {str(s["id"]): s.get("license") for s in sources},
        "stages": [
            {
                "stage_id": st["id"],
                "source_id": st["source"],
                "license": st["license"],
                "evidence_run_id": st.get("evidence_run_id"),
            }
            for st in stages
        ],
    }
    caps = capability_report(sources, workflow)
    integrity = lineage_integrity(workflow, sources)
    return {
        "ok": bool(integrity["ok"]),
        "workflow": workflow,
        "source_ids": lineage["source_ids"],
        "selection_record": selection["selection_record"],
        "composite_score": selection.get("composite_score"),
        "lineage": lineage,
        "lineage_integrity": integrity,
        "capability_report": caps,
    }


# --------------------------------------------------------------------------- decomposition
def decompose(fusion: dict[str, Any]) -> dict[str, Any]:
    """Recover the source workflows a fusion was built from.

    Uses the lineage recorded at fusion time and cross-checks that every fused
    stage is byte-identical (modulo lineage keys) to the recorded source stage.
    """
    lineage = fusion.get("lineage") or {}
    recorded = {str(s["id"]): copy.deepcopy(s) for s in lineage.get("sources") or []}
    workflow = fusion.get("workflow") or {}
    mismatches: list[dict[str, Any]] = []
    for st in workflow.get("stages") or []:
        src = recorded.get(str(st.get("source")))
        if src is None:
            mismatches.append({"stage": st.get("id"), "reason": "source-not-recorded"})
            continue
        original = next((o for o in src.get("stages") or [] if o.get("id") == st.get("id")), None)
        stripped = {k: v for k, v in st.items() if k not in ("source", "license", "evidence_run_id")}
        if original != stripped:
            mismatches.append({"stage": st.get("id"), "reason": "stage-diverged-from-source"})
    components = {sid: src for sid, src in recorded.items()}
    ok = bool(components) and not mismatches
    return {
        "ok": ok,
        "recovered_ids": sorted(components),
        "components": components,
        "mismatches": mismatches,
    }


def drop_stage(workflow: dict[str, Any], stage_id: str) -> dict[str, Any]:
    dropped = copy.deepcopy(workflow)
    dropped["stages"] = [st for st in dropped.get("stages") or [] if st.get("id") != stage_id]
    tools: list[str] = []
    for st in dropped["stages"]:
        for t in st.get("tools") or []:
            if t not in tools:
                tools.append(str(t))
    dropped["tools"] = tools
    if isinstance(dropped.get("stop_rule"), dict):
        dropped["stop_rule"]["max_stages"] = len(dropped["stages"])
    return dropped


# --------------------------------------------------------------------------- execution
def run_standalone(workflow: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Dry-run ``workflow`` on ``case``: every stage's inputs must be available.

    Inputs come from the case and from artifacts produced by earlier stages.
    A workflow is standalone-ok when all of its stages ran and produced their
    outputs; the case's capability requirements are reported separately as
    ``covered`` so a source that lacks a capability still runs standalone.
    """
    available = set((case.get("inputs") or {}).keys())
    produced: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    max_stages = int((workflow.get("stop_rule") or {}).get("max_stages") or 0)
    stages = list(workflow.get("stages") or [])
    if max_stages and len(stages) > max_stages:
        return {
            "ok": False,
            "produced": produced,
            "missing_inputs": missing,
            "stop_rule_violation": f"{len(stages)} stages > max_stages {max_stages}",
            "covered": False,
        }
    for st in stages:
        needs = [i for i in st.get("inputs") or [] if i not in available]
        if needs:
            missing.append({"stage": st.get("id"), "missing": needs})
            if (workflow.get("stop_rule") or {}).get("on_error", "halt") == "halt":
                break
            continue
        outs = list(st.get("outputs") or [])
        available.update(outs)
        produced.append({"stage": st.get("id"), "outputs": outs, "tools": list(st.get("tools") or [])})
    tokens = capability_tokens(workflow)
    required = set(case.get("required") or [])
    ok = not missing and bool(produced) and len(produced) == len(stages)
    return {
        "ok": ok,
        "produced": produced,
        "missing_inputs": missing,
        "covered": ok and required <= tokens,
        "unmet_requirements": sorted(required - tokens),
    }


def score_on_cases(workflow: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    runs = []
    for case in cases:
        run = run_standalone(workflow, case)
        runs.append(
            {
                "case_id": case.get("id"),
                "standalone_ok": bool(run["ok"]),
                "covered": bool(run["covered"]),
                "unmet_requirements": run["unmet_requirements"],
                "stages_run": [p["stage"] for p in run["produced"]],
            }
        )
    covered = [r["case_id"] for r in runs if r["covered"]]
    return {
        "workflow_id": workflow.get("id"),
        "runs": runs,
        "covered": covered,
        "n_cases": len(cases),
        "n_covered": len(covered),
        "score": (len(covered) / len(cases)) if cases else 0.0,
    }


def fusion_covers_source_cases(
    fusion_score: dict[str, Any], source_scores: list[dict[str, Any]]
) -> dict[str, Any]:
    union: set[str] = set()
    for sc in source_scores:
        union.update(sc.get("covered") or [])
    fusion_cases = set(fusion_score.get("covered") or [])
    missing = sorted(union - fusion_cases)
    return {
        "ok": not missing,
        "fusion_cases": sorted(fusion_cases),
        "union_source_cases": sorted(union),
        "missing_from_fusion": missing,
        "per_source": {
            str(sc.get("workflow_id")): sorted(sc.get("covered") or []) for sc in source_scores
        },
    }
