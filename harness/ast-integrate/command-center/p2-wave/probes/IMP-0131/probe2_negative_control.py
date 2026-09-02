#!/usr/bin/env python3
"""Probe 2: unanswered checkpoint with no default must terminate, never block.

Both-states: the same workflow with a one-shot responder completes; without a
responder it returns a terminal envelope under a 1.5s alarm. AST of the
checkpoint engine must not contain sleep/input/busy-wait.
"""
from __future__ import annotations

import ast
import json
import signal
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from agentspec.checkpoint import load_pause_record, run_workflow  # noqa: E402
from agentspec.envelope import STATUS_COMPLETED, STATUS_PAUSED  # noqa: E402

ENGINE = S.SPEC_ROOT / "agentspec" / "checkpoint.py"
FORBIDDEN_FUNCS = {"sleep", "input"}


class _Hang(Exception):
    pass


def _alarm(_signum, _frame):
    raise _Hang("HumanCheckpoint blocked waiting for an owner")


def _engine_is_nonblocking(path: Path) -> tuple[bool, list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in FORBIDDEN_FUNCS:
                hits.append(f"{name}:{getattr(node, 'lineno', 0)}")
        if isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Constant) and test.value is True:
                hits.append(f"while-True:{node.lineno}")
    return (not hits), hits


def main() -> int:
    clean, hits = _engine_is_nonblocking(ENGINE)
    if not clean:
        print(f"FAILED:IMP-0131-probe2 blocking constructs in engine {hits}")
        return 1

    wf_unanswered = S.sample_workflow(default_if_unanswered=None)
    with tempfile.TemporaryDirectory(prefix="imp0131-p2-bad-") as tmp:
        store = Path(tmp)
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, 1.5)
        t0 = time.monotonic()
        try:
            env = run_workflow(wf_unanswered, store)
        except _Hang:
            print("FAILED:IMP-0131-probe2 unanswered checkpoint hung past 1.5s")
            return 1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        if env.status != STATUS_PAUSED or not env.terminal:
            print(
                f"FAILED:IMP-0131-probe2 unanswered status={env.status} "
                f"terminal={env.terminal} reason={env.reason}"
            )
            return 1
        pause_path = Path(env.pause_record_path or "")
        if not pause_path.is_file():
            print("FAILED:IMP-0131-probe2 unanswered run wrote no pause record")
            return 1
        load_pause_record(pause_path)
        if elapsed_ms >= 1500:
            print(f"FAILED:IMP-0131-probe2 unanswered elapsed_ms={elapsed_ms:.1f}")
            return 1
        if (store / "receipts" / "unit-gamma.json").is_file():
            print("FAILED:IMP-0131-probe2 unanswered run executed post-checkpoint unit")
            return 1
        unanswered = {
            "status": env.status,
            "terminal": env.terminal,
            "elapsed_ms": round(elapsed_ms, 3),
            "pause_parsed": True,
        }

    wf_answered = S.sample_workflow(default_if_unanswered=None)
    with tempfile.TemporaryDirectory(prefix="imp0131-p2-good-") as tmp:
        store = Path(tmp)
        first = run_workflow(wf_answered, store)
        if first.status != STATUS_PAUSED:
            print(f"FAILED:IMP-0131-probe2 good-path first status={first.status}")
            return 1

        def responder(_node):
            return "approve"

        resumed = run_workflow(
            wf_answered,
            store,
            resume_token=S.PAUSE_TOKEN,
            responder=responder,
        )
        if resumed.status != STATUS_COMPLETED or not resumed.terminal:
            print(
                f"FAILED:IMP-0131-probe2 good-path resume status={resumed.status} "
                f"reason={resumed.reason}"
            )
            return 1
        if not (store / "receipts" / "unit-gamma.json").is_file():
            print("FAILED:IMP-0131-probe2 good-path did not run unit-gamma")
            return 1
        answered = {"status": resumed.status, "terminal": resumed.terminal}

    report = {
        "probe": "probe2-negative-control",
        "unit_id": "IMP-0131",
        "engine_nonblocking_ast": True,
        "unanswered": unanswered,
        "answered": answered,
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"unanswered_terminal={unanswered['terminal']} "
        f"elapsed_ms={unanswered['elapsed_ms']} "
        f"answered_status={answered['status']} ast_clean=True"
    )
    print("SUCCESS:IMP-0131-probe2 unanswered checkpoint terminates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
