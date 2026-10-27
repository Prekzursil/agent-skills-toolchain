#!/usr/bin/env python3
"""IMP-0421 probe 2: detached invocation must raise at the API boundary.

Any attempt to background (``background=True``, ``--background`` on extra
argv, Windows DETACHED_PROCESS) raises DetachedInvocationError BEFORE a
child is spawned. The shipped ``_spawn`` uses ``subprocess.run`` (blocking)
and does not call ``Popen``.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER_SRC = REPO / "command-center" / "adapters" / "codex.py"
sys.path.insert(0, str(REPO / "command-center"))

from adapters.codex import (  # noqa: E402
    DetachedInvocationError,
    CodexAdapter,
    SpawnRecord,
    STATE_SUCCESS,
)

UNIT = {"id": "IMP-0421-probe", "timeout_seconds": 30}
PROMPT = "named-probe-2 detached-invocation; body must stay off argv"


class SpawnSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, timeout) -> SpawnRecord:
        self.calls.append(list(argv))
        out = argv[list(argv).index("--output-last-message") + 1]
        Path(out).write_text(json.dumps({"ok": True, "probe": "detached"}) + "\n", encoding="utf-8")
        return SpawnRecord(argv=list(argv), exit_code=0, stdout="", stderr="")


def _must_raise(label: str, fn) -> str:
    try:
        fn()
    except DetachedInvocationError as exc:
        return str(exc)
    raise AssertionError(f"{label} did not raise DetachedInvocationError")


def _spawn_uses_run(tree: ast.AST) -> dict:
    spawn_fn = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CodexAdapter":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_spawn":
                    spawn_fn = item
    if spawn_fn is None:
        return {"found": False, "uses_run": False, "uses_popen": False, "shell_true": False}
    uses_run = False
    uses_popen = False
    shell_true = False
    for node in ast.walk(spawn_fn):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name == "run":
                uses_run = True
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        shell_true = True
            if name == "Popen":
                uses_popen = True
    return {
        "found": True,
        "uses_run": uses_run,
        "uses_popen": uses_popen,
        "shell_true": shell_true,
    }


def main() -> int:
    spy = SpawnSpy()
    adapter = CodexAdapter(codex_bin=["codex"], spawn=spy)

    msg_bg = _must_raise(
        "background=True",
        lambda: adapter.dispatch(UNIT, PROMPT, background=True),
    )
    msg_det = _must_raise(
        "detached=True",
        lambda: adapter.dispatch(UNIT, PROMPT, detached=True),
    )
    msg_flag = _must_raise(
        "extra --background",
        lambda: adapter.dispatch(UNIT, PROMPT, extra_argv=["--background"]),
    )
    msg_win = _must_raise(
        "DETACHED_PROCESS",
        lambda: adapter.dispatch(UNIT, PROMPT, creationflags=0x00000008),
    )
    calls_after_refused = len(spy.calls)

    with tempfile.TemporaryDirectory(prefix="imp0421-p2-") as td:
        good = adapter.dispatch(UNIT, PROMPT, work_dir=Path(td))

    src = ADAPTER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    spawn_ast = _spawn_uses_run(tree)
    popen_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if name == "Popen":
                popen_calls += 1
    popen_in_module = popen_calls > 0

    argv = good["invocation"]["argv"]
    print(
        json.dumps(
            {
                "spy_calls_after_refused": calls_after_refused,
                "good_state": good.get("state"),
                "argv_has_background": "--background" in argv,
                "prompt_body_on_argv": good["invocation"]["prompt_body_on_argv"],
                "prompt_file_on_argv": good["invocation"]["prompt_file_on_argv"],
                "ignore_user_config": good["invocation"]["ignore_user_config"],
                "spawn_ast": spawn_ast,
                "popen_in_module": popen_in_module,
                "background_error": msg_bg,
            },
            sort_keys=True,
        )
    )

    checks = [
        ("background_raises", "unreachable by the fan-in barrier" in msg_bg or "refused" in msg_bg.lower()),
        ("detached_raises", "refused" in msg_det.lower()),
        ("flag_raises", "structurally unable" in msg_flag or "refused" in msg_flag.lower()),
        ("win_detached_raises", "DETACHED_PROCESS" in msg_win or "refused" in msg_win.lower()),
        ("no_spawn_on_refuse", calls_after_refused == 0),
        ("good_success", good.get("state") == STATE_SUCCESS),
        ("no_background_on_argv", "--background" not in argv),
        ("prompt_file_on_argv", good["invocation"]["prompt_file_on_argv"] is True),
        ("prompt_body_not_on_argv", good["invocation"]["prompt_body_on_argv"] is False),
        ("ignore_user_config", good["invocation"]["ignore_user_config"] is True),
        ("output_flag_present", "--output-last-message" in argv),
        ("spawn_found", spawn_ast["found"] is True),
        ("spawn_uses_run", spawn_ast["uses_run"] is True),
        ("spawn_no_popen", spawn_ast["uses_popen"] is False),
        ("spawn_no_shell", spawn_ast["shell_true"] is False),
        ("module_no_popen", popen_in_module is False),
        ("spy_ran_once_on_good", len(spy.calls) == 1),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{name}={ok}")
    if failed:
        print("FAILED:IMP-0421-probe2 " + ",".join(failed))
        return 1
    print("SUCCESS:IMP-0421-probe2 detached invocation raises at API boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
