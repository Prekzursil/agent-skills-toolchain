"""Load the append-only results ledger and TEST-REGISTRY.

Absence is recorded, never invented. Resolution still runs (empty index)
before any unbacked verdict.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LEDGER_REL = "command-center/bench/results"
REGISTRY_REL = "command-center/TEST-REGISTRY.json"
PASS_STATUS = frozenset({"pass", "passed", "success", "ok", "green", "true"})
FAIL_STATUS = frozenset({"fail", "failed", "failure", "error", "red", "false"})


def _as_row(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    run_id = (
        obj.get("run_id")
        or obj.get("runId")
        or obj.get("id")
        or obj.get("result_id")
    )
    if not run_id:
        return None
    return {
        "run_id": str(run_id),
        "status": str(obj.get("status") or obj.get("result") or obj.get("outcome") or ""),
        "commit": str(
            obj.get("commit")
            or obj.get("commit_sha")
            or obj.get("git_sha")
            or obj.get("revision")
            or ""
        ).lower(),
        "unit_id": str(obj.get("unit_id") or obj.get("unit") or obj.get("authoring_unit") or ""),
        "ok": obj.get("ok"),
        "passed": obj.get("passed"),
        "raw": obj,
    }


def run_passed(row: dict[str, Any]) -> bool | None:
    st = str(row.get("status") or "").strip().lower()
    if st in PASS_STATUS:
        return True
    if st in FAIL_STATUS:
        return False
    if row.get("ok") is True or row.get("passed") is True:
        return True
    if row.get("ok") is False or row.get("passed") is False:
        return False
    return None


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _rows_from_json(doc: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(doc, list):
        for item in doc:
            row = _as_row(item)
            if row:
                out.append(row)
    elif isinstance(doc, dict):
        for key in ("runs", "results", "entries", "records", "items"):
            val = doc.get(key)
            if isinstance(val, list):
                for item in val:
                    row = _as_row(item)
                    if row:
                        out.append(row)
        row = _as_row(doc)
        if row:
            out.append(row)
    return out


def load_ledger(repo: Path, *, ledger_dir: str | None = None) -> dict[str, Any]:
    rel = ledger_dir or LEDGER_REL
    root = repo / rel
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    present = root.is_dir()
    if present:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".jsonl"}:
                continue
            files.append(path.relative_to(repo).as_posix())
            if path.suffix.lower() == ".jsonl":
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _as_row(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if row:
                        rows.append(row)
            else:
                rows.extend(_rows_from_json(_load_json(path)))
    by_run: dict[str, dict[str, Any]] = {}
    by_unit: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_run[row["run_id"]] = row
        uid = row.get("unit_id") or ""
        if uid:
            by_unit.setdefault(uid, []).append(row)
    return {
        "path": rel,
        "present": present,
        "files": files,
        "row_count": len(rows),
        "by_run_id": by_run,
        "by_unit_id": by_unit,
        "rows": rows,
    }


def load_registry(repo: Path, *, registry_rel: str | None = None) -> dict[str, Any]:
    rel = registry_rel or REGISTRY_REL
    path = repo / rel
    present = path.is_file() and path.stat().st_size > 0
    doc = _load_json(path) if present else None
    by_unit: dict[str, str] = {}
    by_test: dict[str, str] = {}
    if isinstance(doc, dict):
        items = doc.get("tests") or doc.get("entries") or doc.get("items") or []
        if isinstance(items, dict):
            items = [
                {"id": k, **v} if isinstance(v, dict) else {"id": k}
                for k, v in items.items()
            ]
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                run_id = str(item.get("latest_run_id") or item.get("run_id") or "")
                uid = str(item.get("unit_id") or item.get("unit") or "")
                tid = str(item.get("id") or item.get("test_id") or "")
                if uid and run_id:
                    by_unit[uid] = run_id
                if tid and run_id:
                    by_test[tid] = run_id
    return {
        "path": rel,
        "present": present,
        "parseable": doc is not None if present else False,
        "by_unit_id": by_unit,
        "by_test_id": by_test,
    }


def commits_match(claim_commit: str, row_commit: str) -> bool:
    a = (claim_commit or "").lower().strip()
    b = (row_commit or "").lower().strip()
    if not a or not b:
        return False
    if len(a) < 7 or len(b) < 7:
        return a == b
    return a.startswith(b) or b.startswith(a)
