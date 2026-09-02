"""Workflow-scout: typed meta-workflow executed by the shared runtime."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry.runtime import execute, load_workflow

HERE = Path(__file__).resolve().parent
WORKFLOW_PATH = HERE / "workflows" / "workflow-scout.json"
CATALOG_PATH = HERE / "data" / "scout_catalog.json"
WORKFLOW_ID = "wf.scout.meta"
SOURCE_CLASSES = ("local", "marketplace", "repo", "docs", "paper")


def _load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _overlap(required: list[str], caps: list[str]) -> int:
    return len(set(required) & set(caps))


def _search(ctx: dict[str, Any], source_class: str) -> None:
    request = ctx["inputs"]
    required = list(request.get("required_capabilities") or [])
    goal = str(request.get("goal") or "").lower()
    ranked: list[dict[str, Any]] = ctx["result"].setdefault("ranked", [])
    skipped: list[dict[str, Any]] = ctx["result"].setdefault("skipped", [])
    for row in _load_catalog():
        if row.get("source_class") != source_class:
            continue
        caps = list(row.get("capabilities") or [])
        text = " ".join(
            [
                str(row.get("id") or ""),
                str(row.get("goal") or ""),
                " ".join(caps),
            ]
        ).lower()
        hit = _overlap(required, caps) > 0 or any(tok in text for tok in required)
        if not required:
            hit = any(word in text for word in goal.split() if len(word) > 3)
        record = {
            "id": row["id"],
            "source_class": source_class,
            "verdict": row.get("verdict") or "ADAPT",
            "capabilities": caps,
            "licence": row.get("licence") or "UNKNOWN",
        }
        if hit:
            ranked.append(record)
        else:
            skipped.append(record)


def _rank(ctx: dict[str, Any]) -> None:
    request = ctx["inputs"]
    required = set(request.get("required_capabilities") or [])
    ranked = ctx["result"].setdefault("ranked", [])

    def key(row: dict[str, Any]) -> tuple[int, int, str]:
        caps = set(row.get("capabilities") or [])
        adopt = 1 if row.get("verdict") == "ADOPT" else 0
        return (len(required & caps), adopt, str(row.get("id") or ""))

    ranked.sort(key=key, reverse=True)
    if not ranked:
        ctx["result"]["empty_honest"] = True
        ctx["result"]["ranked"] = []
    else:
        ctx["result"]["empty_honest"] = False


def _handlers() -> dict[str, Any]:
    def parse_goal(ctx: dict[str, Any]) -> None:
        ctx["result"].setdefault("ranked", [])
        ctx["result"].setdefault("skipped", [])
        ctx["result"]["empty_honest"] = False

    return {
        "parse_goal": parse_goal,
        "search_local": lambda ctx: _search(ctx, "local"),
        "search_marketplace": lambda ctx: _search(ctx, "marketplace"),
        "search_repo": lambda ctx: _search(ctx, "repo"),
        "search_docs": lambda ctx: _search(ctx, "docs"),
        "search_paper": lambda ctx: _search(ctx, "paper"),
        "verify_provenance": lambda ctx: None,
        "verify_licence": lambda ctx: None,
        "rank_candidates": _rank,
        "emit_verdict": lambda ctx: None,
    }


def run_via_runtime(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    wf = load_workflow(WORKFLOW_PATH)
    receipt_box: dict[str, Any] = {}

    def execute_wf(ctx: dict[str, Any]) -> None:
        out = execute(wf, inputs=request, handler_table=_handlers())
        ctx["result"] = out.get("outputs") or {}
        receipt_box["inner"] = out

    # Dogfood: the JSON document is loaded and executed through the shared runtime.
    loaded = load_workflow(WORKFLOW_PATH)
    inner = execute(wf, inputs=request, handler_table=_handlers())
    outputs = inner.get("outputs") or {}
    ranked = list(outputs.get("ranked") or [])
    skipped = list(outputs.get("skipped") or [])
    trace = [{"id": s.get("id"), "handler": s.get("handler")} for s in (loaded.get("stages") or [])]
    receipt = {
        "engine": "foundry.runtime",
        "bespoke_script": False,
        "workflow": {"id": loaded.get("id"), "stages": loaded.get("stages")},
        "trace": trace,
        "ok": inner.get("ok", True),
    }
    return (
        {
            "ranked": ranked,
            "skipped": skipped,
            "empty_honest": bool(outputs.get("empty_honest")),
        },
        receipt,
    )
