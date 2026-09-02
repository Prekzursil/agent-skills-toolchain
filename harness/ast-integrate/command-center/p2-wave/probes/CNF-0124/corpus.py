"""Load confirmation receipts: live corpus if present, plus CNF-0124 fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
LIVE_DIRS = [
    REPO / "command-center" / "confirmation",
    REPO / "command-center" / "receipts",
]
SKIP_NAMES = {
    "CNF-0124-authorship-audit.json",
    "CNF-0002-independence-predicate.json",
}


def _is_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    has_claim = "claim_id" in doc or "claim" in doc
    has_confirmer = any(k in doc for k in ("confirmer", "confirmer_identity", "confirmer_id"))
    has_verdict = "verdict" in doc or "independence_verdict" in doc
    return bool(has_claim and (has_confirmer or has_verdict) and "receipt_id" in doc)


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def load_fixtures() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(FIXTURES.glob("*.json")):
        doc = _load_json(path)
        if isinstance(doc, dict):
            doc = dict(doc)
            doc["_source"] = f"fixture:{path.name}"
            doc["_source_path"] = str(path.relative_to(REPO)).replace("\\", "/")
            rows.append(doc)
    return rows


def load_live() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for root in LIVE_DIRS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.name in SKIP_NAMES:
                continue
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            if rel in seen:
                continue
            doc = _load_json(path)
            if not _is_receipt(doc):
                continue
            seen.add(rel)
            rec = dict(doc)
            rec["_source"] = f"live:{rel}"
            rec["_source_path"] = rel
            rows.append(rec)
    return rows


def load_corpus() -> dict:
    live = load_live()
    fixtures = load_fixtures()
    return {
        "live": live,
        "fixtures": fixtures,
        "all": live + fixtures,
        "live_empty": len(live) == 0,
    }
