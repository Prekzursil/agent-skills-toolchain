#!/usr/bin/env python3
"""Typed workflow fixtures for IMP-0172.

Identifiers are decoys: the differ must align on mechanism kind, not names.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def _base() -> dict[str, Any]:
    return {
        "id": "wf.base",
        "stages": [
            {
                "id": "discover",
                "kind": "static-scan",
                "role": "analyst",
                "gate": {"pred": "files_present", "args": ["repo"]},
                "tools": ["Read", "Grep"],
                "inputs": ["repo"],
                "outputs": ["candidates.json"],
            },
            {
                "id": "record",
                "kind": "write-config",
                "role": "operator",
                "gate": {"pred": "candidates_nonempty"},
                "tools": ["Write"],
                "inputs": ["candidates.json"],
                "outputs": ["blueprint.json"],
            },
        ],
        "edges": [["discover", "record"]],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    }


def rename_ids(wf: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    out = copy.deepcopy(wf)
    out["id"] = mapping.get(out.get("id") or "", out.get("id") or "") + ".renamed"
    for s in out["stages"]:
        if s["id"] in mapping:
            s["id"] = mapping[s["id"]]
    out["edges"] = [[mapping.get(a, a), mapping.get(b, b)] for a, b in out["edges"]]
    return out


def with_stage(wf: dict[str, Any], stage: dict[str, Any], after_id: str | None = None) -> dict[str, Any]:
    out = copy.deepcopy(wf)
    ids = [s["id"] for s in out["stages"]]
    if after_id and after_id in ids:
        idx = ids.index(after_id) + 1
        out["stages"].insert(idx, copy.deepcopy(stage))
        out["edges"].append([after_id, stage["id"]])
    else:
        out["stages"].append(copy.deepcopy(stage))
    return out


REVIEW = {
    "id": "review",
    "kind": "adversarial-review",
    "role": "critic",
    "gate": {"pred": "needs_decision"},
    "tools": ["Read"],
    "inputs": ["blueprint.json"],
    "outputs": ["decision.json"],
}

PUBLISH = {
    "id": "publish",
    "kind": "publish-pr",
    "role": "releaser",
    "gate": {"pred": "tests_green"},
    "tools": ["Bash"],
    "inputs": ["blueprint.json"],
    "outputs": ["pr-url"],
}


def both_sides_left() -> dict[str, Any]:
    wf = with_stage(_base(), REVIEW, after_id="record")
    wf["id"] = "wf.both-left"
    return wf


def both_sides_right() -> dict[str, Any]:
    wf = with_stage(_base(), PUBLISH, after_id="record")
    wf["id"] = "wf.both-right"
    return wf


def left_ahead() -> tuple[dict[str, Any], dict[str, Any]]:
    a = both_sides_left()
    a["id"] = "wf.left-ahead"
    b = _base()
    b["id"] = "wf.base-right"
    return a, b


def right_ahead() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _base()
    a["id"] = "wf.base-left"
    b = both_sides_right()
    b["id"] = "wf.right-ahead"
    return a, b


def gate_change() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _base()
    b = _base()
    b["id"] = "wf.gate-mut"
    b["stages"][0]["gate"] = {"pred": "bytes_nonzero", "args": ["repo"]}
    return a, b


def role_change() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _base()
    b = _base()
    b["id"] = "wf.role-mut"
    b["stages"][0]["role"] = "importer"
    return a, b


def tool_change() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _base()
    b = _base()
    b["id"] = "wf.tool-mut"
    b["stages"][0]["tools"] = ["Read", "Glob"]
    return a, b


def rename_only() -> tuple[dict[str, Any], dict[str, Any]]:
    a = _base()
    b = rename_ids(_base(), {"discover": "scan", "record": "persist"})
    b["id"] = "wf.renamed"
    return a, b


def identical() -> tuple[dict[str, Any], dict[str, Any]]:
    return _base(), copy.deepcopy(_base())


def fixture_matrix() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Named pairs for the antisymmetry matrix (catalog tests_required[1])."""
    la, lb = left_ahead()
    ra, rb = right_ahead()
    ga, gb = gate_change()
    oa, ob = role_change()
    ta, tb = tool_change()
    na, nb = rename_only()
    ia, ib = identical()
    return [
        ("identical", ia, ib),
        ("rename-only", na, nb),
        ("both-sides-unique", both_sides_left(), both_sides_right()),
        ("left-ahead", la, lb),
        ("right-ahead", ra, rb),
        ("gate-change", ga, gb),
        ("role-change", oa, ob),
        ("tool-change", ta, tb),
    ]


def write_json_fixtures() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    files = {
        "base.json": _base(),
        "both-sides-left.json": both_sides_left(),
        "both-sides-right.json": both_sides_right(),
    }
    la, lb = left_ahead()
    files["left-ahead.json"] = la
    files["left-ahead-right.json"] = lb
    ra, rb = right_ahead()
    files["right-ahead-left.json"] = ra
    files["right-ahead.json"] = rb
    for name, doc in files.items():
        (FIX / name).write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    write_json_fixtures()
    print(f"wrote {len(list(FIX.glob('*.json')))} fixtures under {FIX}")
