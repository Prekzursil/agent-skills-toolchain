"""WorkflowIR corpus for WFA-0096.

The real corpus on this worktree is every WFA catalog unit projected into
the five differ dimensions (stages, roles, gates, tools, stop_rules), plus
on-disk workflow JSON files. Prose fields (title, question) are carried for
paraphrase plants but are not differ dimensions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.I)
DIMENSIONS = ("stages", "roles", "gates", "tools", "stop_rules")
CORPUS_PREFIX = "WFA-"


def canon(value: Any) -> str:
    found = TOKEN_RE.findall(str(value or "").lower())
    return " ".join(found) if found else ""


def _anchor(unit_id: str, field: str) -> str:
    return f"command-center/WORK-UNIT-CATALOG.json#{unit_id}/{field}"


def unit_to_ir(unit: dict[str, Any]) -> dict[str, Any]:
    uid = str(unit["id"])
    tests = [str(t) for t in (unit.get("tests_required") or []) if str(t).strip()]
    role = unit.get("assigned_model_vendor_role") or {}
    tools = [str(p) for p in (unit.get("tool_permissions") or []) if str(p).strip()]
    fails = [str(f) for f in (unit.get("failure_classification") or []) if str(f).strip()]
    stages = [
        {
            "id": f"stage-{i}",
            "kind": "catalog-test",
            "token": canon(t)[:80],
            "source_anchor": _anchor(uid, f"tests_required/{i}"),
        }
        for i, t in enumerate(tests)
    ]
    out_path = str(unit.get("output_path") or "")
    if out_path:
        stages.append(
            {
                "id": "stage-output",
                "kind": "catalog-output",
                "token": "out:" + canon(out_path),
                "source_anchor": _anchor(uid, "output_path"),
            }
        )
    ir = {
        "id": uid,
        "name": str(unit.get("title") or uid),
        "description": str(unit.get("question_or_target") or ""),
        "source_anchor": _anchor(uid, "id"),
        "corpus_kind": "catalog-wfa" if uid.startswith(CORPUS_PREFIX) else "catalog-other",
        "stages": stages,
        "roles": [
            {
                "id": "role-assigned",
                "token": canon(role.get("role") or "none"),
                "vendor": canon(role.get("vendor") or "none"),
                "source_anchor": _anchor(uid, "assigned_model_vendor_role"),
            }
        ],
        "gates": [
            {
                "id": f"gate-{i}",
                "token": canon(t),
                "source_anchor": _anchor(uid, f"tests_required/{i}"),
            }
            for i, t in enumerate(tests)
        ],
        "tools": [
            {
                "id": f"tool-{i}",
                "token": canon(p),
                "source_anchor": _anchor(uid, f"tool_permissions/{i}"),
            }
            for i, p in enumerate(tools)
        ],
        "stop_rules": [
            {
                "id": "stop-timeout",
                "token": f"timeout:{unit.get('timeout_seconds')}",
                "source_anchor": _anchor(uid, "timeout_seconds"),
            },
            {
                "id": "stop-phase",
                "token": "phase:" + canon(unit.get("phase")),
                "source_anchor": _anchor(uid, "phase"),
            },
        ],
    }
    for i, fail in enumerate(fails):
        ir["stop_rules"].append(
            {
                "id": f"stop-fail-{i}",
                "token": "fail:" + canon(fail),
                "source_anchor": _anchor(uid, f"failure_classification/{i}"),
            }
        )
    return ir


def workflow_file_to_ir(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
    rel = path.relative_to(REPO).as_posix()
    wid = str(doc.get("id") or path.stem)
    stages = []
    for i, stage in enumerate(doc.get("stages") or []):
        if not isinstance(stage, dict):
            continue
        stages.append(
            {
                "id": str(stage.get("id") or f"stage-{i}"),
                "kind": str(stage.get("kind") or "workflow-stage"),
                "token": canon(stage.get("id") or "") + " " + canon(stage.get("kind") or ""),
                "source_anchor": f"{rel}#/stages/{i}",
            }
        )
    stopping = doc.get("stopping") if isinstance(doc.get("stopping"), dict) else {}
    ir = {
        "id": f"disk:{wid}",
        "name": wid,
        "description": str(doc.get("discovery_only") or ""),
        "source_anchor": rel,
        "corpus_kind": "disk-workflow",
        "stages": stages,
        "roles": [],
        "gates": [],
        "tools": [],
        "stop_rules": [
            {
                "id": "stop-on-error",
                "token": "on-error:" + canon(stopping.get("on_error") or "unspecified"),
                "source_anchor": f"{rel}#/stopping",
            }
        ],
    }
    if stopping.get("max_stages") is not None:
        ir["stop_rules"].append(
            {
                "id": "stop-max-stages",
                "token": f"max-stages:{stopping.get('max_stages')}",
                "source_anchor": f"{rel}#/stopping/max_stages",
            }
        )
    return ir


def load_catalog_units() -> list[dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    return [u for u in units if isinstance(u, dict) and u.get("id")]


def load_base_corpus() -> list[dict[str, Any]]:
    """Real IR corpus: every WFA catalog unit, plus on-disk workflow JSON."""
    units = load_catalog_units()
    irs = [unit_to_ir(u) for u in units if str(u["id"]).startswith(CORPUS_PREFIX)]
    seen = {ir["id"] for ir in irs}
    for path in sorted(REPO.glob("command-center/p2-wave/probes/ARC-*/fixtures/**/workflows/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        ir = workflow_file_to_ir(path, doc)
        if ir["id"] in seen:
            continue
        seen.add(ir["id"])
        irs.append(ir)
    if len(irs) < 100:
        raise RuntimeError(f"IR corpus too small ({len(irs)}); refusing a toy fixture")
    return irs


def index_by_id(irs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ir in irs:
        out[str(ir["id"])] = ir
    return out
