"""IMP-0172 fixtures: the 8-pair antisymmetry matrix plus the both-sides-unique
pair (persisted as JSON fixtures for the probes)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _base(name="baseline"):
    return {
        "name": name,
        "stages": [
            {"name": "implement", "roles": ["coder"], "tools": ["Edit", "Bash"], "gates": []},
            {"name": "validate", "roles": ["tester"], "tools": ["Bash"], "gates": ["tests-pass"]},
        ],
        "roles": ["coder", "tester"],
        "gates": ["tests-pass"],
        "edges": [["implement", "validate"]],
    }


def pairs() -> list:
    a = _base()
    identical_b = _base()

    rename_b = _base()
    rename_b["stages"][1] = dict(rename_b["stages"][1], name="verify")

    both_left = _base()
    both_left["stages"].append(
        {"name": "adversarial-review", "roles": ["refuter"], "tools": ["Grep"], "gates": ["no-open-p0"]})
    both_left["edges"].append(["adversarial-review", "validate"])

    both_right = _base()
    both_right["stages"].append(
        {"name": "publish-pr", "roles": ["publisher"], "tools": ["Bash"], "gates": ["ci-green"]})
    both_right["edges"].append(["publish-pr", "validate"])

    left_ahead_a = _base()
    left_ahead_a["stages"].append(
        {"name": "record-ledger", "roles": ["scribe"], "tools": ["Bash"], "gates": []})

    right_ahead_b = _base()
    right_ahead_b["stages"].append(
        {"name": "emit-summary", "roles": ["emitter"], "tools": ["Write"], "gates": []})

    gate_a = _base()
    gate_a["stages"][1]["gates"] = ["tests-pass", "coverage-100"]

    role_a = _base()
    role_a["stages"][0]["roles"] = ["coder", "reviewer"]

    tool_a = _base()
    tool_a["stages"][0]["tools"] = ["Edit", "Bash", "Grep"]

    return [
        ("identical", _base(), identical_b),
        ("rename-only", _base(), rename_b),
        ("both-sides-unique", both_left, both_right),
        ("left-ahead", left_ahead_a, _base()),
        ("right-ahead", _base(), right_ahead_b),
        ("gate-change", gate_a, _base()),
        ("role-change", role_a, _base()),
        ("tool-change", tool_a, _base()),
    ]


def write_both_sides_fixtures() -> tuple:
    pl = HERE / "fixtures" / "both-sides-left.json"
    pr = HERE / "fixtures" / "both-sides-right.json"
    for p, d in [(pl, pairs()[2][1]), (pr, pairs()[2][2])]:
        p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")
    return pl, pr


def load_both_sides() -> tuple:
    pl, pr = write_both_sides_fixtures()
    return json.loads(pl.read_text(encoding="utf-8")), json.loads(pr.read_text(encoding="utf-8"))
