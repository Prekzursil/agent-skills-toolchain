#!/usr/bin/env python3
"""Probe 2: content classifier on file BODY, not path.

Planted mutant (catalog tests_required): a real authored module under a
scratch-looking path must be rescued by the body classifier while a path-only
classifier loses it. Inverse: a 4000-z blob under src/core must be SCRATCH by
body and REAL-WORK by path.

This probe also tries to FALSIFY the headline counts in the census artifact
when that artifact already exists (independent recount of report.paths).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402

UNIT = "AUD-0006"
ART = REPO / "command-center" / "audit" / "AUD-0006-uncommitted-work-census.json"
REL_REAL = "command-center/p2-wave/probes/AUD-0006/control/tmp/scratch_cache/real_module.py"
REL_JUNK = "command-center/p2-wave/probes/AUD-0006/control/src/core/session_state.py"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def classify_rel(rel: str, cfg: dict) -> dict:
    return C.classify_path(REPO, rel, cfg)


def recount_paths(paths: list[dict]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for row in paths:
        if not isinstance(row, dict):
            continue
        c[str(row.get("content_verdict") or "MISSING")] += 1
    return dict(c)


def try_falsify_artifact() -> dict:
    """Independent recount. Missing artifact is skip, not pass-by-absence of check."""
    if not ART.is_file():
        return {"status": "SKIP", "reason": "artifact-not-yet-written"}
    try:
        doc = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "reason": f"unparseable:{type(exc).__name__}"}
    report = doc.get("report") if isinstance(doc, dict) else None
    if not isinstance(report, dict):
        return {"status": "FAIL", "reason": "report-missing"}
    paths = report.get("paths") or []
    if not isinstance(paths, list):
        return {"status": "FAIL", "reason": "paths-not-list"}
    live = recount_paths(paths)
    claimed = report.get("tally") or {}
    mismatch = {
        k: {"claimed": claimed.get(k), "recounted": live.get(k, 0)}
        for k in set(list(claimed) + list(live))
        if claimed.get(k) != live.get(k, 0)
    }
    if mismatch:
        return {
            "status": "FAIL",
            "reason": "headline-count-falsified",
            "mismatch": mismatch,
            "recount": live,
        }
    return {"status": "PASS", "reason": "headline-matches-independent-recount", "recount": live}


def main() -> int:
    cfg, src = C.load_hygiene_config()
    real = classify_rel(REL_REAL, cfg)
    junk = classify_rel(REL_JUNK, cfg)
    c1 = real["content_verdict"] == "REAL-WORK" and real["path_only_verdict"] == "SCRATCH"
    c2 = junk["content_verdict"] == "SCRATCH" and junk["path_only_verdict"] == "REAL-WORK"
    falsify = try_falsify_artifact()
    falsify_ok = falsify["status"] in {"PASS", "SKIP"}
    ok = c1 and c2 and falsify_ok
    payload = {
        "pass": bool(ok),
        "probe": "probe2-body-classifier",
        "unit_id": UNIT,
        "hygiene_source": src,
        "control_real_under_scratch_path": real,
        "control_blob_under_source_path": junk,
        "rescued_by_content": c1,
        "rejected_by_content": c2,
        "both_directions": c1 and c2,
        "falsify_headline": falsify,
        "reviewer_id": "AUD-0006-probe2-body-classifier",
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if not c1:
        return _fail(f"planted real module not rescued: {real}")
    if not c2:
        return _fail(f"z-blob not rejected as scratch: {junk}")
    if not falsify_ok:
        return _fail(f"headline falsified: {falsify}")
    print(
        "SUCCESS:AUD-0006-probe2 body classifier rescues scratch-path real module "
        "and rejects source-path degenerate blob; path-only strawman loses both"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
