"""Per-workflow regression baselines with corpus/spec gates (IMP-0201).

A certified workflow gets a NAMED baseline frozen with its corpus_version
and spec_version. A later run is compared against it ONLY under the same
corpus: a cross-corpus comparison is REFUSED with a named reason, because
comparing across corpora is the quiet way a regression gate stops
measuring anything. The delta is recomputed from per-case ROWS - a stored
summary is a claim, not a receipt, and a summary-only freeze is refused.
"""
from __future__ import annotations

# g1-mod: real-surface

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

HERE = Path(__file__).resolve().parent

REASON_CROSS_CORPUS = "CROSS_CORPUS_REFUSED"
REASON_SPEC_MISMATCH = "SPEC_VERSION_MISMATCH_REFUSED"
REASON_SUMMARY_ONLY = "SUMMARY_ONLY_REFUSED"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Result:
    ok: bool = True
    status: str = "ok"
    state: str = "SUCCESS"
    verdict: str = "PASS"
    reason: str = ""
    terminal: bool = True
    substitutions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    seated: list = field(default_factory=list)
    requested: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    outcome: str = "clean"
    exit_code: int = 0
    trusted: bool = True
    accepted: bool = True
    blocked: bool = False
    passed: bool = True
    present: bool = True
    found: bool = True
    planted: bool = True
    file_count: int = 0
    payload_bytes: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "state": self.state,
                "verdict": self.verdict, "accepted": self.accepted,
                "blocked": self.blocked, "passed": self.passed}


def _rows_of(doc: Any) -> list[dict[str, Any]]:
    rows = (doc or {}).get("per_case_rows")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and "value" in r]


def _mean_delta(run_rows: list[dict[str, Any]], base_rows: list[dict[str, Any]]) -> tuple:
    n = min(len(run_rows), len(base_rows))
    numerator = sum(int(r["value"]) - int(b["value"]) for r, b in zip(run_rows, base_rows))
    if n == 0:
        return 0.0, 0, 0
    return numerator / n, numerator, n


def freeze_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    """Freeze a baseline. A summary-only freeze (no per_case_rows) is refused."""
    rows = _rows_of(baseline)
    if not rows:
        return {
            "ok": False,
            "accepted": False,
            "refused": True,
            "reason": REASON_SUMMARY_ONLY,
            "detail": "baseline carries no per_case_rows; a summary is a claim, not a receipt",
        }
    doc = dict(baseline)
    doc["frozen"] = True
    doc["n_cases"] = len(rows)
    doc["baseline_sha256"] = _sha(json.dumps(doc, sort_keys=True).encode("utf-8"))
    return {"ok": True, "accepted": True, "frozen": True,
            "baseline": doc, "n_cases": len(rows)}


def compare_to_baseline(run: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Compare a run against its frozen baseline under corpus+spec gates."""
    run_corpus = str((run or {}).get("corpus_version") or "")
    base_corpus = str((baseline or {}).get("corpus_version") or "")
    if run_corpus != base_corpus:
        return {
            "ok": False,
            "accepted": False,
            "refused": True,
            "reason": REASON_CROSS_CORPUS,
            "detail": (
                "cross-corpus comparison refused: run corpus_version "
                + repr(run_corpus) + " differs from baseline corpus_version "
                + repr(base_corpus)
            ),
        }
    run_spec = str((run or {}).get("spec_version") or "")
    base_spec = str((baseline or {}).get("spec_version") or "")
    if run_spec != base_spec:
        return {
            "ok": False,
            "accepted": False,
            "refused": True,
            "reason": REASON_SPEC_MISMATCH,
            "detail": "spec_version " + repr(run_spec) + " != baseline " + repr(base_spec),
        }
    base_rows = _rows_of(baseline)
    if not base_rows:
        return {
            "ok": False,
            "accepted": False,
            "refused": True,
            "reason": REASON_SUMMARY_ONLY,
            "detail": "baseline has no per_case_rows to recompute from",
        }
    run_rows = _rows_of(run)
    mean, numerator, n = _mean_delta(run_rows, base_rows)
    return {
        "ok": True,
        "accepted": True,
        "refused": False,
        "reason": "",
        "mean_delta": mean,
        "mean_delta_numerator": numerator,
        "mean_delta_denominator": n,
        "n_cases": n,
        "summary_consulted": False,
    }


def compare_ignoring_corpus_for_control(run: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Known-broken control sibling: corpus gate REMOVED.

    Accepts the cross-corpus pair the real gate refuses, and reports the
    spec-gate verdict it would still apply. Its acceptance is the proof the
    corpus gate is load-bearing.
    """
    ungated = bool(_rows_of(baseline)) and bool(_rows_of(run))
    good_ok = ungated
    run_spec = str((run or {}).get("spec_version") or "")
    base_spec = str((baseline or {}).get("spec_version") or "")
    spec_reason = REASON_SPEC_MISMATCH if run_spec != base_spec else ""
    return {"good_ok": good_ok, "ungated_ok": good_ok, "spec_reason": spec_reason}


def delta_from_rows(run_rows: list, baseline_rows: list) -> dict[str, Any]:
    """Recompute mean delta from per-case rows only (no summary parameter exists)."""
    rr = [r for r in (run_rows or []) if isinstance(r, dict) and "value" in r]
    br = [r for r in (baseline_rows or []) if isinstance(r, dict) and "value" in r]
    mean, numerator, n = _mean_delta(rr, br)
    return {
        "ok": True,
        "mean_delta": mean,
        "mean_delta_numerator": numerator,
        "mean_delta_denominator": n,
        "n_cases": n,
        "summary_consulted": False,
    }


def make_run(corpus_version: str, spec_version: str, values: list) -> dict[str, Any]:
    """Build a run document with per-case rows from raw values."""
    return {
        "corpus_version": corpus_version,
        "spec_version": spec_version,
        "per_case_rows": [{"case": "c" + str(i), "value": int(v)} for i, v in enumerate(values)],
    }


def load_json(path: Any) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: Any, doc: Any) -> None:
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


__all__ = ["REASON_CROSS_CORPUS", "REASON_SPEC_MISMATCH", "REASON_SUMMARY_ONLY",
           "Result", "compare_ignoring_corpus_for_control", "compare_to_baseline",
           "delta_from_rows", "dump_json", "freeze_baseline", "load_json", "make_run"]
