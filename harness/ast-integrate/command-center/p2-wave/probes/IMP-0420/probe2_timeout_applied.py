#!/usr/bin/env python3
"""IMP-0420 probe2: declared timeout is the one applied, not a catalog default.

Both-states: the same subagent body times out under a short declared deadline and
completes under a longer declared deadline. A missing timeout_seconds is refused
rather than filled with the catalog default (1800). Source walk confirms
resolve_timeout_seconds has no get-with-default / `or 1800` fallback.
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_adapter import ADAPTER_PATH, load_adapter  # noqa: E402


def _unit(uid: str, timeout) -> dict:
    body = {"id": uid, "tool_permissions": ["Read"]}
    if timeout is not Ellipsis:
        body["timeout_seconds"] = timeout
    return body


def _sleeper(seconds: float):
    def _run(tools):
        time.sleep(seconds)
        return tools.Read("seed.txt")

    return _run


def _timeout_fn_source_ok(src: str) -> tuple[bool, list[str]]:
    """Refuse get-with-default or a catalog-default constant inside resolve_timeout_seconds."""
    problems: list[str] = []
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_timeout_seconds":
            fn = node
            break
    if fn is None:
        return False, ["resolve_timeout_seconds missing"]
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and len(node.args) >= 2:
                key = node.args[0]
                if isinstance(key, ast.Constant) and key.value == "timeout_seconds":
                    problems.append("dict.get(timeout_seconds, default) fallback")
        if isinstance(node, ast.Constant) and node.value == 1800:
            problems.append("literal 1800 inside resolve_timeout_seconds")
        if isinstance(node, ast.Name) and node.id == "CATALOG_DEFAULT_TIMEOUT_SECONDS":
            problems.append("catalog default referenced inside resolve_timeout_seconds")
    return not problems, problems


def main() -> int:
    ca = load_adapter()
    adapter = ca.ClaudeAdapter()
    failures: list[str] = []
    src = ADAPTER_PATH.read_text(encoding="utf-8")
    ast_ok, ast_problems = _timeout_fn_source_ok(src)
    if not ast_ok:
        failures.extend(ast_problems)

    with tempfile.TemporaryDirectory(prefix="imp0420-p2-") as td:
        root = Path(td)
        (root / "seed.txt").write_text("ok\n", encoding="utf-8")

        short = adapter.dispatch(
            _unit("FIX-TIMEOUT-SHORT", 0.25),
            _sleeper(0.9),
            sandbox_root=root,
        )
        long = adapter.dispatch(
            _unit("FIX-TIMEOUT-LONG", 2.0),
            _sleeper(0.05),
            sandbox_root=root,
        )
        missing = adapter.dispatch(
            _unit("FIX-TIMEOUT-MISSING", Ellipsis),
            _sleeper(0.01),
            sandbox_root=root,
        )
        # Explicit catalog-default-shaped value must still be recorded as the UNIT value.
        eighteen = adapter.dispatch(
            _unit("FIX-TIMEOUT-DECLARED-1800", 1800),
            _sleeper(0.01),
            sandbox_root=root,
        )

    if short["state"] != "TIMEOUT":
        failures.append(
            f"short declared timeout did not fire (state={short['state']} "
            f"outcome={short['result']['outcome']}); default may have been applied"
        )
    if short.get("applied_timeout_seconds") != 0.25:
        failures.append(f"short applied_timeout_seconds={short.get('applied_timeout_seconds')}")
    if short.get("timeout_source") != "unit.timeout_seconds":
        failures.append(f"short timeout_source={short.get('timeout_source')}")
    if long["state"] != "SUCCESS":
        failures.append(f"long declared timeout rejected a fast subagent: {long['result']}")
    if long.get("applied_timeout_seconds") != 2.0:
        failures.append(f"long applied_timeout_seconds={long.get('applied_timeout_seconds')}")
    if missing["result"]["outcome"] != "timeout-not-declared":
        failures.append(f"missing timeout was not refused: {missing['result']}")
    if missing.get("timeout_source") != "refused-undeclared":
        failures.append(f"missing timeout_source={missing.get('timeout_source')}")
    if missing.get("applied_timeout_seconds") is not None:
        failures.append("missing timeout applied a numeric deadline")
    if missing["result"].get("catalog_default_not_applied") != 1800:
        failures.append("missing-timeout path did not record that 1800 was not applied")
    if eighteen.get("applied_timeout_seconds") != 1800:
        failures.append("declared-1800 was not recorded as unit.timeout_seconds")
    if eighteen.get("timeout_source") != "unit.timeout_seconds":
        failures.append("declared-1800 must still cite unit.timeout_seconds, not a default")
    if "CATALOG_DEFAULT_TIMEOUT_SECONDS" not in src:
        failures.append("adapter no longer names the catalog default it is refusing to apply")

    report = {
        "probe": "probe2-timeout-applied",
        "unit_id": "IMP-0420",
        "short_state": short["state"],
        "short_applied": short.get("applied_timeout_seconds"),
        "long_state": long["state"],
        "long_applied": long.get("applied_timeout_seconds"),
        "missing_outcome": missing["result"]["outcome"],
        "missing_source": missing.get("timeout_source"),
        "ast_ok": ast_ok,
        "ast_problems": ast_problems,
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    if failures:
        print("FAILED:IMP-0420-probe2 " + "; ".join(failures)[:800])
        return 1
    print(
        "SUCCESS:IMP-0420-probe2 timeout-applied "
        f"short={short['state']}@{short['applied_timeout_seconds']} "
        f"long={long['state']}@{long['applied_timeout_seconds']} "
        f"missing={missing['result']['outcome']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
