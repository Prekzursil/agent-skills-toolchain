"""Shared TST-0223 helpers: executor fixture and AST mutation of narrow()."""
from __future__ import annotations

import importlib.util
import inspect
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Any, Iterable


def _stdlib_ast():
    """Load CPython ast even when PYTHONPATH shadows it with tools/ast.py."""
    cached = sys.modules.get("ast")
    if cached is not None and hasattr(cached, "parse") and hasattr(cached, "BitAnd"):
        return cached
    stdlib = sysconfig.get_path("stdlib")
    path = Path(stdlib) / "ast.py"
    if not path.is_file():
        path = Path(stdlib) / "ast" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_stdlib_ast_tst0223", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"stdlib ast missing at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ast = _stdlib_ast()

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

_spec_root = str(C.SPEC_ROOT)
if _spec_root in sys.path:
    sys.path.remove(_spec_root)
sys.path.insert(0, _spec_root)
_mod = sys.modules.get("agentspec")
_mod_file = str(getattr(_mod, "__file__", "") or "").replace("\\", "/")
if _mod is not None and _mod_file.endswith("tools/agentspec/__init__.py"):
    for _key in [k for k in list(sys.modules) if k == "agentspec" or k.startswith("agentspec.")]:
        del sys.modules[_key]

from agentspec.permission_bound import narrow  # noqa: E402
from agentspec.spec import ToolPermissionError, freeze_tool_permissions  # noqa: E402
from agentspec.subworkflow_executor import (  # noqa: E402
    Subworkflow,
    Task,
    Workflow,
    execute,
)

BOUND_PY = C.SPEC_ROOT / "agentspec" / "permission_bound.py"


def catalog_inputs() -> list[dict[str, Any]]:
    rows = []
    for rel in C.NAMED_INPUTS:
        path = C.REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def run_executor_fixture() -> dict[str, Any]:
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
    inner_read = Workflow(
        id="inner-read",
        nodes=(
            Task(
                id="deep",
                budget=1,
                write_name="ok.txt",
                write_from_param="label",
                attempted_tool="Read",
            ),
        ),
    )
    outer_read = Workflow(
        id="outer-read",
        nodes=(
            Subworkflow(
                id="child",
                workflow_ref="inner-read",
                id_namespace="nest.ok",
                param_bindings={"label": "OK"},
                tool_permissions=frozenset({"Read"}),
            ),
        ),
    )
    parent = frozenset({"Read", "Grep", "Bash"})
    with tempfile.TemporaryDirectory(prefix="tst0223-") as td:
        root = Path(td)
        denied = False
        code = None
        try:
            execute(
                outer_write,
                {"inner-write": inner_write},
                root / "deny",
                params={"label": "PWN"},
                parent_perms=parent,
            )
        except ToolPermissionError as exc:
            denied = True
            code = exc.code
        leaked = list((root / "deny").rglob("secret.txt"))
        result = execute(
            outer_read,
            {"inner-read": inner_read},
            root / "ok",
            params={"label": "OK"},
            parent_perms=parent,
        )
        ok_files = list((root / "ok").rglob("ok.txt"))
        depths = [
            {
                "id": rid,
                "kind": rec.get("kind"),
                "effective": rec.get("effective_permissions"),
            }
            for rid, rec in result.receipts.items()
        ]
        return {
            "denied_write": denied,
            "deny_code": code,
            "leaked_secret": bool(leaked),
            "allowed_read": bool(ok_files),
            "ok_files": len(ok_files),
            "depths": depths,
            "parent_perms": sorted(parent),
        }


def mutate_narrow_bitand_to_bitor():
    """AST-rewrite live narrow(): BitAnd -> BitOr. Does not write the file."""
    tree = ast.parse(inspect.getsource(narrow))
    found = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
            node.op = ast.BitOr()
            found += 1
    if found != 1:
        raise AssertionError(f"expected one BitAnd in narrow(), found {found}")
    ns = {
        "freeze_tool_permissions": freeze_tool_permissions,
        "Iterable": Iterable,
        "frozenset": frozenset,
    }
    exec(compile(ast.fix_missing_locations(tree), "<TST-0223-mutant-narrow>", "exec"), ns)
    mutant = ns.get("narrow")
    if mutant is None:
        raise AssertionError("mutant narrow() missing after exec")
    return mutant


def live_narrow_is_intersection() -> bool:
    src = inspect.getsource(narrow)
    after = src.split("return", 1)[-1]
    return " & " in src and "|" not in after


def bound_source_snapshot() -> str:
    return BOUND_PY.read_text(encoding="utf-8")
