"""Class-expansion trigger: EXPAND iff sampled_error_rate > threshold (Fraction)."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from confirmation_queue import enqueue, load_queue

THRESHOLD_REL = "command-center/confirmation/thresholds/CNF-0139-predefined-threshold.json"


@dataclass
class Threshold:
    numer: int
    denom: int
    source_path: str
    frozen_at: str = ""

    @property
    def value(self) -> Fraction:
        return Fraction(self.numer, self.denom)

    def as_dict(self) -> dict[str, Any]:
        return {
            "numer": self.numer,
            "denom": self.denom,
            "as_float": float(self.value),
            "source_path": self.source_path,
            "frozen_at": self.frozen_at,
            "rule": "EXPAND iff sampled_error_rate > threshold (strictly greater)",
        }


def load_threshold(repo: Path) -> Threshold:
    path = Path(repo) / THRESHOLD_REL
    if path.is_file():
        doc = json_load(path)
        frac = doc.get("threshold") or doc
        numer = int(frac.get("numer") or frac.get("numerator") or 1)
        denom = int(frac.get("denom") or frac.get("denominator") or 10)
        return Threshold(
            numer=numer,
            denom=denom,
            source_path=THRESHOLD_REL,
            frozen_at=str(doc.get("frozen_at") or "2026-08-24T00:00:00Z"),
        )
    return Threshold(numer=1, denom=10, source_path=THRESHOLD_REL, frozen_at="2026-08-24T00:00:00Z")


def json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def trigger_source_anchor() -> dict[str, Any]:
    path = Path(__file__).resolve()
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if "def evaluate_class" in ln]
    line = hits[0] if hits else 1
    rel = "command-center/confirmation/class_expansion.py"
    return {
        "path": rel,
        "line": line,
        "citation": f"{rel}:{line}",
        "symbol": "evaluate_class",
    }


def evaluate_class(
    *,
    class_id: str,
    members: list[str],
    n_fail: int,
    n_obs: int,
    n_blocked: int = 0,
    queue_path: Path,
    expanded: set[str] | None = None,
    threshold: Threshold | None = None,
    include_blocked_in_denominator: bool = False,
) -> dict[str, Any]:
    thr = threshold or Threshold(1, 10, THRESHOLD_REL)
    denom = int(n_obs) + (int(n_blocked) if include_blocked_in_denominator else 0)
    if denom <= 0:
        rate = Fraction(0, 1)
    else:
        rate = Fraction(int(n_fail), denom)
    latched = expanded if expanded is not None else set()
    before = load_queue(queue_path)
    before_n = len(before.get("entries") or [])
    if class_id in latched:
        return {
            "class_id": class_id,
            "decision": "SILENT",
            "reason": "already_fully_expanded",
            "rate": f"{rate.numerator}/{rate.denominator}",
            "queue_path": str(queue_path),
            "queue_length_before": before_n,
            "queue_length_after": before_n,
            "queue_length_delta": 0,
            "created_unit_ids": [],
            "persisted_entries": before.get("entries") or [],
        }
    if rate == thr.value:
        decision, reason = "SILENT", "at_threshold"
    elif rate > thr.value:
        decision, reason = "EXPAND", "above_threshold"
    else:
        decision, reason = "SILENT", "below_threshold"
    created: list[str] = []
    if decision == "EXPAND":
        rows = [{"unit_id": uid, "class_id": class_id} for uid in members]
        result = enqueue(queue_path, rows)
        created = [r["unit_id"] for r in result["added"]]
        latched.add(class_id)
    after = load_queue(queue_path)
    after_n = len(after.get("entries") or [])
    return {
        "class_id": class_id,
        "decision": decision,
        "reason": reason,
        "rate": f"{n_fail}/{denom if denom else n_obs}",
        "queue_path": str(queue_path),
        "queue_length_before": before_n,
        "queue_length_after": after_n,
        "queue_length_delta": after_n - before_n,
        "created_unit_ids": created,
        "persisted_entries": after.get("entries") or [],
    }
