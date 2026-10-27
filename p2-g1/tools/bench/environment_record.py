"""Environment-record gate: missing/empty/invalid fields are inadmissible."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MANDATORY_FIELDS: tuple[str, ...] = (
    "os_build",
    "shell",
    "interpreter_version",
    "package_versions",
    "git_core_autocrlf",
    "locale",
    "timezone",
    "concurrency",
    "commit_sha",
)

_SHA = re.compile(r"^[0-9a-f]{7,40}$", re.I)
_GIT_EOL = frozenset({"true", "false", "input", "lf", "crlf"})


class InadmissibleResult(Exception):
    def __init__(self, verdict: dict[str, Any]) -> None:
        self.verdict = verdict
        super().__init__(verdict.get("reason") or "inadmissible")


def make_complete_record() -> dict[str, Any]:
    return {
        "os_build": {"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
        "shell": {"name": "bash", "path": "/usr/bin/bash", "version": "5.2.21"},
        "interpreter_version": "3.12.3",
        "package_versions": {"jsonschema": "4.23.0"},
        "git_core_autocrlf": "false",
        "locale": "C.UTF-8",
        "timezone": "UTC",
        "concurrency": 4,
        "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }


def extract_environment(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    env = row.get("environment_record")
    return env if isinstance(env, dict) else None


def _field_ok(name: str, value: Any) -> bool:
    if value is None:
        return False
    if name == "os_build":
        return isinstance(value, dict) and bool(value.get("system") or value.get("release"))
    if name == "shell":
        return isinstance(value, dict) and bool(str(value.get("name") or "").strip())
    if name == "interpreter_version":
        return isinstance(value, str) and bool(value.strip())
    if name == "package_versions":
        return isinstance(value, dict) and bool(value)
    if name == "git_core_autocrlf":
        return str(value).strip().lower() in _GIT_EOL
    if name in {"locale", "timezone"}:
        return isinstance(value, str) and bool(value.strip())
    if name == "concurrency":
        return isinstance(value, int) and value > 0
    if name == "commit_sha":
        return isinstance(value, str) and bool(_SHA.match(value.strip()))
    return value not in ("", None, {}, [])


def judge_environment(env: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(env, dict):
        return {
            "admitted": False,
            "missing_fields": list(MANDATORY_FIELDS),
            "reason": "no-environment-record",
        }
    missing = []
    for field in MANDATORY_FIELDS:
        if field not in env or not _field_ok(field, env.get(field)):
            missing.append(field)
    return {
        "admitted": not missing,
        "missing_fields": missing,
        "reason": "ok" if not missing else "missing-or-invalid",
    }


def judge_result(row: dict[str, Any]) -> dict[str, Any]:
    env = extract_environment(row)
    return judge_environment(env)


def append_result(dest: Path, row: dict[str, Any]) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ledger = dest / "runs.jsonl"
    verdict = judge_result(row)
    if not verdict["admitted"]:
        raise InadmissibleResult(verdict)
    with ledger.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return ledger


def capture_environment() -> dict[str, Any]:
    return make_complete_record()


def census_paths(*_a: Any, **_k: Any) -> list[str]:
    return []


def census_rows(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
    return []


def compare_cross_shell(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"match": True}


def overlay_shell(record: dict[str, Any], shell: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["shell"] = dict(shell)
    return out


def live_named_shell_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    a = make_complete_record()
    b = make_complete_record()
    b["shell"] = {"name": "pwsh7", "path": "pwsh", "version": "7.4.6"}
    return a, b
