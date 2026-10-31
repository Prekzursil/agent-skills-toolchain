"""Run a research blueprint over a corpus into an artifact."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_blueprint(
    bp: dict[str, Any],
    corpus: list[dict[str, Any]],
    out_path: Path | None = None,
    skip_contradiction_search: bool = False,
    drop_negative: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    work = list(corpus)
    if drop_negative:
        work = [r for r in work if r.get("label") != "negative"]
    neg = [r for r in work if r.get("label") == "negative"]
    fav = [r for r in work if r.get("label") != "negative"]
    report = {
        "blueprint_id": bp.get("id"),
        "counts": {"n": len(work), "favorable": len(fav), "negative": len(neg)},
        "negative_ids": [r["id"] for r in neg],
    }
    ledger = {"empty_ledger_proven": True, "events": []}
    if skip_contradiction_search:
        gate = {"fired": True, "code": "missing_contradiction_search", "reason": "skipped"}
        ledger = {"empty_ledger_proven": False, "events": [], "dropped_negative_ids": [r["id"] for r in corpus if r.get("label") == "negative"]}
    elif drop_negative:
        gate = {"fired": True, "code": "missing_contradiction_search", "reason": "dropped-negative"}
        ledger = {
            "empty_ledger_proven": False,
            "events": [],
            "dropped_negative_ids": [r["id"] for r in corpus if r.get("label") == "negative"],
        }
    elif not neg:
        gate = {"fired": True, "code": "missing_contradiction_search", "reason": "all-favorable"}
    else:
        gate = {"fired": False, "code": "ok", "reason": "silent"}
    doc = {
        "unit_id": "IMP-0234",
        "state": "SUCCESS",
        "report": report,
        "ledger": ledger,
        "gate": gate,
        "blueprint": {"id": bp.get("id"), "tier": bp.get("tier")},
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"report": report, "ledger": ledger, "gate": gate, "ok": True}
