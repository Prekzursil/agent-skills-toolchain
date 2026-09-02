#!/usr/bin/env python3
"""CI column: persist a run record and re-read its conclusion field.

A stored summary is stale evidence. Cells in the CI column are filled by
reading run['jobs'][claim_id]['conclusion'] from the run file after the
chroot finishes, never from an in-memory copy and never from ci-summary.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from container import run_container

HERE = Path(__file__).resolve().parent
RUNS = HERE / "ci-runs"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def job_conclusion(result: dict[str, Any]) -> str:
    return "success" if result.get("ok") else "failure"


def write_stale_summary(path: Path, live_conclusion: str) -> dict[str, Any]:
    """Deliberately wrong headline, to prove cells must not read this file."""
    stale = "failure" if live_conclusion == "success" else "success"
    doc = {
        "headline": "stale stored CI summary — not a run record",
        "conclusion": stale,
        "source": "summary",
        "captured_at": "1970-01-01T00:00:00Z",
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


def persist_run(*, run_id: str, nonce: str, container_payload: dict[str, Any]) -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    jobs = {}
    overall = "success"
    for row in container_payload.get("results") or []:
        cid = str(row["claim_id"])
        conc = job_conclusion(row)
        jobs[cid] = {
            "conclusion": conc,
            "value": row.get("value"),
            "ok": row.get("ok"),
            "rule": row.get("rule"),
        }
        if conc != "success" and cid.startswith("C-PORTABLE"):
            overall = "failure"
    # Windows-specific FAIL on CI (Linux) is expected; it does not fail the run.
    doc = {
        "id": run_id,
        "name": "cnf0151-portable-subset",
        "status": "completed",
        "conclusion": overall,
        "html_url": f"file://{RUNS / (run_id + '.json')}",
        "run_started_at": _now(),
        "head_sha": (container_payload.get("container") or {}).get("digest", ""),
        "jobs": jobs,
        "container": container_payload.get("container"),
        "host_cache_visible": container_payload.get("host_cache_visible"),
        "nonce": nonce,
        "source": "run",
    }
    path = RUNS / f"{run_id}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def reread_run(path: Path) -> dict[str, Any]:
    """Re-read the run's own conclusion field. Callers must not pass a summary."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("source") != "run":
        raise ValueError(f"refusing non-run record {path}: source={doc.get('source')}")
    if "conclusion" not in doc:
        raise ValueError(f"run {path} missing conclusion")
    return doc


def run_ci_column(*, run_id: str, nonce: str) -> dict[str, Any]:
    payload = run_container(nonce=f"ci-{nonce}", extra_binds=None, pathext="")
    run_path = persist_run(run_id=run_id, nonce=nonce, container_payload=payload)
    summary_path = HERE / "ci-summary.json"
    live = json.loads(run_path.read_text(encoding="utf-8"))
    stale = write_stale_summary(summary_path, live["conclusion"])
    reread = reread_run(run_path)
    if reread["conclusion"] == stale["conclusion"]:
        raise RuntimeError("stale summary conclusion collided with live run; plant failed")
    repo = HERE.parents[3]
    return {
        "payload": payload,
        "run_path": str(run_path),
        "run_path_rel": str(run_path.relative_to(repo)),
        "summary_path_rel": str(summary_path.relative_to(repo)),
        "run": reread,
        "stale_summary": stale,
        "used_source": "run.conclusion",
        "rejected_source": "ci-summary.conclusion",
    }
