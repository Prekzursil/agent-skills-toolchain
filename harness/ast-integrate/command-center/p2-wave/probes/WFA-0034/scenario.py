#!/usr/bin/env python3
"""Load the candidate set and run the maintenance extractor."""
from __future__ import annotations

import json
from pathlib import Path

from engine import extract_all, mutant_drop_archived_flag, mutant_infer_unreachable
from transport import FixtureTransport

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_REGISTRY = HERE / "fixtures" / "registry.json"
AUTHORITATIVE_CANDIDATES = [
    Path(
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def authoritative_registry_hit() -> dict:
    for path in AUTHORITATIVE_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            data = load_json(path)
            n = 0
            if isinstance(data, dict):
                n = len(data.get("candidates") or [])
            return {
                "present": True,
                "path": str(path),
                "n_candidates": n,
            }
    return {
        "present": False,
        "path": None,
        "n_candidates": 0,
        "searched": [str(p) for p in AUTHORITATIVE_CANDIDATES],
    }


def load_candidates() -> tuple[list[dict], dict]:
    hit = authoritative_registry_hit()
    data = load_json(FIXTURE_REGISTRY)
    if not isinstance(data, dict):
        raise FileNotFoundError(str(FIXTURE_REGISTRY))
    candidates = [c for c in (data.get("candidates") or []) if isinstance(c, dict)]
    return candidates, {
        "fixture_registry": str(FIXTURE_REGISTRY.relative_to(REPO).as_posix()),
        "authoritative_284": hit,
        "note": data.get("note"),
    }


def run_extraction() -> dict:
    candidates, meta = load_candidates()
    transport = FixtureTransport(HERE)
    result = extract_all(candidates, transport)
    result["source_meta"] = meta
    result["n_scheduler_calls"] = len(result.get("scheduler_log") or [])
    return result


def negative_controls() -> dict:
    candidates, _meta = load_candidates()
    transport = FixtureTransport(HERE)
    good = extract_all(candidates, transport)
    inferred = mutant_infer_unreachable(candidates, transport)
    dropped = mutant_drop_archived_flag(good)
    from engine import prose_leaked_into_measured

    infer_fired = any(
        prose_leaked_into_measured(r)
        for r in inferred.get("rows") or []
        if r.get("candidate_id") == "wf-ext-unreachable"
    )
    drop_fired = not any(
        (r.get("disposition_flag") or {}).get("adopt_as_is_risk")
        for r in dropped.get("rows") or []
        if r.get("candidate_id") == "wf-ext-archived-adopt"
    )
    good_silent_infer = not any(
        prose_leaked_into_measured(r)
        for r in good.get("rows") or []
        if r.get("status") == "NOT-CHECKED"
    )
    good_silent_drop = any(
        (r.get("disposition_flag") or {}).get("adopt_as_is_risk")
        for r in good.get("rows") or []
        if r.get("candidate_id") == "wf-ext-archived-adopt"
    )
    return {
        "infer_from_prose": {
            "id": "WFA-0034-INFER-FROM-PROSE-MUTANT",
            "fired_on_bad_state": infer_fired,
            "silent_on_good_state": good_silent_infer,
        },
        "drop_archived_flag": {
            "id": "WFA-0034-DROP-ARCHIVED-ADOPT-FLAG-MUTANT",
            "fired_on_bad_state": drop_fired,
            "silent_on_good_state": good_silent_drop,
        },
        "pass": infer_fired and drop_fired and good_silent_infer and good_silent_drop,
    }
