#!/usr/bin/env python3
"""TST-0223 probe 2: the executor refuses the deepest privileged call; no leaked file.

A nested subworkflow whose deepest Task attempts Write while the parent bag
lacks it is refused with tool-permission-denied (spawn_count=0, no file), an
unprivileged task in the same run writes fine (both-states control), and
re-entry (a second execute() of the same tree) cannot widen either.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.spec import ToolPermissionError  # noqa: E402
from agentspec.subworkflow_executor import ExecuteOpts, Subworkflow, Task, Workflow, execute  # noqa: E402

ROOT = HERE / "fixtures" / "artifacts"


def build_tree() -> tuple[Workflow, dict[str, Workflow]]:
    """parent(no Write) -> child(declares Write) -> deepest task attempting Write."""
    deepest = Workflow(
        id="wf-deepest",
        nodes=(
            Task(id="normal-write", write_name="out.txt", write_from_param="label", attempted_tool=""),
            Task(id="escalation-write", write_name="leak.txt", write_from_param="label", attempted_tool="Write"),
        ),
    )
    child = Workflow(id="wf-child", nodes=(Subworkflow(id="sub-deep", workflow_ref="wf-deepest", tool_permissions=frozenset({"Read", "Write"})),))
    parent = Workflow(id="wf-parent", nodes=(Subworkflow(id="sub-child", workflow_ref="wf-child", tool_permissions=frozenset({"Read", "Write"})),))
    return parent, {"wf-parent": parent, "wf-child": child, "wf-deepest": deepest}


def tree_state(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


def main() -> int:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    parent, registry = build_tree()
    parent_perms = frozenset({"Read", "Grep", "Bash"})

    leaked = False
    refused = False
    code = None
    try:
        execute(parent, registry, ROOT, params={"label": "attempt-1"}, parent_perms=parent_perms, opts=ExecuteOpts())
    except ToolPermissionError as exc:
        refused = True
        code = getattr(exc, "code", None)

    # the first (permitted) task ran before the refusal; the escalation file must not exist
    files_after = tree_state(ROOT)
    leaked = any(p.endswith("leak.txt") for p in files_after)

    # both-states control: drop the escalation task, the permitted task writes
    ok_root = ROOT.parent / "artifacts-ok"
    if ok_root.exists():
        shutil.rmtree(ok_root)
    ok_wf = Workflow(
        id="wf-ok",
        nodes=(Task(id="normal-write", write_name="out.txt", write_from_param="label", attempted_tool=""),),
    )
    execute(ok_wf, {"wf-ok": ok_wf}, ok_root, params={"label": "control"}, parent_perms=parent_perms, opts=ExecuteOpts())
    control_wrote = any(q.name == "out.txt" for q in ok_root.rglob("*") if q.is_file())

    # re-entry: a second execute() of the SAME tree cannot widen either
    root2 = ROOT.parent / "artifacts-reentry"
    if root2.exists():
        shutil.rmtree(root2)
    refused2 = False
    try:
        execute(parent, registry, root2, params={"label": "attempt-2"}, parent_perms=parent_perms, opts=ExecuteOpts())
    except ToolPermissionError:
        refused2 = True
    reentry_leak = any(p.endswith("leak.txt") for p in tree_state(root2))

    checks = {
        "deepest_write_refused": refused is True and code == "tool-permission-denied",
        "no_leaked_file_after_refusal": leaked is False,
        "own_perm_task_writes_both_states": control_wrote is True,
        "reentry_cannot_widen": refused2 is True and reentry_leak is False,
    }
    out = {
        "probe": "probe2_executor_deep_refusal",
        "unit": "TST-0223",
        "refusal_code": code,
        "files_after_refusal": files_after,
        "control_wrote": control_wrote,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_executor_deep_refusal.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(ROOT.parent, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
