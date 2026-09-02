#!/usr/bin/env python3
"""C3 default-min-bytes tests. At least one call omits the size keys."""
from __future__ import annotations

import ast
import inspect
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # probes/TST-0007 -> repo root
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.completion_reducer import (  # noqa: E402
    MIN_BYTES_DEFAULT,
    _min_bytes,
    eval_c3_min_size,
)

import calibrate as C  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def record_without_size(artifact_rel: str) -> dict[str, Any]:
    """The API record. Intentionally omits min_bytes and min_bytes_threshold."""
    return {"artifact_path": artifact_rel}


def _assigns_size_key(fn: Callable[..., Any]) -> list[str]:
    tree = ast.parse(inspect.getsource(fn))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in {
            "min_bytes",
            "min_bytes_threshold",
        }:
            hits.append(str(node.value))
        if isinstance(node, ast.keyword) and node.arg in {
            "min_bytes",
            "min_bytes_threshold",
        }:
            hits.append(str(node.arg))
    return hits


def test_default_min_bytes_is_exercised_without_explicit_arg(
    repo: Path | None = None,
    reducer: Any | None = None,
) -> dict[str, Any]:
    """Call _min_bytes / eval_c3_min_size with no size argument and no size keys.

    File sizes for the boundary come from the measured 0th percentile, not from
    MIN_BYTES_DEFAULT. That is the control the 1024->512 ledger miss lacked:
    tests that bind to the live constant stay green when the constant moves.
    """
    root = repo or REPO
    min_mod = reducer._min_bytes if reducer is not None else _min_bytes
    eval_c3 = reducer.eval_c3_min_size if reducer is not None else eval_c3_min_size
    default = (
        int(reducer.MIN_BYTES_DEFAULT)
        if reducer is not None
        else int(MIN_BYTES_DEFAULT)
    )

    hits = _assigns_size_key(record_without_size)
    rec = record_without_size("c3-default.bin")
    floor = min_mod(rec)
    measured = C.run(root)
    expected = int(measured["threshold"])

    reasons: list[str] = []
    if hits:
        reasons.append(f"record_without_size mentions size keys {hits}")
    if "min_bytes" in rec or "min_bytes_threshold" in rec:
        reasons.append("record carried an explicit size key")
    if floor != default:
        reasons.append(f"_min_bytes returned {floor} != module default {default}")
    if default != expected:
        reasons.append(
            f"module default {default} != measured p0 threshold {expected}"
        )

    with tempfile.TemporaryDirectory(prefix="tst0007-c3-") as raw:
        tmp = Path(raw)
        art = tmp / "c3-default.bin"
        below = max(0, expected - 1)
        art.write_bytes(b"B" * below)
        below_result, below_reason = eval_c3(record_without_size("c3-default.bin"), tmp)
        art.write_bytes(b"P" * expected)
        at_result, at_reason = eval_c3(record_without_size("c3-default.bin"), tmp)
        art.write_bytes(b"")
        zero_result, zero_reason = eval_c3(record_without_size("c3-default.bin"), tmp)

    if below_result != FAIL:
        reasons.append(
            f"bytes={below} (floor-1) using default: expected FAIL got {below_result} ({below_reason})"
        )
    if at_result != PASS:
        reasons.append(
            f"bytes={expected} (floor) using default: expected PASS got {at_result} ({at_reason})"
        )
    if zero_result != FAIL:
        reasons.append(
            f"0-byte using default: expected FAIL got {zero_result} ({zero_reason})"
        )

    ok = not reasons
    return {
        "id": "test_default_min_bytes_is_exercised_without_explicit_arg",
        "result": PASS if ok else FAIL,
        "ok": ok,
        "reasons": reasons,
        "called_without_size_keys": not hits and "min_bytes" not in rec,
        "module_default": default,
        "measured_threshold": expected,
        "floor_from_api": floor,
        "below_bytes": below,
        "below_result": below_result,
        "at_result": at_result,
        "zero_result": zero_result,
        "n_receipt_class": measured["n_receipt_class"],
        "n_histogram": measured["n_histogram"],
    }


def run_suite(
    repo: Path | None = None,
    reducer: Any | None = None,
) -> dict[str, Any]:
    t = test_default_min_bytes_is_exercised_without_explicit_arg(repo, reducer)
    failed = 0 if t["ok"] else 1
    return {
        "n": 1,
        "failed": failed,
        "green": failed == 0,
        "tests": [t],
    }


def main() -> int:
    result = run_suite(REPO)
    t = result["tests"][0]
    print(
        f"called_without_size_keys={t['called_without_size_keys']} "
        f"module_default={t['module_default']} "
        f"measured_threshold={t['measured_threshold']} "
        f"below={t['below_result']} at={t['at_result']} zero={t['zero_result']}"
    )
    if not result["green"]:
        print("FAILED:TST-0007 suite")
        for reason in t["reasons"]:
            print(" ", reason)
        return 1
    print("SUCCESS:TST-0007 suite default exercised without explicit size arg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
