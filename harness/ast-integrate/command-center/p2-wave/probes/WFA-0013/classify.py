#!/usr/bin/env python3
"""Classify a committed blob as WORKFLOW, NON-WORKFLOW, or AMBIGUOUS.

Binary verdicts are refused: a file that looks workflow-adjacent but does not
meet either bar is AMBIGUOUS, never forced.
"""
from __future__ import annotations

import json
import re
from typing import Any

WORKFLOW = "WORKFLOW"
NON_WORKFLOW = "NON-WORKFLOW"
AMBIGUOUS = "AMBIGUOUS"

_ON_LINE = re.compile(r"(?m)^(?:on|'on'|\"on\")\s*:")
_JOBS_LINE = re.compile(r"(?m)^(?:jobs|'jobs'|\"jobs\")\s*:")
_WORKFLOW_DISPATCH = re.compile(r"\bworkflow_dispatch\b")
_STAGE_SEQ = re.compile(
    r"(?im)\b(stages|pipeline|orchestration)\b.*=.*\[",
)
_STOP_RULE = re.compile(r"(?im)\b(stop_rule|halt|max_stages|on_error)\b")


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _decode(blob: bytes) -> str:
    if b"\0" in blob[:1024]:
        return ""
    return blob.decode("utf-8", errors="replace")


def _is_workflow_schema_instance(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    ident = doc.get("id")
    tools = doc.get("tools")
    stop = doc.get("stop_rule")
    stages = doc.get("stages")
    if not (isinstance(ident, str) and ident.strip()):
        return False
    if not (isinstance(tools, list) and all(isinstance(t, str) and t for t in tools)):
        return False
    if not isinstance(stop, dict) or not stop:
        return False
    if not (isinstance(stages, list) and len(stages) >= 1):
        return False
    return True


def _partial_workflow_json(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    keys = set(doc)
    hints = {"stages", "stop_rule", "subworkflows", "tools", "jobs"}
    return bool(keys & hints) and not _is_workflow_schema_instance(doc)


def _yaml_gha(text: str) -> str | None:
    has_on = bool(_ON_LINE.search(text)) or bool(_WORKFLOW_DISPATCH.search(text))
    has_jobs = bool(_JOBS_LINE.search(text))
    if has_on and has_jobs:
        return WORKFLOW
    if has_on or has_jobs:
        return AMBIGUOUS
    return None


def classify(path: str, blob: bytes) -> str:
    rel = _posix(path)
    lower = rel.lower()
    text = _decode(blob)
    stripped = text.strip()

    if not stripped:
        if "workflow" in lower or ".github/workflows/" in lower:
            return AMBIGUOUS
        return NON_WORKFLOW

    if lower.endswith((".yml", ".yaml")):
        gha = _yaml_gha(text)
        if gha is not None:
            return gha
        if ".github/workflows/" in lower or "workflow" in lower:
            return AMBIGUOUS
        return NON_WORKFLOW

    if lower.endswith(".json"):
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return AMBIGUOUS if "workflow" in lower else NON_WORKFLOW
        if _is_workflow_schema_instance(doc):
            return WORKFLOW
        if _partial_workflow_json(doc):
            return AMBIGUOUS
        if "workflow" in lower:
            return AMBIGUOUS
        return NON_WORKFLOW

    if lower.endswith("skill.md"):
        if _STAGE_SEQ.search(text) and _STOP_RULE.search(text):
            return WORKFLOW
        return AMBIGUOUS

    if lower.endswith((".py", ".js", ".mjs", ".sh")):
        if _STAGE_SEQ.search(text) and _STOP_RULE.search(text):
            return WORKFLOW
        if any(k in lower for k in ("workflow", "orchestrat", "pipeline")):
            return AMBIGUOUS
        return NON_WORKFLOW

    if any(k in lower for k in ("workflow", "orchestrat", "pipeline")):
        return AMBIGUOUS
    return NON_WORKFLOW


def is_candidate_path(path: str) -> bool:
    p = _posix(path).lower()
    if p.startswith(".github/workflows/") or "/workflows/" in p:
        return True
    if p.startswith("skills/") or p.startswith("scripts/"):
        return True
    if any(k in p for k in ("workflow", "orchestrat", "pipeline", "skill.md")):
        return True
    if p.startswith("tools/") and p.endswith(
        (".yml", ".yaml", ".json", ".py", ".js", ".mjs", ".sh")
    ):
        return True
    if p.endswith((".yml", ".yaml")):
        return True
    return False
