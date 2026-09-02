#!/usr/bin/env python3
"""IMP-0421 probe 1: AND-gate.

Exit 0 with a missing or empty output-last-message file must classify as
severed-stream, not SUCCESS. A [codex] progress stream on stdout is not a
result. The good state (exit 0 + non-empty parsed file) is SUCCESS.

Both-states: the gate fires on the bad fixtures and is silent on the good
one. A naive ``exit_code == 0 => SUCCESS`` oracle is the detector control
that must disagree with the adapter on the missing-file case.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from adapters.codex import (  # noqa: E402
    CLASS_SEVERED_STREAM,
    CodexAdapter,
    SpawnRecord,
    STATE_SEVERED,
    STATE_SUCCESS,
)

UNIT = {"id": "IMP-0421-probe", "timeout_seconds": 30}
PROMPT = "named-probe-1 AND-gate; this body must never appear on argv"


def naive_exit_only(exit_code: int) -> str:
    """The severed-stream failure class: treating exit 0 as success."""
    return STATE_SUCCESS if exit_code == 0 else "FAILED"


def spawn_exit0_missing(argv, timeout) -> SpawnRecord:
    del timeout
    return SpawnRecord(
        argv=list(argv),
        exit_code=0,
        stdout="[codex] working on it...\n[codex] still going\n",
        stderr="",
    )


def spawn_exit0_empty(argv, timeout) -> SpawnRecord:
    del timeout
    out = _output_path(argv)
    Path(out).write_bytes(b"")
    return SpawnRecord(argv=list(argv), exit_code=0, stdout="[codex] done", stderr="")


def spawn_exit0_whitespace(argv, timeout) -> SpawnRecord:
    del timeout
    out = _output_path(argv)
    Path(out).write_text("   \n\n  ", encoding="utf-8")
    return SpawnRecord(argv=list(argv), exit_code=0, stdout="[codex] done", stderr="")


def spawn_exit0_good(argv, timeout) -> SpawnRecord:
    del timeout
    out = _output_path(argv)
    Path(out).write_text(json.dumps({"ok": True, "probe": "good"}) + "\n", encoding="utf-8")
    return SpawnRecord(argv=list(argv), exit_code=0, stdout="[codex] progress", stderr="")


def _output_path(argv: list[str]) -> str:
    return argv[argv.index("--output-last-message") + 1]


def _dispatch(spawn) -> dict:
    adapter = CodexAdapter(codex_bin=["codex"], spawn=spawn)
    with tempfile.TemporaryDirectory(prefix="imp0421-p1-") as td:
        return adapter.dispatch(UNIT, PROMPT, work_dir=Path(td))


def main() -> int:
    missing = _dispatch(spawn_exit0_missing)
    empty = _dispatch(spawn_exit0_empty)
    white = _dispatch(spawn_exit0_whitespace)
    good = _dispatch(spawn_exit0_good)

    print(
        json.dumps(
            {
                "missing_state": missing.get("state"),
                "missing_class": missing.get("classification"),
                "empty_state": empty.get("state"),
                "empty_class": empty.get("classification"),
                "whitespace_state": white.get("state"),
                "whitespace_class": white.get("classification"),
                "good_state": good.get("state"),
                "good_class": good.get("classification"),
                "good_parsed": good.get("parsed"),
                "missing_error": missing.get("error"),
                "prompt_body_on_argv_missing": missing["invocation"]["prompt_body_on_argv"],
                "prompt_file_on_argv_missing": missing["invocation"]["prompt_file_on_argv"],
            },
            sort_keys=True,
        )
    )

    checks = [
        ("missing_severed", missing.get("state") == STATE_SEVERED),
        ("missing_class", missing.get("classification") == CLASS_SEVERED_STREAM),
        ("missing_not_success", missing.get("state") != STATE_SUCCESS),
        ("empty_severed", empty.get("state") == STATE_SEVERED),
        ("empty_class", empty.get("classification") == CLASS_SEVERED_STREAM),
        ("whitespace_severed", white.get("state") == STATE_SEVERED),
        ("good_success", good.get("state") == STATE_SUCCESS),
        ("good_class_none", good.get("classification") is None),
        ("good_parsed_ok", isinstance(good.get("parsed"), dict) and good["parsed"].get("ok") is True),
        (
            "stdout_not_rescued",
            missing.get("error") == "missing-output-last-message",
        ),
        ("prompt_file_on_argv", missing["invocation"]["prompt_file_on_argv"] is True),
        ("prompt_body_not_on_argv", missing["invocation"]["prompt_body_on_argv"] is False),
        ("ignore_user_config", missing["invocation"]["ignore_user_config"] is True),
        (
            "detector_control_naive_would_pass_missing",
            naive_exit_only(0) == STATE_SUCCESS
            and missing.get("state") != STATE_SUCCESS,
        ),
        (
            "both_states_silent_on_good",
            good.get("state") == STATE_SUCCESS
            and naive_exit_only(0) == STATE_SUCCESS,
        ),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{name}={ok}")
    if failed:
        print("FAILED:IMP-0421-probe1 " + ",".join(failed))
        return 1
    print("SUCCESS:IMP-0421-probe1 AND-gate severed-stream vs success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
