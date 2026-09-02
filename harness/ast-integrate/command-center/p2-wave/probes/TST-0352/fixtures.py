"""Planted ledger rows for TST-0352 missing-field and census controls."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from bench.environment_record import MANDATORY_FIELDS, make_complete_record

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "fixtures" / "historical.jsonl"


def admitted_result() -> dict:
    return {
        "id": "h-complete",
        "metric": 1.0,
        "environment_record": make_complete_record(),
    }


def rejected_missing(field: str) -> dict:
    env = make_complete_record()
    del env[field]
    return {
        "id": f"h-missing-{field}",
        "metric": 0.0,
        "environment_record": env,
    }


def rejected_no_env() -> dict:
    return {"id": "h-no-environment", "metric": 0.0}


def planted_rows() -> list[dict]:
    rows = [admitted_result()]
    for field in MANDATORY_FIELDS:
        rows.append(rejected_missing(field))
    rows.append(rejected_no_env())
    return rows


def write_historical_jsonl(path: Path | None = None) -> Path:
    out = path or LEDGER
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in planted_rows()]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def named_shell_pair() -> tuple[dict, dict]:
    """pwsh7 vs Git Bash overlays of the same complete measurement."""
    base = make_complete_record()
    git_bash = deepcopy(base)
    git_bash["shell"] = {
        "name": "git-bash",
        "path": r"C:\Program Files\Git\bin\bash.exe",
        "version": "GNU bash, version 5.2.21(1)-release",
    }
    pwsh7 = deepcopy(base)
    pwsh7["shell"] = {
        "name": "pwsh7",
        "path": r"C:\Program Files\PowerShell\7\pwsh.exe",
        "version": "PowerShell 7.4.6",
    }
    return git_bash, pwsh7
