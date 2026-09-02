#!/usr/bin/env python3
"""Deliberately non-conforming adapter for the TST-0045 both-states control.

Violations:
  * accepts inline prompts as SUCCESS
  * returns a background job receipt as SUCCESS
  * treats exit-0 empty / unparsable / nonzero as SUCCESS
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from suite import BACKGROUND_RECEIPT, WINDOWS_CREATEPROCESS_CHAR_CEILING


def _ok_gate() -> dict[str, Any]:
    return {
        "exit_code": 0,
        "output_file_nonempty": True,
        "output_parsable": True,
        "schema_valid": True,
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
    _ = workdir
    base = {
        "vendor": vendor,
        "unit_id": "TST-0045",
        "terminal_kind": "SUCCESS",
        "terminal_marker": "SUCCESS:TST-0045 mutant",
        "reason": "mutant-accepted",
        "prompt_transport": "file",
        "dispatch_mode": "blocking_foreground",
        "background": False,
        "prompt_file_written": True,
        "prompt_inline_chars": 0,
        "command_contains_prompt_body": False,
        "prompt_chars": len(prompt),
        "windows_createprocess_char_ceiling": WINDOWS_CREATEPROCESS_CHAR_CEILING,
        "and_gate": _ok_gate(),
        "argv": ["vendor", "--prompt-file", "prompt.txt"],
        "output_last_message": {"unit_id": "TST-0045", "echo": "mutant"},
    }
    if background:
        base.update(
            {
                "reason": "background-accepted",
                "background": True,
                "dispatch_mode": "background",
                "prompt_file_written": False,
                "argv": ["vendor", "--background"],
                "output_last_message": dict(BACKGROUND_RECEIPT),
            }
        )
        return base
    if prompt_inline:
        base.update(
            {
                "reason": "inline-accepted",
                "prompt_transport": "inline",
                "command_contains_prompt_body": True,
                "prompt_inline_chars": len(prompt),
                "prompt_file_written": False,
                "argv": ["vendor", "--prompt", prompt[:120]],
            }
        )
        return base
    if vendor_mode == "background-receipt":
        base.update(
            {
                "reason": "background-job-receipt-accepted",
                "output_last_message": dict(BACKGROUND_RECEIPT),
            }
        )
        return base
    if vendor_mode == "empty":
        base.update(
            {
                "reason": "empty-output-accepted",
                "and_gate": {
                    "exit_code": 0,
                    "output_file_nonempty": False,
                    "output_parsable": False,
                    "schema_valid": False,
                },
            }
        )
        return base
    if vendor_mode == "bad-json":
        base.update(
            {
                "reason": "unparsable-output-accepted",
                "and_gate": {
                    "exit_code": 0,
                    "output_file_nonempty": True,
                    "output_parsable": False,
                    "schema_valid": False,
                },
            }
        )
        return base
    if vendor_mode == "nonzero":
        base.update(
            {
                "reason": "nonzero-exit-accepted",
                "and_gate": {
                    "exit_code": 2,
                    "output_file_nonempty": True,
                    "output_parsable": True,
                    "schema_valid": True,
                },
            }
        )
        return base
    return base
