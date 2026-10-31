"""Monotone narrowing: child ⊆ parent, union mutant goes red, executor fixture."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agentspec.permission_bound import (
    N_TREES,
    SEED,
    narrow,
    run_property_corpus,
    union_widen,
)
from agentspec.spec import ToolPermissionError, freeze_tool_permissions
from agentspec.subworkflow_executor import Subworkflow, Task, Workflow, execute


def test_narrow_is_intersection() -> None:
    got = narrow({"Read", "Write"}, {"Read", "Grep"})
    assert got == frozenset({"Read"})
    src_parent = freeze_tool_permissions({"Read", "Grep", "Bash"})
    declared = freeze_tool_permissions({"Read", "Grep", "Bash", "Write"})
    assert narrow(src_parent, declared) == src_parent
    assert union_widen(src_parent, declared) == declared


def test_property_corpus_5000_is_green() -> None:
    live = run_property_corpus(n_trees=N_TREES, seed=SEED)
    assert live["n_trees"] >= 5000
    assert live["pass"] is True
    assert live["violations"] == 0
    assert live["widening_attempts"] >= 1
    assert live["widening_calls_denied"] >= 1
    assert live["widening_calls_allowed"] == 0


def test_union_mutant_goes_red() -> None:
    mutated = run_property_corpus(n_trees=400, seed=SEED, narrow_fn=union_widen)
    assert mutated["violations"] >= 1
    assert mutated["pass"] is not True
    assert mutated["widening_calls_allowed"] >= 1


def test_executor_denies_widening_write(tmp_path: Path | None = None) -> None:
    inner_write = Workflow(
        id="inner-write",
        nodes=(
            Task(
                id="deep",
                budget=1,
                write_name="secret.txt",
                write_from_param="label",
                attempted_tool="Write",
            ),
        ),
    )
    outer_write = Workflow(
        id="outer-write",
        nodes=(
            Subworkflow(
                id="child",
                workflow_ref="inner-write",
                id_namespace="nest.child",
                param_bindings={"label": "PWN"},
                tool_permissions=frozenset({"Read", "Grep", "Bash", "Write"}),
            ),
        ),
    )
    parent = frozenset({"Read", "Grep", "Bash"})
    root = tmp_path if tmp_path is not None else Path(tempfile.mkdtemp(prefix="tst0223-test-"))
    deny = root / "deny"
    raised = False
    try:
        execute(
            outer_write,
            {"inner-write": inner_write},
            deny,
            params={"label": "PWN"},
            parent_perms=parent,
        )
    except ToolPermissionError as exc:
        raised = True
        assert exc.code == "tool-permission-denied"
    assert raised
    assert not list(deny.rglob("secret.txt"))
