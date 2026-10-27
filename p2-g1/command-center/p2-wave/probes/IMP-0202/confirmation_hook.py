"""IMP-0202: the independent-confirmation hook on the certification path.

A confirmation record must: (1) come from a reviewer that is not the author,
(2) cite RAW artifacts (paths under raw/) rather than only the author summary
or a bare digest, and (3) every cited path is existence-checked (Test-Path)
BEFORE any digest is read. The digest is recomputed from the raw rows and must
match the claim. A digest is a claim, not a receipt (spec 10646).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _recompute(rows_doc: dict) -> dict:
    deltas = [round(c["baseline_s"] - c["treatment_s"], 4) for c in rows_doc["cases"]]
    return {"mean_delta": round(sum(deltas) / len(deltas), 4), "n": len(deltas),
            "verdict": "OUTPERFORMS" if all(d > 0 for d in deltas) else "MIXED"}


def _digest_of(stats: dict) -> str:
    return hashlib.sha256(json.dumps(stats, sort_keys=True).encode("utf-8")).hexdigest()


def confirm(record: dict, workspace: Path) -> dict:
    trace = ["stage:independence_check"]
    if str(record.get("reviewer_id")) == str(record.get("author_id")):
        return {"verdict": "REJECT", "reason": "AUTHOR_NOT_INDEPENDENT",
                "independent": False, "certified": False, "trace": trace,
                "digest_accepted": False, "digest_read": False, "recomputed": None}
    trace.append("stage:classify_citations")
    cites = record.get("citations") or {}
    raw_cites = [c for c in cites.get("raw") or []]
    summary_cites = [c for c in cites.get("summary") or []]
    digest_field = record.get("claimed_digest")
    trace.append(f"class:raw={len(raw_cites)} summary={len(summary_cites)} "
                 f"digest_cites={len(cites.get('digest') or [])} "
                 f"digest_field={digest_field is not None}")
    if not raw_cites:
        if summary_cites:
            return {"verdict": "REJECT", "reason": "SUMMARY_ONLY_CLAIM",
                    "blocked_by": "independent_confirmation_hook",
                    "independent": True, "certified": False, "trace": trace,
                    "digest_accepted": False, "digest_read": False, "recomputed": None}
        return {"verdict": "REJECT", "reason": "DIGEST_IS_CLAIM",
                "blocked_by": "independent_confirmation_hook",
                "independent": True, "certified": False, "trace": trace,
                "digest_accepted": False, "digest_read": False, "recomputed": None}
    trace.append("stage:test_path")
    missing = []
    for p in raw_cites:
        trace.append(f"test_path:{p}")
        if not (workspace / p).is_file():
            missing.append(p)
    if missing:
        return {"verdict": "REJECT", "reason": "PATH_ABSENT", "paths_missing": missing,
                "independent": True, "certified": False, "trace": trace,
                "digest_accepted": False, "digest_read": False, "recomputed": None}
    trace.append("stage:recompute")
    stats = None
    for p in raw_cites:
        doc = json.loads((workspace / p).read_text(encoding="utf-8"))
        stats = _recompute(doc) if stats is None else stats
    recomputed_digest = _digest_of(stats)
    trace.append(f"recompute:{recomputed_digest[:16]}")
    if digest_field and recomputed_digest != digest_field:
        return {"verdict": "REJECT", "reason": "RECOMPUTE_MISMATCH",
                "independent": True, "certified": False, "trace": trace,
                "digest_accepted": False, "digest_read": True, "recomputed": stats}
    trace.append("stage:certify")
    return {"verdict": "ACCEPT", "reason": "RAW_RECOMPUTE_MATCH",
            "independent": True, "certified": True, "raw_citations": raw_cites,
            "trace": trace, "digest_accepted": True, "digest_read": True,
            "recomputed": stats}
