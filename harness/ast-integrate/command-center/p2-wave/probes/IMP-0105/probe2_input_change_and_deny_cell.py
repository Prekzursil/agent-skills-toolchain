#!/usr/bin/env python3
"""Probe 2: one-input change moves score+line; deny names the policy cell.

Both-states in one process: ALLOW (pkg.alpha) and DENY (pkg.delta). A deny
that only says 'denied' without the (signature, trust, advisory) triple fails.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import explain  # noqa: E402


def main() -> int:
    corpus = explain.demo_corpus()
    before = explain.why(
        package_id="pkg.alpha",
        corpus=corpus,
        query="json lint",
        subject="search",
    )
    lint_before = next(
        row for row in before["ranking"]["components"] if row["term"] == "lint"
    )
    conf_before = next(
        row
        for row in before["quality"]["components"]
        if row["id"] == "conformance_pass_rate"
    )
    others_before = {
        row["id"]: int(row["value"])
        for row in before["quality"]["components"]
        if row["id"] != "conformance_pass_rate"
    }

    mutated = copy.deepcopy(corpus)
    alpha = next(pkg for pkg in mutated if pkg["id"] == "pkg.alpha")
    alpha["name"] = "alpha-json-helper"
    alpha["description"] = "json documents in a workspace"
    alpha["tags"] = ["json"]
    alpha["skills"] = ["json.help"]
    alpha["conformance_pass_rate"] = 100
    after = explain.why(
        package_id="pkg.alpha",
        corpus=mutated,
        query="json lint",
        subject="search",
    )
    lint_after = next(
        row for row in after["ranking"]["components"] if row["term"] == "lint"
    )
    conf_after = next(
        row
        for row in after["quality"]["components"]
        if row["id"] == "conformance_pass_rate"
    )
    others_after = {
        row["id"]: int(row["value"])
        for row in after["quality"]["components"]
        if row["id"] != "conformance_pass_rate"
    }

    ranking_moved = (
        int(lint_after["value"]) != int(lint_before["value"])
        and int(after["ranking"]["score_milli"]) != int(before["ranking"]["score_milli"])
        and int(lint_after["value"]) == 0
    )
    quality_moved = (
        int(conf_after["value"]) != int(conf_before["value"])
        and int(after["quality"]["score_milli"]) != int(before["quality"]["score_milli"])
        and others_after == others_before
    )

    denied = explain.why(package_id="pkg.delta", corpus=corpus, subject="install")
    allowed = explain.why(package_id="pkg.alpha", corpus=corpus, subject="install")
    deny_cell = denied["policy"]["cell_id"]
    allow_cell = allowed["policy"]["cell_id"]
    deny_ok = (
        denied["policy"]["verdict"] == "DENY"
        and denied["policy"]["specified_cell"] is True
        and deny_cell == "signature=invalid|trust=LOW|advisory=critical"
        and "policy cell" in denied["policy"]["message"]
        and deny_cell in denied["policy"]["message"]
        and deny_cell in "\n".join(denied["human_lines"])
    )
    allow_ok = (
        allowed["policy"]["verdict"] == "ALLOW"
        and allow_cell == "signature=valid|trust=HIGH|advisory=clean"
        and allow_cell != deny_cell
    )
    generic_only = (
        "deny" in denied["policy"]["message"].lower()
        and "signature=" not in denied["policy"]["message"]
    )

    payload = {
        "allow_cell": allow_cell,
        "allow_ok": allow_ok,
        "deny_cell": deny_cell,
        "deny_ok": deny_ok,
        "generic_only_message": generic_only,
        "lint_after": lint_after["value"],
        "lint_before": lint_before["value"],
        "pass": ranking_moved and quality_moved and deny_ok and allow_ok and not generic_only,
        "probe": "probe2-input-change-and-deny-cell",
        "quality_moved_one_component": quality_moved,
        "ranking_moved_lint_and_total": ranking_moved,
        "unit_id": "IMP-0105",
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0105-probe2 input-change or deny-cell")
        return 1
    print(
        "SUCCESS:IMP-0105-probe2 lint+conformance lines moved; "
        f"deny cell={deny_cell} allow cell={allow_cell}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
