"""Design-rationale lint: load-bearing claims must resolve on disk (IMP-0214)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PASS = "PASS"
REJECTED = "REJECTED"
PATH_LINE = re.compile(r"([\w./\\-]+\.[A-Za-z0-9]+):(\d+)")


def _ledger_ids(root: Path, ledger_rel: str | None) -> set[str]:
    if not ledger_rel:
        return set()
    path = root / ledger_rel
    if not path.is_file():
        return set()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = set()
    for run in doc.get("runs") or []:
        if isinstance(run, dict) and run.get("id"):
            ids.add(str(run["id"]))
    return ids


def _file_line_ok(root: Path, anchor: dict[str, Any]) -> tuple[bool, str]:
    rel = str(anchor.get("path") or "").replace("\\", "/")
    if not rel:
        return False, "missing-path"
    path = root / rel
    if not path.is_file():
        return False, f"missing-file:{rel}"
    try:
        line_no = int(anchor.get("line") or 0)
    except (TypeError, ValueError):
        return False, "bad-line"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return False, f"oob:{rel}:{line_no}"
    snippet = str(anchor.get("snippet") or "")
    if snippet and snippet not in lines[line_no - 1]:
        return False, f"snippet-miss:{rel}:{line_no}"
    return True, ""


def _normalize_anchors(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not raw:
        return out
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str):
                m = PATH_LINE.search(item)
                if m:
                    out.append(
                        {
                            "kind": "file_line",
                            "path": m.group(1).replace("\\", "/"),
                            "line": int(m.group(2)),
                            "snippet": "",
                        }
                    )
                else:
                    out.append({"kind": "opaque", "text": item})
    return out


def lint_rationale(doc: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    root = Path(root) if root is not None else Path.cwd()
    violations: list[dict[str, Any]] = []
    ledger_rel = doc.get("benchmark_ledger")
    known_runs = _ledger_ids(root, str(ledger_rel) if ledger_rel else None)
    decisions = list(doc.get("decisions") or [])
    for row in decisions:
        load_bearing = bool(row.get("load_bearing"))
        anchors = _normalize_anchors(row.get("anchors"))
        if load_bearing and not anchors:
            violations.append(
                {
                    "code": "UNANCHORED_LOAD_BEARING",
                    "decision": row.get("id"),
                    "detail": "load-bearing decision has no anchors",
                }
            )
            text = str(row.get("text") or "")
            narrative = str(doc.get("narrative") or "")
            if text and text in narrative:
                violations.append(
                    {
                        "code": "LOAD_BEARING_PROSE_UNANCHORED",
                        "decision": row.get("id"),
                        "detail": "narrative repeats unanchored claim",
                    }
                )
            continue
        for anchor in anchors:
            kind = str(anchor.get("kind") or "")
            if kind == "file_line":
                ok, detail = _file_line_ok(root, anchor)
                if not ok:
                    violations.append(
                        {
                            "code": "UNRESOLVED_FILE_LINE",
                            "decision": row.get("id"),
                            "detail": detail,
                        }
                    )
            elif kind == "benchmark_run":
                run_id = str(anchor.get("run_id") or "")
                if run_id not in known_runs:
                    violations.append(
                        {
                            "code": "UNRESOLVED_BENCHMARK_RUN",
                            "decision": row.get("id"),
                            "detail": run_id,
                        }
                    )
            elif kind == "inference":
                inferred = str(anchor.get("inferred_from") or "")
                # Must name a path that exists somewhere in the string.
                hit = False
                for token in inferred.replace("\\", "/").split():
                    cand = token.strip(",")
                    if "/" in cand and (root / cand).is_file():
                        hit = True
                        break
                if not hit:
                    violations.append(
                        {
                            "code": "UNRESOLVED_INFERENCE",
                            "decision": row.get("id"),
                            "detail": inferred,
                        }
                    )
            elif kind == "opaque":
                violations.append(
                    {
                        "code": "UNRESOLVED_FILE_LINE",
                        "decision": row.get("id"),
                        "detail": str(anchor.get("text") or ""),
                    }
                )
    ok = not violations
    return {
        "ok": ok,
        "verdict": PASS if ok else REJECTED,
        "violations": violations,
        "violation_count": len(violations),
    }


def emit_rationale(
    workflow_id: str,
    goal: str,
    decisions: list[dict[str, Any]],
    root: Path | None = None,
    sources: list[Any] | None = None,
    benchmark_ledger: Any = None,
) -> dict[str, Any]:
    doc = {
        "schema": "workflow-forge.design-rationale.v1",
        "workflow_id": workflow_id,
        "goal": goal,
        "decisions": list(decisions),
        "sources": list(sources or []),
        "benchmark_ledger": benchmark_ledger,
    }
    lint = lint_rationale(doc, root=root)
    if not lint["ok"]:
        raise ValueError(f"rationale rejected: {[v['code'] for v in lint['violations']]}")
    doc["lint"] = {"verdict": PASS, "violation_count": 0, "ok": True}
    return doc
