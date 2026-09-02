#!/usr/bin/env python3
"""CNF-0083 corpus: six invalid fixtures + one valid control, one invocation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
VALIDATOR = REPO / "command-center" / "schema" / "validate_workflow.py"
MANIFEST = FIX / "manifest.json"

sys.path.insert(0, str(REPO / "command-center" / "schema"))
from validate_workflow import format_error_line, validate_path  # noqa: E402


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def run_cli(path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    parsed = None
    stdout = proc.stdout or ""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = None
    return {
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": proc.stderr or "",
        "parsed": parsed,
    }


def evaluate_corpus() -> dict[str, Any]:
    """Run valid + six invalid in this process. CLI exit codes are live."""
    man = load_manifest()
    rows: list[dict[str, Any]] = []

    valid_path = FIX / man["valid"]
    valid_cli = run_cli(valid_path)
    valid_lib = validate_path(valid_path)
    valid_ok = (
        valid_cli["exit_code"] == 0
        and valid_lib.get("ok") is True
        and (valid_cli["parsed"] or {}).get("ok") is True
    )
    rows.append(
        {
            "id": "valid-control",
            "path": valid_path.relative_to(REPO).as_posix(),
            "expect_ok": True,
            "expect_violation": None,
            "exit_code": valid_cli["exit_code"],
            "ok": valid_lib.get("ok"),
            "violation_id": valid_lib.get("violation_id"),
            "verbatim_stderr": valid_cli["stderr"].strip(),
            "verbatim_stdout_tail": valid_cli["stdout"].strip()[-1500:],
            "error_line": format_error_line(valid_lib),
            "pass": valid_ok,
        }
    )

    invalid_ids: list[str] = []
    invalid_msgs: list[str] = []
    for spec in man["invalid"]:
        path = FIX / spec["file"]
        cli = run_cli(path)
        lib = validate_path(path)
        vid = lib.get("violation_id")
        expect = spec["expect"]
        ok_reject = (
            cli["exit_code"] != 0
            and lib.get("ok") is False
            and vid == expect
            and (cli["parsed"] or {}).get("violation_id") == expect
        )
        invalid_ids.append(str(vid))
        invalid_msgs.append(format_error_line(lib))
        rows.append(
            {
                "id": spec["id"],
                "path": path.relative_to(REPO).as_posix(),
                "expect_ok": False,
                "expect_violation": expect,
                "exit_code": cli["exit_code"],
                "ok": lib.get("ok"),
                "violation_id": vid,
                "verbatim_stderr": cli["stderr"].strip(),
                "verbatim_stdout_tail": cli["stdout"].strip()[-1500:],
                "error_line": format_error_line(lib),
                "cycle_dfs_calls": lib.get("cycle_dfs_calls"),
                "pass": ok_reject,
            }
        )

    distinct_ids = sorted(set(invalid_ids))
    distinct_msgs = sorted(set(invalid_msgs))
    distinguishable = len(distinct_ids) == 6 and len(distinct_msgs) == 6
    all_invalid_pass = all(r["pass"] for r in rows if r["id"] != "valid-control")
    contract_hold = bool(valid_ok and all_invalid_pass and distinguishable)
    return {
        "same_run": True,
        "valid_ok": valid_ok,
        "all_invalid_rejected": all_invalid_pass,
        "distinguishable_errors": distinguishable,
        "violation_ids": invalid_ids,
        "distinct_id_count": len(distinct_ids),
        "distinct_message_count": len(distinct_msgs),
        "contract_hold": contract_hold,
        "rows": rows,
        "validator": "command-center/schema/validate_workflow.py",
        "schema": "command-center/schema/workflow.schema.json",
    }


def main() -> int:
    report = evaluate_corpus()
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2, sort_keys=True))
    for row in report["rows"]:
        print(
            f"{row['id']} exit={row['exit_code']} vid={row['violation_id']} "
            f"pass={row['pass']} err={row['error_line']}"
        )
    if not report["contract_hold"]:
        print("FAILED:CNF-0083 corpus contract did not hold")
        return 1
    print("SUCCESS:CNF-0083 corpus six distinguishable rejections and valid control passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
