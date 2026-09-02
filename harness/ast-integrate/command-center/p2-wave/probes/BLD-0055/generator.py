"""Synthetic catalog generator that the live cc-validate gate can accept.

A corpus the gate rejects measures nothing. Items use the register id
shape tools/command-center/validate.py requires, are acyclic, and carry
terminal disposition evidence so REACH-3/5 stay silent on the good state.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

Shape = Literal["chain", "sparse"]

DEFAULTS: dict[str, Any] = {
    "assignment": {
        "model": "opus",
        "vendor": "anthropic",
        "role": "implementer",
        "basis": "BLD-0055 synthetic generator",
    },
    "tool_permissions": ["Read", "Bash"],
    "execution_substrate": "worktree-isolated",
    "timeout_seconds": 1800,
    "output_schema": "command-center/schema/receipt.schema.json",
    "evidence_requirement": (
        "two mechanically independent signals, each anchored to a file:line"
    ),
    "reviewer_requirement": "one independent reviewer",
    "retry_policy": "two strikes then pivot",
    "failure_classification": ["overclaim", "resource-exhaustion"],
    "tests_required": ["both-states control"],
    "owner_approval_required": False,
}


def item_id(i: int) -> str:
    return f"T-{i}"


def title_for(i: int, *, plant_near_dup: bool) -> str:
    if plant_near_dup and i == 2:
        return "alpha beta gamma delta epsilon zeta eta theta unique2"
    if plant_near_dup and i == 1:
        return "alpha beta gamma delta epsilon zeta eta theta unique1"
    return f"synthetic settled unit {i} tokenu{i}"


def register_markdown(ids: list[str]) -> str:
    lines = ["## 4. SETTLED", ""]
    for iid in ids:
        lines.append(f"| {iid} | synthetic {iid} |")
    return "\n".join(lines) + "\n"


def build_items(n: int, shape: Shape, *, plant_near_dup: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for i in range(1, n + 1):
        iid = item_id(i)
        deps: list[str] = []
        if shape == "chain" and i > 1:
            deps = [item_id(i - 1)]
        elif shape == "sparse" and i > 3 and i % 4 == 0:
            deps = [item_id(i - 3)]
        items.append(
            {
                "id": iid,
                "title": title_for(i, plant_near_dup=plant_near_dup),
                "phase": "13",
                "target": f"scale census item {i}",
                "inputs": ["synthetic-generator"],
                "dependencies": deps,
                "program": "HARNESS",
                "section": "SETTLED",
                "status": "CLOSED",
                "disposition": "DONE-VERIFIED",
                "disposition_evidence": (
                    "synthetic closed item for BLD-0055 scale census; "
                    "terminal disposition is generator-authored"
                ),
                "effort": "S",
                "evidence": "BLD-0055 generator",
                "sources": ["BLD-0055"],
                "owner_gate": [],
                "security_class": "none",
                "next_smallest_action": "none",
                "defer": None,
                "history": [],
                "output_path": f"command-center/receipts/{iid}.json",
                "completion_sentinel": f"SUCCESS:{iid}",
            }
        )
    return items


def make_catalog(
    n: int,
    *,
    shape: Shape = "chain",
    plant_near_dup: bool = True,
    register_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    if n < 1:
        raise ValueError("n must be >= 1")
    items = build_items(n, shape, plant_near_dup=plant_near_dup)
    ids = [item_id(i) for i in range(1, n + 1)]
    text = register_markdown(ids)
    digest = hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    catalog: dict[str, Any] = {
        "schema_version": 1,
        "defaults": DEFAULTS,
        "owner_questions": [],
        "provenance": {
            "register": str(register_path) if register_path else "SYNTHETIC",
            "register_sha256": digest,
        },
        "items": items,
    }
    return catalog, text
