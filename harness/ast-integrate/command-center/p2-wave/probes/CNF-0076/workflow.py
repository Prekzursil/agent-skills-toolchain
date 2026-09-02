"""Executable fusion, decomposition, and stage-lineage checks for CNF-0076.

Decompose reads fusion STAGES and their lineage citations, not sources_declared
metadata. A fusion that lists a source in metadata but carries none of its
stages cannot satisfy the round-trip; that is the metadata-only-claim control.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "fixtures" / "sources"
CASE_PATH = HERE / "fixtures" / "cases" / "case-alpha.json"
ORIGINAL_OUT_DIR = HERE / "fixtures" / "original-outputs"
FUSION_PATH = HERE / "fixtures" / "fusion" / "wf.fused-index.json"

OMITTED_SOURCE_ID = "wf.license-stamp"
REMOVED_STAGE_ID = "wf.term-index::count"


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources() -> list[dict]:
    paths = sorted(SOURCE_DIR.glob("wf.*.json"))
    if len(paths) < 3:
        raise FileNotFoundError(f"need >=3 source workflows in {SOURCE_DIR}")
    sources = [load_json(p) for p in paths]
    ids = [s["id"] for s in sources]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate source ids: {ids}")
    return sources


def load_case() -> dict:
    return load_json(CASE_PATH)


def stage_fingerprint(stage: dict) -> tuple:
    return (
        str(stage.get("id") or ""),
        str(stage.get("op") or ""),
        json.dumps(stage.get("params") or {}, sort_keys=True, separators=(",", ":")),
    )


def workflow_fingerprint(workflow: dict) -> str:
    payload = [
        {"id": s.get("id"), "op": s.get("op"), "params": s.get("params") or {}}
        for s in workflow.get("stages") or []
    ]
    return sha256_text(canonical_dumps(payload))


def execute(workflow: dict, case: dict) -> dict:
    """Run stages in order. Unknown ops fail closed."""
    doc = json.loads(json.dumps(case))
    log: list[dict] = []
    for stage in workflow.get("stages") or []:
        op = stage.get("op")
        params = stage.get("params") or {}
        sid = str(stage.get("id") or "")
        if op == "lowercase":
            field = params.get("field", "text")
            doc[field] = str(doc[field]).lower()
        elif op == "tokenize":
            field = params.get("field", "text")
            out = params.get("out", "tokens")
            doc[out] = str(doc[field]).split()
        elif op == "unique_sort":
            field = params.get("field", "tokens")
            out = params.get("out", "terms")
            doc[out] = sorted(set(doc[field]))
        elif op == "count":
            field = params.get("field", "tokens")
            out = params.get("out", "counts")
            counts: dict[str, int] = {}
            for tok in doc[field]:
                counts[tok] = counts.get(tok, 0) + 1
            doc[out] = {k: counts[k] for k in sorted(counts)}
        elif op == "stamp":
            key = params.get("key", "license")
            doc[key] = params.get("value")
        else:
            raise ValueError(f"unknown op {op!r} in stage {sid}")
        log.append({"stage_id": sid, "op": op})
    text = canonical_dumps(doc)
    return {
        "doc": doc,
        "log": log,
        "canonical": text,
        "sha256": sha256_text(text),
        "executed": True,
        "workflow_id": workflow.get("id"),
        "stage_count": len(log),
    }


def fuse(
    sources: list[dict],
    *,
    omit_source_ids: list[str] | tuple[str, ...] = (),
    fusion_id: str = "wf.fused-index",
) -> dict:
    omit = set(omit_source_ids)
    stages: list[dict] = []
    declared: list[str] = []
    for src in sources:
        sid = src["id"]
        if sid in omit:
            continue
        declared.append(sid)
        for st in src.get("stages") or []:
            stages.append(
                {
                    "id": f"{sid}::{st['id']}",
                    "op": st["op"],
                    "params": copy.deepcopy(st.get("params") or {}),
                    "lineage": {
                        "source_id": sid,
                        "stage_id": st["id"],
                        "license": src.get("license"),
                        "credit": src.get("credit"),
                    },
                }
            )
    return {
        "id": fusion_id,
        "kind": "fused_workflow",
        "strategy": "union-with-lineage",
        "sources_declared": declared,
        "stages": stages,
        "fingerprint": "",
    }


def decompose(fusion: dict) -> dict:
    """Recover source mechanism sets from stage lineage. Ignores sources_declared."""
    recovered_map: dict[str, dict] = {}
    orphans: list[dict] = []
    for stage in fusion.get("stages") or []:
        lin = stage.get("lineage") if isinstance(stage.get("lineage"), dict) else {}
        source_id = lin.get("source_id")
        if not source_id:
            orphans.append({"fusion_stage_id": stage.get("id"), "reason": "no-lineage"})
            continue
        rec = recovered_map.setdefault(
            str(source_id),
            {
                "id": str(source_id),
                "kind": "recovered_source",
                "license": lin.get("license"),
                "credit": lin.get("credit"),
                "stages": [],
            },
        )
        rec["stages"].append(
            {
                "id": str(lin.get("stage_id") or stage.get("id")),
                "op": stage.get("op"),
                "params": copy.deepcopy(stage.get("params") or {}),
            }
        )
        if rec.get("license") is None:
            rec["license"] = lin.get("license")
        if rec.get("credit") is None:
            rec["credit"] = lin.get("credit")
    recovered = list(recovered_map.values())
    return {
        "recovered": recovered,
        "orphans": orphans,
        "recovered_ids": [r["id"] for r in recovered],
        "stage_count": len(fusion.get("stages") or []),
    }


def capability_diff(fusion: dict, original_sources: list[dict]) -> dict:
    """Set-difference of original source mechanisms vs recovered-from-lineage."""
    decomp = decompose(fusion)
    recovered_by_id = {r["id"]: r for r in decomp["recovered"]}
    lost: list[dict] = []
    matched: list[dict] = []
    for src in original_sources:
        sid = src["id"]
        orig_fp = {stage_fingerprint(s) for s in src.get("stages") or []}
        rec = recovered_by_id.get(sid)
        if rec is None:
            lost.append(
                {
                    "source_id": sid,
                    "reason": "absent-from-lineage-graph",
                    "stages": [s["id"] for s in src.get("stages") or []],
                    "license": src.get("license"),
                    "credit": src.get("credit"),
                }
            )
            continue
        rec_fp = {stage_fingerprint(s) for s in rec.get("stages") or []}
        missing = sorted(orig_fp - rec_fp)
        extra = sorted(rec_fp - orig_fp)
        row = {
            "source_id": sid,
            "fingerprint_match": orig_fp == rec_fp,
            "missing_stages": [m[0] for m in missing],
            "extra_stages": [e[0] for e in extra],
            "license_survived": rec.get("license") == src.get("license"),
            "credit_survived": rec.get("credit") == src.get("credit"),
        }
        if missing:
            lost.append(
                {
                    "source_id": sid,
                    "reason": "stage-missing-after-decompose",
                    "stages": [m[0] for m in missing],
                    "license": src.get("license"),
                    "credit": src.get("credit"),
                }
            )
        else:
            matched.append(row)
    return {
        "lost_capabilities": lost,
        "matched": matched,
        "orphans": decomp["orphans"],
        "recovered": decomp["recovered"],
        "recovered_ids": decomp["recovered_ids"],
    }


def recover_and_execute(
    fusion: dict,
    original_sources: list[dict],
    case: dict,
    original_runs: dict[str, dict] | None = None,
) -> dict:
    if original_runs is None:
        original_runs = {s["id"]: execute(s, case) for s in original_sources}
    diff = capability_diff(fusion, original_sources)
    rows: list[dict] = []
    for rec in diff["recovered"]:
        run = execute(rec, case)
        orig = original_runs.get(rec["id"]) or {}
        match = bool(orig) and orig.get("sha256") == run["sha256"]
        orig_doc = orig.get("doc") if isinstance(orig.get("doc"), dict) else {}
        rec_doc = run["doc"]
        differing = sorted(set(orig_doc) | set(rec_doc))
        differing_fields = [
            k
            for k in differing
            if json.dumps(orig_doc.get(k), sort_keys=True)
            != json.dumps(rec_doc.get(k), sort_keys=True)
        ]
        rows.append(
            {
                "source_id": rec["id"],
                "executed": True,
                "output_match": match,
                "definition": rec,
                "execution_output": run["doc"],
                "execution_log": run["log"],
                "diff_against_original": {
                    "match": match,
                    "original_sha256": orig.get("sha256"),
                    "recovered_sha256": run["sha256"],
                    "differing_fields": differing_fields,
                },
                "lineage_license": rec.get("license"),
                "lineage_credit": rec.get("credit"),
                "fingerprint": workflow_fingerprint(rec),
                "original_fingerprint": workflow_fingerprint(
                    next(s for s in original_sources if s["id"] == rec["id"])
                ),
            }
        )
    executed = [r for r in rows if r["executed"]]
    return {
        "recovered": rows,
        "lost_capabilities": diff["lost_capabilities"],
        "orphans": diff["orphans"],
        "every_recovered_source_executed": bool(rows) and len(executed) == len(rows),
        "every_recovered_output_matches": bool(rows) and all(r["output_match"] for r in rows),
        "original_runs": {
            sid: {"sha256": run["sha256"], "doc": run["doc"], "log": run["log"]}
            for sid, run in original_runs.items()
        },
    }


def remove_one_stage(fusion: dict, stage_id: str) -> dict:
    mutilated = copy.deepcopy(fusion)
    before = len(mutilated.get("stages") or [])
    mutilated["stages"] = [s for s in mutilated["stages"] if s.get("id") != stage_id]
    after = len(mutilated["stages"])
    if after != before - 1:
        raise ValueError(f"remove-one-stage did not drop {stage_id}: {before}->{after}")
    mutilated["id"] = f"{fusion.get('id')}.minus-{stage_id}"
    return mutilated


def issue_set(lost: list[dict]) -> set[tuple]:
    return {
        (str(item.get("source_id")), str(item.get("reason")), tuple(item.get("stages") or []))
        for item in lost
    }


def remove_one_stage_control(
    fusion: dict,
    original_sources: list[dict],
    stage_id: str = REMOVED_STAGE_ID,
) -> dict:
    intact = capability_diff(fusion, original_sources)
    mutilated_fusion = remove_one_stage(fusion, stage_id)
    mutilated = capability_diff(mutilated_fusion, original_sources)
    new_issues = issue_set(mutilated["lost_capabilities"]) - issue_set(
        intact["lost_capabilities"]
    )
    intact_stage_n = len(fusion.get("stages") or [])
    mut_stage_n = len(mutilated_fusion.get("stages") or [])
    recovered_stage_n_intact = sum(len(r["stages"]) for r in intact["recovered"])
    recovered_stage_n_mut = sum(len(r["stages"]) for r in mutilated["recovered"])
    intact_has_removal_issue = any(
        item.get("reason") == "stage-missing-after-decompose"
        for item in intact["lost_capabilities"]
    )
    intact_does_not_fire = not intact_has_removal_issue
    mutilated_fires = bool(new_issues)
    detected = (
        intact_does_not_fire
        and mutilated_fires
        and recovered_stage_n_mut == recovered_stage_n_intact - 1
        and mut_stage_n == intact_stage_n - 1
    )
    return {
        "removed_stage_id": stage_id,
        "detected": detected,
        "intact_does_not_fire": intact_does_not_fire,
        "intact_new_issues": 0,
        "mutilated_fires": bool(new_issues),
        "new_issues": [
            {"source_id": a, "reason": b, "stages": list(c)} for a, b, c in sorted(new_issues)
        ],
        "intact_lost_count": len(intact["lost_capabilities"]),
        "mutilated_lost_count": len(mutilated["lost_capabilities"]),
        "intact_fusion_stage_count": intact_stage_n,
        "mutilated_fusion_stage_count": mut_stage_n,
        "intact_recovered_stage_count": recovered_stage_n_intact,
        "mutilated_recovered_stage_count": recovered_stage_n_mut,
        "intact_lost": intact["lost_capabilities"],
        "mutilated_lost": mutilated["lost_capabilities"],
    }


def metadata_only_mutant(fusion: dict, extra_source_id: str = OMITTED_SOURCE_ID) -> dict:
    mutant = copy.deepcopy(fusion)
    declared = list(mutant.get("sources_declared") or [])
    if extra_source_id not in declared:
        declared.append(extra_source_id)
    mutant["sources_declared"] = declared
    mutant["id"] = f"{fusion.get('id')}.metadata-only"
    return mutant


def freeze_original_outputs(original_runs: dict[str, dict]) -> None:
    ORIGINAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sid, run in original_runs.items():
        path = ORIGINAL_OUT_DIR / f"{sid}.json"
        path.write_text(canonical_dumps(run["doc"]), encoding="utf-8")


def persist_fusion(fusion: dict) -> None:
    FUSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = copy.deepcopy(fusion)
    body["fingerprint"] = workflow_fingerprint(fusion)
    FUSION_PATH.write_text(json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run_analysis() -> dict:
    sources = load_sources()
    case = load_case()
    original_runs = {s["id"]: execute(s, case) for s in sources}
    freeze_original_outputs(original_runs)

    complete = fuse(sources, omit_source_ids=())
    lossy = fuse(sources, omit_source_ids=(OMITTED_SOURCE_ID,))
    persist_fusion(lossy)

    complete_diff = capability_diff(complete, sources)
    lossy_exec = recover_and_execute(lossy, sources, case, original_runs)
    control = remove_one_stage_control(lossy, sources, REMOVED_STAGE_ID)

    meta = metadata_only_mutant(lossy, OMITTED_SOURCE_ID)
    meta_diff = capability_diff(meta, sources)
    meta_still_lost = any(
        item.get("source_id") == OMITTED_SOURCE_ID for item in meta_diff["lost_capabilities"]
    )

    lineage_rows = []
    for stage in lossy.get("stages") or []:
        lin = stage.get("lineage") or {}
        lineage_rows.append(
            {
                "fusion_stage_id": stage.get("id"),
                "op": stage.get("op"),
                "source_id": lin.get("source_id"),
                "source_stage_id": lin.get("stage_id"),
                "license": lin.get("license"),
                "credit": lin.get("credit"),
                "lineage_present": bool(lin.get("source_id") and lin.get("stage_id")),
            }
        )

    return {
        "sources": sources,
        "case": case,
        "fusion": lossy,
        "complete_fusion": complete,
        "original_runs": original_runs,
        "complete_lost": complete_diff["lost_capabilities"],
        "lossy_exec": lossy_exec,
        "control": control,
        "metadata_only_still_lost": meta_still_lost,
        "metadata_only_lost": meta_diff["lost_capabilities"],
        "lineage": lineage_rows,
        "every_lineage_present": bool(lineage_rows)
        and all(r["lineage_present"] for r in lineage_rows),
        "lost_capability_both_states": {
            "complete_fusion_lost_count": len(complete_diff["lost_capabilities"]),
            "lossy_fusion_lost_count": len(lossy_exec["lost_capabilities"]),
            "detector_silent_on_complete": len(complete_diff["lost_capabilities"]) == 0,
            "detector_fires_on_omission": any(
                item.get("source_id") == OMITTED_SOURCE_ID
                for item in lossy_exec["lost_capabilities"]
            ),
        },
    }
