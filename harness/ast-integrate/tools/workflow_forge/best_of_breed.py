"""Score-only best-of-breed fusion (IMP-0185 / WFA-0103)."""
from __future__ import annotations

from typing import Any

TIED = "TIED"
REPUTATION_NOT_EVIDENCE = "REPUTATION_NOT_EVIDENCE"
WRITTEN_TIE_RULE_ID = "lexicographic-source-id"


class FusionBuildError(Exception):
    def __init__(self, code: str, message: str = "", **ctx: Any) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.ctx = ctx
        for key, val in ctx.items():
            setattr(self, key, val)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "ok": False,
            "error": self.code,
            "message": self.message,
        }
        payload.update(self.ctx)
        return payload


def _rows_by_slot(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in evidence:
        if not isinstance(row, dict):
            continue
        out.setdefault(str(row.get("slot_id") or ""), []).append(row)
    return out


def fuse_best_of_breed(
    sources: Any,
    evidence: list[dict[str, Any]],
    tie_rule: str = WRITTEN_TIE_RULE_ID,
    prefer_source: str | None = None,
) -> dict[str, Any]:
    if prefer_source:
        return {
            "ok": False,
            "error": REPUTATION_NOT_EVIDENCE,
            "slot_id": None,
        }
    record: list[dict[str, Any]] = []
    for slot, rows in _rows_by_slot(evidence).items():
        ranked = sorted(rows, key=lambda r: (-float(r.get("score") or 0), str(r.get("source_id") or "")))
        if not ranked:
            continue
        top = ranked[0]
        rest = ranked[1:]
        tied = bool(rest) and float(rest[0].get("score") or 0) == float(top.get("score") or 0)
        if tied and tie_rule == "refuse":
            return {"ok": False, "error": TIED, "slot_id": slot}
        if tied:
            chosen = min(ranked, key=lambda r: str(r.get("source_id") or ""))
            losers = [r for r in ranked if r is not chosen]
            record.append(
                {
                    "slot_id": slot,
                    "chosen_source_id": chosen.get("source_id"),
                    "score": chosen.get("score"),
                    "resolution": WRITTEN_TIE_RULE_ID,
                    "losers": [
                        {"source_id": r.get("source_id"), "score": r.get("score")}
                        for r in losers
                    ],
                    "run_id": chosen.get("run_id") or chosen.get("benchmark_run_id"),
                    "benchmark_run_id": chosen.get("benchmark_run_id") or chosen.get("run_id"),
                    "stage_id": chosen.get("stage_id") or slot,
                }
            )
        else:
            record.append(
                {
                    "slot_id": slot,
                    "chosen_source_id": top.get("source_id"),
                    "score": top.get("score"),
                    "resolution": "strict-score",
                    "losers": [
                        {"source_id": r.get("source_id"), "score": r.get("score")}
                        for r in rest
                    ],
                    "run_id": top.get("run_id") or top.get("benchmark_run_id"),
                    "benchmark_run_id": top.get("benchmark_run_id") or top.get("run_id"),
                    "stage_id": top.get("stage_id") or slot,
                }
            )
    workflow = _assemble_workflow(sources, record)
    composite = sum(float(r.get("score") or 0) for r in record)
    return {
        "ok": True,
        "selection_record": record,
        "workflow": workflow,
        "composite_score": composite,
    }


def _assemble_workflow(sources: Any, record: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict) and src.get("id"):
                by_id[str(src["id"])] = src
    stages = []
    for row in record:
        src = by_id.get(str(row.get("chosen_source_id") or "")) or {}
        slot = str(row.get("slot_id") or "")
        src_stages = src.get("stages") if isinstance(src, dict) else []
        match = None
        for st in src_stages or []:
            if isinstance(st, dict) and st.get("id") == slot:
                match = dict(st)
                break
        if match is None:
            match = {"id": slot, "type": "task", "tools": list(src.get("tools") or [])}
        stages.append(match)
    tools: list[str] = []
    for st in stages:
        for t in st.get("tools") or []:
            if t not in tools:
                tools.append(str(t))
    return {
        "id": "wf.fused.best-of-breed",
        "stages": stages,
        "tools": tools,
        "stop_rule": {"max_stages": len(stages), "on_error": "halt"},
        "timeout_seconds": 300,
    }


def build_best_of_breed(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return fuse_best_of_breed(*args, **kwargs)


def independent_winners(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for slot, rows in _rows_by_slot(evidence).items():
        ranked = sorted(rows, key=lambda r: (-float(r.get("score") or 0), str(r.get("source_id") or "")))
        if ranked:
            out[slot] = ranked[0]
    return out


def ablate_second_best(result: dict[str, Any], slot: str) -> dict[str, Any]:
    record = list(result.get("selection_record") or [])
    before = float(result.get("composite_score") or sum(float(r.get("score") or 0) for r in record))
    after_rows = []
    for row in record:
        if row.get("slot_id") != slot:
            after_rows.append(row)
            continue
        losers = row.get("losers") or []
        if not losers:
            after_rows.append(row)
            continue
        second = losers[0]
        after_rows.append(
            {
                **row,
                "chosen_source_id": second.get("source_id"),
                "score": second.get("score"),
            }
        )
    after = sum(float(r.get("score") or 0) for r in after_rows)
    delta = after - before
    return {
        "ok": True,
        "slot_id": slot,
        "composite_before": before,
        "composite_after": after,
        "delta": delta,
        "composite_moved": delta < 0,
    }


def selection_cites_run_ids(selection: Any) -> dict[str, Any]:
    if isinstance(selection, dict):
        rows = selection.get("selection_record") or []
    else:
        rows = list(selection or [])
    missing = []
    cited = 0
    for row in rows:
        if "benchmark_run_id" in row:
            rid = row.get("benchmark_run_id")
        else:
            rid = row.get("run_id")
        if rid:
            cited += 1
        else:
            missing.append(str(row.get("slot_id") or ""))
    total = len(rows)
    return {
        "ok": cited == total and total > 0 and not missing,
        "cited": cited,
        "total": total,
        "missing_slots": missing,
    }
