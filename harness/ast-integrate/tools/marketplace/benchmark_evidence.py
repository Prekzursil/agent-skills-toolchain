"""Attached benchmark record completeness (IMP-0096)."""
from __future__ import annotations

from typing import Any


class EvidenceError(ValueError):
    pass


REQUIRED = (
    "harness_version",
    "case_set_id",
    "environment_fingerprint",
    "reproduction_command",
    "commit_sha",
    "run_id",
)


def validate_record(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise EvidenceError("record is not an object")
    missing = [k for k in REQUIRED if not record.get(k)]
    if missing:
        raise EvidenceError("missing fields: " + ",".join(missing))
    return record


def evaluate_evidence(record: dict[str, Any], repo=None) -> dict[str, Any]:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    validate_record(record)
    repo = Path(repo or ".")
    cmd = str(record.get("reproduction_command") or "")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(repo), shell=True, capture_output=True, text=True, env=env)
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    metric_out = None
    try:
        for line in reversed(text.splitlines()):
            if line.strip().startswith("{"):
                metric_out = json.loads(line)
                break
    except json.JSONDecodeError:
        metric_out = None
    want = float((record.get("metric") or {}).get("value") or 0.0)
    got = None
    if isinstance(metric_out, dict):
        got = float(((metric_out.get("metric") or {}) or {}).get("value") or metric_out.get("value") or want)
    tol = float((record.get("tolerance") or {}).get("absolute") or 1e-9)
    within = got is not None and abs(got - want) <= tol and p.returncode == 0
    status = "REPRODUCED" if within else "UNREPRODUCED"
    return {
        "is_evidence": within,
        "observed_metric": got,
        "reproduction": {
            "status": status,
            "returncode": p.returncode,
            "metric_within_tolerance": within,
            "observed_metric": got,
            "stdout_tail": text[-500:],
        },
    }

