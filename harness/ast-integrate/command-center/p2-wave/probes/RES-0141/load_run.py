"""Load frozen corpus + labels and score the live detector. No I/O besides reads."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import CORPUS, LABELS, load_json  # noqa: E402
from labels import assign  # noqa: E402
from score import evaluate  # noqa: E402


def gold_flag(row: dict) -> bool:
    return bool(row.get("gold_breaking", row.get("gold_breaking")))


def control_flag(row: dict) -> bool:
    return bool(row.get("control_negative") or row.get("control_negative"))


def best_silent(ev: dict) -> dict:
    return ev.get("best_silent_on_controls") or ev.get("best_silent_on_controls") or {}


def live() -> tuple[dict, dict, dict]:
    corpus = load_json(CORPUS)
    assigned = assign(corpus)
    disk = load_json(LABELS) if LABELS.is_file() else assigned
    # Prefer in-memory assign (same rule as labels.py). Disk must agree on ids.
    disk_ids = {r["id"] for r in (disk.get("labels") or [])}
    mem_ids = {r["id"] for r in assigned["labels"]}
    if disk_ids and disk_ids != mem_ids:
        raise RuntimeError("labels.json ids != assign(corpus) ids")
    ev = evaluate(corpus["notes"], assigned["labels"])
    return corpus, assigned, ev
