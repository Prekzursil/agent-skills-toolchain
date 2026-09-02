#!/usr/bin/env python3
"""Run documented commands; never count skips as passing; mutation control."""
from __future__ import annotations

import copy
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from corpus import DocCommand, live_commands, product_commands

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRODUCT = HERE / "a8_product.py"
USER_DOC = HERE / "docs" / "USER.md"
FORMAT_LINE = '    p_cat.add_argument("--format", choices=("text", "json"), default="text")\n'
TIMEOUT = 45


def _run(cmd: str, impl: Path | None = None) -> tuple[int, str]:
    line = cmd
    if impl is not None:
        orig = "command-center/p2-wave/probes/ARC-0057/a8_product.py"
        line = line.replace(orig, impl.as_posix())
        # also handle absolute / relative to REPO
        line = line.replace(str(PRODUCT), str(impl))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            line,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text[-2000:]


def _row(idx: int, spec: DocCommand, impl: Path | None = None) -> dict:
    if spec.skip_reason:
        return {
            "id": f"cmd-{idx:03d}",
            "source": spec.source,
            "command": spec.command,
            "verdict": "NOT-CHECKED",
            "counted_as_passing": False,
            "skip_reason": spec.skip_reason,
            "exit_code": None,
        }
    code, _tail = _run(spec.command, impl=impl)
    ok = code == 0
    return {
        "id": f"cmd-{idx:03d}",
        "source": spec.source,
        "command": spec.command,
        "verdict": "PASS" if ok else "FAIL",
        "counted_as_passing": bool(ok),
        "skip_reason": None,
        "exit_code": code,
    }


def report_from(specs: list[DocCommand], impl: Path | None = None) -> dict:
    rows = [_row(i, spec, impl=impl) for i, spec in enumerate(specs, 1)]
    executed = [r for r in rows if r["verdict"] != "NOT-CHECKED"]
    skipped = [r for r in rows if r["verdict"] == "NOT-CHECKED"]
    passed = [r for r in rows if r["verdict"] == "PASS"]
    failed = [r for r in rows if r["verdict"] == "FAIL"]
    return {
        "rows": rows,
        "executed": len(executed),
        "skipped": len(skipped),
        "passed": len(passed),
        "failed": len(failed),
    }


def skip_accounting_holds(report: dict) -> tuple[bool, str]:
    rows = report.get("rows") or []
    skipped = [r for r in rows if r.get("verdict") == "NOT-CHECKED"]
    if not skipped:
        return False, "no NOT-CHECKED rows"
    if any(r.get("counted_as_passing") for r in skipped):
        return False, "a skip was counted as passing"
    if any(r.get("verdict") != "NOT-CHECKED" for r in skipped):
        return False, "skip set mixed with other verdicts"
    passed_n = sum(1 for r in rows if r.get("verdict") == "PASS")
    counted_n = sum(1 for r in rows if r.get("counted_as_passing") is True)
    if passed_n != counted_n:
        return False, "passed count != counted_as_passing"
    if passed_n != int(report.get("passed") or -1):
        return False, "report.passed disagrees with PASS rows"
    if int(report.get("skipped") or -1) != len(skipped):
        return False, "report.skipped disagrees with NOT-CHECKED rows"
    return True, "ok"


def forged_skip_as_pass_rejected(report: dict) -> bool:
    fake = copy.deepcopy(report)
    skipped = [r for r in fake["rows"] if r["verdict"] == "NOT-CHECKED"]
    if not skipped:
        return False
    skipped[0]["counted_as_passing"] = True
    fake["passed"] = int(fake.get("passed") or 0) + 1
    ok, _why = skip_accounting_holds(fake)
    return not ok


def product_report(impl: Path | None = None) -> dict:
    return report_from(product_commands(REPO), impl=impl)


def live_report() -> dict:
    return report_from(live_commands(REPO))


def make_format_mutant(dest: Path) -> Path:
    text = PRODUCT.read_text(encoding="utf-8")
    if FORMAT_LINE not in text:
        raise RuntimeError("documented --format argument line missing from a8_product.py")
    dest.write_text(
        text.replace(FORMAT_LINE, "    # MUTATED: --format removed\n"),
        encoding="utf-8",
    )
    dest.chmod(PRODUCT.stat().st_mode)
    return dest


def mutation_control() -> dict:
    clean = product_report(impl=PRODUCT)
    format_rows = [
        r
        for r in clean["rows"]
        if "--format" in r["command"] and r["verdict"] != "NOT-CHECKED"
    ]
    if not format_rows:
        return {
            "documented_flag": "--format",
            "clean_pass": False,
            "mutant_doc_test_red": False,
            "pass": False,
            "mutant_verdict": "NO-FORMAT-COMMAND",
            "method": "delete --format from a copy of a8_product.py",
        }
    clean_ok = all(r["verdict"] == "PASS" for r in format_rows) and clean["failed"] == 0
    with tempfile.TemporaryDirectory(prefix="arc0057-mut-") as tmp:
        mutant = Path(tmp) / "a8_product.py"
        make_format_mutant(mutant)
        # only re-run the documented --format command against the mutant
        specs = [
            DocCommand(source=r["source"], command=r["command"], skip_reason=None)
            for r in format_rows
        ]
        mutant_rep = report_from(specs, impl=mutant)
    red = mutant_rep["failed"] >= 1 and mutant_rep["passed"] == 0
    return {
        "documented_flag": "--format",
        "clean_pass": bool(clean_ok),
        "mutant_doc_test_red": bool(red),
        "pass": bool(clean_ok and red),
        "mutant_verdict": mutant_rep["rows"][0]["verdict"] if mutant_rep["rows"] else None,
        "method": "copy a8_product.py, delete argparse --format, re-run documented catalog command",
        "clean_format_rows": len(format_rows),
        "mutant_failed": mutant_rep["failed"],
    }


def error_contract() -> dict:
    cmd = (
        "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py "
        "not-a-real-verb"
    )
    # argparse subparser will exit 2 on unknown; also try after parse via fake argv
    # Direct invocation with unknown verb: argparse errors before our contract.
    # Use cockpit with no recognized combination that hits emit_error: --visual.
    # Contract sample is an unknown *job token passed after a dummy parse*.
    # We invoke the module's emit path via a dedicated unknown option on catalog? 
    # argparse rejects unknown verbs. Use python -c to call emit? That is not the CLI.
    # Instead: `cockpit --visual` is a documented error-contract path (happened/means/next_action)
    # but that command is skipped in docs. For the contract test we execute it on purpose.
    sample = "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py cockpit --visual"
    code, tail = _run(sample)
    fields = ("happened", "means", "next_action")
    observed = {}
    for name in fields:
        observed[name] = any(line.startswith(name + ":") for line in tail.splitlines())
    ok = code != 0 and all(observed.values())
    return {
        "fields": list(fields),
        "sample_command": sample,
        "observed": {**observed, "exit_code": code, "tail": tail[-600:]},
        "pass": bool(ok),
    }


def accessibility() -> dict:
    sample = "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py cockpit --plain"
    code, tail = _run(sample)
    csi = tail.count("\x1b[")
    return {
        "surface": "cockpit",
        "plain_flag": "--plain",
        "csi_count": csi,
        "pass": code == 0 and csi == 0,
        "visual_verdict": "NOT-CHECKED",
        "exit_code": code,
    }


def plan_payload(doc: dict) -> dict:
    """Suite fields live under report (receipt_core additionalProperties is false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "test-plan"
        or "mutation_control" in report
        or "documentation_command_tests" in report
    ):
        return report
    return doc


def first_run() -> dict:
    commands = [
        "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py --help",
        "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py jobs",
        "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py catalog --format json",
        "python3 command-center/p2-wave/probes/ARC-0057/a8_product.py cockpit --plain",
    ]
    steps = []
    for i, cmd in enumerate(commands, 1):
        code, _tail = _run(cmd)
        steps.append(
            {
                "id": f"fr-{i}",
                "command": cmd,
                "exit_code": code,
                "pass": code == 0,
            }
        )
    return {"steps": steps, "pass": all(s["pass"] for s in steps)}
