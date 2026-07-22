#!/usr/bin/env python
"""Regression tests for the semantic-router benchmark contract and isolation."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
EVAL_PY = HERE / "eval.py"
ROUTE_PY = HERE / "route.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def eval_module():
    return _load(EVAL_PY, "semantic_router_eval_test")


def _perfect_results(cases):
    results = []
    for _prompt, skills, mcps, _mismatch in cases:
        results.append((set(skills[:1]), set(mcps[:1])))
    return results


def test_json_mode_emits_the_contract_consumed_by_bench(
    eval_module, monkeypatch, capsys
):
    # Known-broken: --json printed the human table, so bench parsed no HYBRID result.
    perfect = _perfect_results(eval_module.CASES)
    monkeypatch.setattr(eval_module, "run", lambda _route, _tag, _env: perfect)

    assert eval_module.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {"lexical", "semantic", "hybrid"}
    hybrid = payload["hybrid"]
    assert (
        hybrid["skill_total"],
        hybrid["mcp_total"],
        hybrid["neg_total"],
    ) == (14, 5, 2)
    assert hybrid["skill_total"] + hybrid["mcp_total"] + hybrid["neg_total"] == 21
    assert len(hybrid["case_outcomes"]) == len(eval_module.CASES)


def test_eval_and_router_resolve_the_lexical_peer_from_their_tree(eval_module):
    # Known-broken: both modules required a deployed $HOME/.claude/hooks peer in CI.
    route_module = _load(ROUTE_PY, "semantic_router_route_path_test")
    expected = HERE.parent / "skill-router"

    assert Path(eval_module.OLD) == expected / "route.py"
    assert route_module.LEXICAL_DIR == expected


def test_every_acceptable_cluster_resolves_to_an_authoritative_unit(eval_module):
    # Known-broken: the Binary Ninja case named stale MCP server "binary-ninja".
    skill_names = {
        path.parent.name
        for path in (REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md")
    }
    metadata = json.loads((HERE / "index" / "meta.json").read_text(encoding="utf-8"))
    mcp_names = {row["name"] for row in metadata["rows"] if row.get("kind") == "mcp"}

    for case_id, (_prompt, skills, mcps, _mismatch) in enumerate(eval_module.CASES):
        if skills:
            assert skill_names.intersection(skills), (
                f"case {case_id} has no authoritative acceptable skill: {skills}"
            )
        if mcps:
            assert mcp_names.intersection(mcps), (
                f"case {case_id} has no indexed acceptable MCP: {mcps}"
            )


def test_benchmark_mode_does_not_read_or_write_router_feedback(monkeypatch, capsys):
    # Known-broken: eval read success boosts and consulted/appended calibrated-silence state.
    route_module = _load(ROUTE_PY, "semantic_router_route_isolation_test")
    success = importlib.import_module("success")
    monkeypatch.setattr(route_module, "BENCH", True, raising=False)
    monkeypatch.setattr(route_module, "PURE", True)
    monkeypatch.setattr(
        success,
        "load_success",
        lambda: pytest.fail("benchmark read mutable success history"),
    )

    def semantic_without_history(_prompt, history):
        assert history == {}
        return []

    monkeypatch.setattr(route_module, "_semantic", semantic_without_history)
    monkeypatch.setattr(route_module, "_all_names", set)
    route_module.assemble("a benchmark prompt long enough to route", record=False)

    buckets = {
        "skill": ["/systematic-debugging"],
        "mcp": [],
        "agent": [],
        "command": [],
        "memory": [],
    }
    monkeypatch.setattr(
        route_module,
        "assemble",
        lambda *_args, **_kwargs: (buckets, ["skills: /systematic-debugging"], []),
    )
    monkeypatch.setattr(route_module, "_first_seen", lambda *_args: True)
    monkeypatch.setattr(
        route_module,
        "_cs_allow",
        lambda *_args: pytest.fail("benchmark consulted calibrated-silence state"),
    )
    monkeypatch.setattr(
        route_module,
        "_cs_record",
        lambda *_args: pytest.fail("benchmark wrote calibrated-silence state"),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "prompt": "the app crashes when I click the delete button",
                    "session_id": "eval-isolation",
                }
            )
        ),
    )

    assert route_module.main() == 0
    assert "systematic-debugging" in capsys.readouterr().out
