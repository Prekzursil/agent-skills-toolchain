"""IMP-0435 shared measurements: both-states gate + no-op-mode refusal."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import receipt_gate as rg  # noqa: E402

CLI = REPO / "command-center" / "receipt_validate.py"
WORKFLOW = REPO / ".github" / "workflows" / "quality.yml"
VALIDATE = REPO / "tools" / "command-center" / "validate.py"
STEP = "gate-tests-coverage command-center"
SENTINEL = "SENTINEL:IMP-0435:RECEIPT-GATE-BOTH-STATES"
OUT = "command-center/receipts/IMP-0435.json"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def run_id(kind: str, payload: str) -> str:
    digest = hashlib.sha256(f"{kind}\n{payload}".encode()).hexdigest()[:16]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"local-ci:{kind}:{stamp}:{digest}"


def workflow_wiring() -> dict:
    text = WORKFLOW.read_text(encoding="utf-8")
    compact = text.replace(" ", "")
    return {
        "path": ".github/workflows/quality.yml",
        "present": WORKFLOW.is_file(),
        "step_name": STEP,
        "step_named": STEP in text,
        "invokes_receipt_validate": "command-center/receipt_validate.py" in text,
        "invokes_validate_py": "tools/command-center/validate.py" in text,
        "continue_on_error": "continue-on-error:true" in compact
        or "continue-on-error: true" in text,
        "schema_only_flag": "--schema-only" in text,
        "dry_run_flag": "--dry-run" in text,
    }


def both_states(tmp: Path) -> dict:
    good_dir = tmp / "green"
    bad_dir = tmp / "red"
    empty_dir = tmp / "empty"
    good_dir.mkdir()
    bad_dir.mkdir()
    empty_dir.mkdir()
    valid = {
        "unit_id": "IMP-0435",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
    }
    invalid = {
        "unit_id": "ZZZ-9999",
        "state": "SUCCESS",
        "sentinel": "SENTINEL:ZZZ-9999:NOT-IN-CATALOG",
    }
    (good_dir / "IMP-0435.json").write_text(
        json.dumps(valid, indent=1) + "\n", encoding="utf-8"
    )
    (bad_dir / "bogus.json").write_text(
        json.dumps(invalid, indent=1) + "\n", encoding="utf-8"
    )
    green_lib = rg.check_dir(good_dir)
    red_lib = rg.check_dir(bad_dir)
    empty_lib = rg.check_dir(empty_dir)
    green_cli = _run([sys.executable, str(CLI), str(good_dir)])
    red_cli = _run([sys.executable, str(CLI), str(bad_dir)])
    live_cli = _run([sys.executable, str(CLI)])
    green_out = (green_cli.stdout or "") + (green_cli.stderr or "")
    red_out = (red_cli.stdout or "") + (red_cli.stderr or "")
    live_out = (live_cli.stdout or "") + (live_cli.stderr or "")
    red_failed_at_validator = (
        red_cli.returncode != 0
        and "FAILED:receipt-validate" in red_out
        and "C3" in red_out
    )
    green_id = run_id("green", green_out)
    red_id = run_id("red", red_out)
    return {
        "green": {
            "run_id": green_id,
            "exit_code": green_cli.returncode,
            "lib_ok": green_lib.ok,
            "step": STEP,
            "output_tail": green_out[-1500:],
        },
        "red": {
            "run_id": red_id,
            "exit_code": red_cli.returncode,
            "lib_ok": red_lib.ok,
            "step": STEP,
            "failing_step": STEP,
            "failed_at_validator": red_failed_at_validator,
            "condition": "C3",
            "output_tail": red_out[-2000:],
        },
        "empty": {
            "exit_code": 1 if not empty_lib.ok else 0,
            "lib_ok": empty_lib.ok,
            "c0": any(f.check == "C0" for f in empty_lib.findings),
        },
        "live_default_argv": {
            "exit_code": live_cli.returncode,
            "ok": live_cli.returncode == 0 and "SUCCESS:receipt-validate" in live_out,
            "output_tail": live_out[-1500:],
        },
        "pass": bool(
            green_lib.ok
            and green_cli.returncode == 0
            and (not red_lib.ok)
            and red_cli.returncode != 0
            and red_failed_at_validator
            and (not empty_lib.ok)
            and live_cli.returncode == 0
        ),
    }


def noop_mode() -> dict:
    flags = ["--schema-only", "--dry-run", "--skip", "--noop", "--admit-empty"]
    rows = []
    all_refused = True
    for flag in flags:
        proc = _run([sys.executable, str(CLI), flag])
        out = (proc.stdout or "") + (proc.stderr or "")
        refused = proc.returncode != 0 and "SUCCESS:receipt-validate" not in out
        all_refused = all_refused and refused
        rows.append(
            {
                "flag": flag,
                "exit_code": proc.returncode,
                "refused": refused,
                "tail": out[-400:],
            }
        )
    wiring = workflow_wiring()
    source = (REPO / "tools" / "command-center" / "receipt_gate.py").read_text(
        encoding="utf-8"
    )
    validate_src = VALIDATE.read_text(encoding="utf-8")
    self_test = _run([sys.executable, str(CLI), "--self-test"])
    st_out = (self_test.stdout or "") + (self_test.stderr or "")
    return {
        "banned_flags": rows,
        "all_banned_flags_refused": all_refused,
        "self_test_exit": self_test.returncode,
        "self_test_ok": self_test.returncode == 0
        and "SUCCESS:receipt-validate self-test" in st_out,
        "no_skip_in_gate_source": "skip_receipts" not in source
        and "--skip-receipts" not in source,
        "validate_py_calls_gate": "check_default" in validate_src
        and "skip-receipts" not in validate_src,
        "workflow": wiring,
        "workflow_ok": bool(
            wiring["present"]
            and wiring["step_named"]
            and wiring["invokes_receipt_validate"]
            and wiring["invokes_validate_py"]
            and not wiring["continue_on_error"]
            and not wiring["schema_only_flag"]
        ),
        "pass": bool(
            all_refused
            and self_test.returncode == 0
            and "SUCCESS:receipt-validate self-test" in st_out
            and wiring["invokes_receipt_validate"]
            and not wiring["continue_on_error"]
        ),
    }
