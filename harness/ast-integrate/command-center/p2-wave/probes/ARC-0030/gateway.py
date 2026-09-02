"""A4 gateway: index-all, select-from-index-text, activate-selected.

Faithful to command-center/phase3/A4/DESIGN.json:
  * index_text is kind + name only (bodies/roles/instructions excluded)
  * select() is token overlap against index_text, top-k, fallback if all scores 0
  * telemetry has no labelled-recall / gold-miss metric
  * turn_ok if any selection activates (or defined fallback fires)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"

GOLD_ID = "skill.council"
DISTRACTOR_ID = "wf.catalog-class.discovery-only"
BUDGET = 1

# Live-corpus task: four named roles (skill.council body) plus catalog-class
# discovery (workflow name). Gold is the four-voice skill, not the workflow.
TASK = (
    "Use Architect, Skeptic, Pragmatist, and Critic as static prompt sections "
    "to review catalog-class discovery. Do not compile a CouncilSpec expression tree."
)


def tokenize(text: str) -> set[str]:
    s = (text or "").lower()
    buf: list[str] = []
    toks: set[str] = set()
    for ch in s:
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                toks.add("".join(buf))
                buf = []
    if buf:
        toks.add("".join(buf))
    toks.discard("")
    return toks


def name_of(entry: dict[str, Any]) -> str:
    if entry.get("name"):
        return str(entry["name"])
    cid = str(entry.get("id") or "")
    if "." in cid:
        return cid.split(".", 1)[1]
    return cid


def body_text(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("id") or ""),
        str(entry.get("kind") or ""),
        name_of(entry),
        str(entry.get("description") or ""),
        str(entry.get("instructions") or ""),
        str(entry.get("title") or ""),
        str(entry.get("body") or ""),
        " ".join(str(x) for x in (entry.get("roles") or [])),
        json.dumps(entry.get("stages") or [], sort_keys=True, default=str),
    ]
    return " ".join(parts)


def load_registry_caps(path: Path | None = None) -> list[dict[str, Any]]:
    raw = json.loads((path or REGISTRY).read_text(encoding="utf-8"))
    entries = raw.get("entries") or []
    return [e for e in entries if isinstance(e, dict) and e.get("id")]


def index_record(entry: dict[str, Any]) -> dict[str, Any]:
    kind = str(entry.get("kind") or "unknown")
    name = name_of(entry)
    return {
        "capability_id": str(entry["id"]),
        "kind": kind,
        "name": name,
        "index_text": f"{kind} {name}",
        "installed": True,
        "indexed": True,
    }


def overlap(task: str, text: str) -> int:
    return len(tokenize(task) & tokenize(text))


def _rank(task: str, caps: list[dict[str, Any]], field: str) -> list[tuple[int, str, dict[str, Any], dict[str, Any]]]:
    ranked: list[tuple[int, str, dict[str, Any], dict[str, Any]]] = []
    for cap in caps:
        rec = index_record(cap)
        blob = rec["index_text"] if field == "index" else body_text(cap)
        ranked.append((overlap(task, blob), rec["capability_id"], cap, rec))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked


def _telemetry(
    *,
    index_rows: list[dict[str, Any]],
    selected_ids: list[str],
    activation_ok: bool,
    fallback_fired: bool,
    budget_ok: bool,
    errors: list[str],
    explanation: str,
) -> dict[str, Any]:
    nonempty = len(selected_ids) > 0
    installed = [r for r in index_rows if r.get("installed")]
    coverage = bool(installed) and all(r.get("indexed") for r in installed)
    turn_ok = (
        not errors
        and activation_ok
        and budget_ok
        and (nonempty or fallback_fired)
    )
    return {
        "index_coverage_ok": coverage,
        "selection_nonempty": nonempty,
        "activation_ok": activation_ok,
        "budget_ok": budget_ok,
        "fallback_fired": fallback_fired,
        "explanation_emitted": bool(explanation),
        "error_count": len(errors),
        "turn_ok": turn_ok,
    }


def run_gateway(
    task: str,
    caps: list[dict[str, Any]],
    *,
    mode: str = "a4_index",
    budget: int = BUDGET,
) -> dict[str, Any]:
    """Run one turn.

    mode:
      a4_index     — DESIGN select() against index_text only
      body_aware   — control that consults bodies (not A4)
      a1_always_on — catching architecture: every body resident, no select gate
    """
    index_rows = [index_record(c) for c in caps]
    by_id = {str(c["id"]): c for c in caps}
    errors: list[str] = []
    budget_ok = True
    fallback_fired = False
    selected_ids: list[str] = []
    scores: dict[str, int] = {}

    if mode == "a1_always_on":
        selected_ids = sorted(by_id)
        explanation = "A1 always-on: every installed body is resident; no select gate."
        activated = list(selected_ids)
    else:
        field = "index" if mode == "a4_index" else "body"
        ranked = _rank(task, caps, field)
        scores = {cid: sc for sc, cid, _cap, _rec in ranked}
        for sc, cid, _cap, _rec in ranked:
            if sc <= 0:
                continue
            if len(selected_ids) >= budget:
                budget_ok = True
                break
            selected_ids.append(cid)
        if not selected_ids:
            fallback_fired = True
            explanation = "fallback: no positive index overlap; no body materialized."
            activated = []
        else:
            explanation = (
                f"mode={mode} selected={selected_ids} scores="
                + ",".join(f"{k}:{scores.get(k, 0)}" for k in selected_ids)
            )
            activated = list(selected_ids)

    activation_ok = True
    resident_bodies = list(activated)
    tel = _telemetry(
        index_rows=index_rows,
        selected_ids=selected_ids if mode != "a1_always_on" else activated,
        activation_ok=activation_ok,
        fallback_fired=fallback_fired,
        budget_ok=budget_ok,
        errors=errors,
        explanation=explanation,
    )
    return {
        "mode": mode,
        "task": task,
        "index": index_rows,
        "indexed_ids": [r["capability_id"] for r in index_rows],
        "selected_ids": selected_ids if mode != "a1_always_on" else activated,
        "activated_ids": activated,
        "resident_bodies": resident_bodies,
        "scores": scores,
        "explanation": explanation,
        "telemetry": tel,
        "gold_id": GOLD_ID,
        "gold_indexed": GOLD_ID in by_id,
        "gold_selected": GOLD_ID in (selected_ids if mode != "a1_always_on" else activated),
        "distractor_id": DISTRACTOR_ID,
        "distractor_selected": DISTRACTOR_ID in (
            selected_ids if mode != "a1_always_on" else activated
        ),
    }


def turn_metric_view(tel: dict[str, Any]) -> dict[str, Any]:
    """The gateway's own turn health vector (no gold, no labelled recall)."""
    return {
        "index_coverage_ok": bool(tel.get("index_coverage_ok")),
        "selection_nonempty": bool(tel.get("selection_nonempty")),
        "activation_ok": bool(tel.get("activation_ok")),
        "budget_ok": bool(tel.get("budget_ok")),
        "fallback_fired": bool(tel.get("fallback_fired")),
        "explanation_emitted": bool(tel.get("explanation_emitted")),
        "error_count": int(tel.get("error_count") or 0),
        "turn_ok": bool(tel.get("turn_ok")),
    }


def metrics_all_green(tel: dict[str, Any]) -> bool:
    v = turn_metric_view(tel)
    return (
        v["index_coverage_ok"] is True
        and v["selection_nonempty"] is True
        and v["activation_ok"] is True
        and v["budget_ok"] is True
        and v["fallback_fired"] is False
        and v["explanation_emitted"] is True
        and v["error_count"] == 0
        and v["turn_ok"] is True
    )
