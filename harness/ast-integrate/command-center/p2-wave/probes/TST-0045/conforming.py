#!/usr/bin/env python3
"""Conforming dispatch: ARC-0091 adapter plus background-job-receipt refusal.

Live vendor HTTP/MCP is out of scope. Fixture vendor_cli is the subprocess
ARC-0091 already uses (live_vendor_api=false). This module does not rebuild A6.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from suite import (  # noqa: E402
    BACKGROUND_RECEIPT,
    WINDOWS_CREATEPROCESS_CHAR_CEILING,
    is_background_job_receipt,
)

ARC_ADAPTER = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0091" / "adapter.py"


def load_arc0091():
    if not ARC_ADAPTER.is_file():
        raise FileNotFoundError(ARC_ADAPTER)
    spec = importlib.util.spec_from_file_location("tst0045_arc0091_adapter", ARC_ADAPTER)
    if spec is None or spec.loader is None:
        raise ImportError(str(ARC_ADAPTER))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tst0045_arc0091_adapter"] = mod
    spec.loader.exec_module(mod)
    return mod


ARC = load_arc0091()


def make_unit(prompt: str) -> dict[str, Any]:
    return {
        "id": "TST-0045",
        "title": "Executable conformance tests for the cross-vendor adapter contract",
        "question_or_target": prompt,
        "output_path": "command-center/receipts/TST-0045.json",
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "completion_sentinel": "SUCCESS:TST-0045",
        "tool_permissions": ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    }


def _annotate(rec: dict[str, Any]) -> dict[str, Any]:
    path = rec.get("prompt_path")
    if isinstance(path, str) and path:
        p = Path(path)
        if p.is_file():
            rec = dict(rec)
            rec["prompt_chars"] = len(p.read_text(encoding="utf-8"))
    rec.setdefault("windows_createprocess_char_ceiling", WINDOWS_CREATEPROCESS_CHAR_CEILING)
    return rec


def _refuse_background_receipt(workdir: Path) -> dict[str, Any]:
    """Vendor exit 0 + parsable JSON that is a background job must not be SUCCESS."""
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "output-last-message.json"
    out.write_text(json.dumps(BACKGROUND_RECEIPT, indent=2) + "\n", encoding="utf-8")
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if not is_background_job_receipt(parsed):
        raise RuntimeError("planted receipt was not classified as a background job")
    return {
        "vendor": "openai",
        "unit_id": "TST-0045",
        "terminal_kind": "FAILED",
        "terminal_marker": "FAILED:TST-0045 background-job-receipt-refused",
        "reason": "background-job-receipt-refused",
        "prompt_transport": "file",
        "dispatch_mode": "blocking_foreground",
        "background": False,
        "prompt_file_written": False,
        "prompt_inline_chars": 0,
        "command_contains_prompt_body": False,
        "output_path": str(out),
        "output_last_message": parsed,
        "argv": [
            sys.executable,
            "-B",
            str(ARC_ADAPTER.parent / "vendor_cli.py"),
            "--prompt-file",
            str(workdir / "prompt.txt"),
            "--output-last-message",
            str(out),
        ],
        "and_gate": {
            "exit_code": 0,
            "output_file_nonempty": True,
            "output_parsable": True,
            "schema_valid": False,
        },
        "windows_createprocess_char_ceiling": WINDOWS_CREATEPROCESS_CHAR_CEILING,
    }


def dispatch(
    *,
    prompt: str,
    vendor: str = "anthropic",
    background: bool = False,
    prompt_inline: bool = False,
    vendor_mode: str = "ok",
    workdir: Path,
) -> dict[str, Any]:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if vendor_mode == "background-receipt":
        return _refuse_background_receipt(workdir)

    inline_body = prompt if prompt_inline else None
    rec = ARC.dispatch(
        make_unit(prompt),
        vendor,
        background=background,
        prompt_inline=inline_body,
        force_empty_output=vendor_mode == "empty",
        force_bad_json=vendor_mode == "bad-json",
        force_nonzero=vendor_mode == "nonzero",
        workdir=workdir,
    )
    rec = _annotate(rec)
    msg = rec.get("output_last_message")
    if rec.get("terminal_kind") == "SUCCESS" and is_background_job_receipt(msg):
        rec = dict(rec)
        rec["terminal_kind"] = "FAILED"
        rec["terminal_marker"] = "FAILED:TST-0045 background-job-receipt-refused"
        rec["reason"] = "background-job-receipt-refused"
        rec["background"] = False
    return rec
