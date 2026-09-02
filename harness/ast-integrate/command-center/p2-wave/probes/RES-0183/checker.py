#!/usr/bin/env python3
"""Check a draft research recommendation against extracted owner constraints."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from extract import build_constraints, negation_before  # noqa: E402


def normalize_draft(draft: Any) -> dict:
    if isinstance(draft, str):
        return {
            "id": "anon",
            "mode": "recommend",
            "text": draft,
            "proposed_release_mode": None,
        }
    if not isinstance(draft, dict):
        raise TypeError(type(draft))
    text = str(draft.get("text") or draft.get("recommendation") or "")
    return {
        "id": str(draft.get("id") or "anon"),
        "mode": str(draft.get("mode") or "recommend").lower(),
        "text": text,
        "proposed_release_mode": draft.get("proposed_release_mode"),
    }


def check_draft(
    draft: Any, constraints: dict[str, Any] | None = None
) -> dict[str, Any]:
    blob = constraints or build_constraints()
    rec = normalize_draft(draft)
    violations: list[dict] = []
    if rec["mode"] in {"mention", "quote", "describe-rejected"}:
        return {
            "draft_id": rec["id"],
            "mode": rec["mode"],
            "compliant": True,
            "violations": [],
            "note": "mention/quote of a rejected alternative is not a recommendation",
        }
    binding = [
        c
        for c in (blob.get("stated") or [])
        if c.get("binding") and c.get("kind") == "STATED"
    ]
    mode = rec.get("proposed_release_mode")
    text = rec["text"]
    for c in binding:
        if mode:
            forbidden_modes = c.get("forbidden_release_modes") or []
            if str(mode).upper() in {m.upper() for m in forbidden_modes}:
                violations.append(
                    {
                        "constraint_id": c["id"],
                        "rule_id": "proposed_release_mode",
                        "detail": f"proposed_release_mode={mode} is forbidden by {c['id']}",
                    }
                )
        for rule in c.get("forbidden_patterns") or []:
            regex = re.compile(rule["regex"])
            for m in regex.finditer(text):
                if negation_before(text, m.start()):
                    continue
                violations.append(
                    {
                        "constraint_id": c["id"],
                        "rule_id": rule["id"],
                        "detail": m.group(0),
                    }
                )
    return {
        "draft_id": rec["id"],
        "mode": rec["mode"],
        "compliant": not violations,
        "violations": violations,
    }


def load_drafts() -> dict:
    path = HERE / "fixtures" / "drafts.json"
    return json.loads(path.read_text(encoding="utf-8"))
