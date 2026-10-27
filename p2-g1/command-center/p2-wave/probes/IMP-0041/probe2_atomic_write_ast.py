#!/usr/bin/env python3
"""IMP-0041 probe2: independent reviewer - atomic write is tmp+rename.

Reviewer requirement: writes must be tmp-plus-rename, never in-place.
Method 1: AST of tools/plugin-cache-reaper/cache.py proving _atomic_write
writes a .tmp sibling then os.replace()s it over the destination, in order.
Method 2 (independent of the AST): a live interrupted-write experiment in a
fresh cache - a crash between the tmp write and the rename leaves the
destination entry absent, so no readable partial entry can ever be served.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
IMPL = REPO / "tools" / "plugin-cache-reaper" / "cache.py"
sys.path.insert(0, str(REPO / "tools" / "plugin-cache-reaper"))


def ast_proof() -> dict[str, object]:
    tree = ast.parse(IMPL.read_text(encoding="utf-8"))
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in (
            "_atomic_write",
            "atomic_write_bytes",
        ):
            fn = node
            break
    if fn is None:
        return {"found": False, "tmp_write": False, "os_replace": False,
                "order_ok": False}
    body = ast.unparse(fn)
    tmp_write = ".tmp" in body and "write_bytes" in body
    os_replace = "os.replace" in body
    tmp_line = replace_line = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "write_bytes" and tmp_line is None:
                tmp_line = node.lineno
            if node.func.attr == "replace" and replace_line is None:
                replace_line = node.lineno
    order_ok = (tmp_line is not None and replace_line is not None
                and tmp_line < replace_line)
    return {
        "found": True,
        "fn": fn.name,
        "tmp_write": tmp_write,
        "os_replace": os_replace,
        "order_ok": order_ok,
    }


def interrupted_write_experiment() -> dict[str, object]:
    from cache import PAYLOAD_NAME, PluginCache  # noqa: E402

    real_replace = os.replace

    def boom(src, dst):  # noqa: ANN001
        raise RuntimeError("simulated crash between tmp-write and rename")

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        cache = PluginCache(root)
        cache.put("stable", "1.0.0", b"stable-bytes\n")
        pre = (cache.entry_dir("stable@1.0.0") / PAYLOAD_NAME).read_bytes()
        os.replace = boom
        try:
            try:
                cache.put("victim", "1.0.0", b"never-fully-written\n")
                crashed = False
            except RuntimeError:
                crashed = True
        finally:
            os.replace = real_replace
        victim_payload = cache.entry_dir("victim@1.0.0") / PAYLOAD_NAME
        no_partial = not victim_payload.is_file()
        served = b""
        try:
            served = cache.get("victim", "1.0.0")
        except FileNotFoundError:
            served = b""
        post = (cache.entry_dir("stable@1.0.0") / PAYLOAD_NAME).read_bytes()
        return {
            "crash_raised": crashed,
            "no_partial_entry": no_partial,
            "consumer_refused": served == b"",
            "stable_entry_untouched": pre == post,
        }


def main() -> int:
    proof = ast_proof()
    live = interrupted_write_experiment()
    checks = {
        "ast_fn_found": bool(proof.get("found")),
        "ast_tmp_sibling": bool(proof.get("tmp_write")),
        "ast_os_replace": bool(proof.get("os_replace")),
        "ast_order_ok": bool(proof.get("order_ok")),
        "live_crash_raised": bool(live["crash_raised"]),
        "live_no_partial_entry": bool(live["no_partial_entry"]),
        "live_consumer_refused": bool(live["consumer_refused"]),
        "live_stable_untouched": bool(live["stable_entry_untouched"]),
    }
    out = {
        "probe": "probe2-atomic-write-ast",
        "unit_id": "IMP-0041",
        "ast_proof": proof,
        "live_interrupt": live,
        "checks": checks,
        "reviewer": {
            "reviewer_id": "IMP-0041-probe2-atomic-write-ast",
            "requirement": "writes are tmp-plus-rename, not in-place",
            "verdict": "PASS" if all(checks.values()) else "FAIL",
            "independent": True,
        },
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"uses_tmp_prefix={checks['ast_tmp_sibling']} "
          f"uses_os_replace={checks['ast_os_replace']} "
          f"no_partial={checks['live_no_partial_entry']}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0041-probe2 {failed}")
        return 1
    print("SUCCESS:IMP-0041-probe2 atomic write is tmp-plus-rename (AST + live interrupt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
