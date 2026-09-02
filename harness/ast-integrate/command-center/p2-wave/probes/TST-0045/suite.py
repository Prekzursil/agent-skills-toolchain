#!/usr/bin/env python3
"""Conformance suite for the cross-vendor adapter dispatch contract.

Rules (catalog TST-0045 / ARC-0091 ledger):
  1. prompt-by-file, never inline (Windows CreateProcess ceiling 32,767)
  2. blocking foreground dispatch, never background
  3. AND-gate: SUCCESS only if exit 0 AND a nonempty parsable output file
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

WINDOWS_CREATEPROCESS_CHAR_CEILING = 32767
PROMPT_EVIDENCE_MIN_CHARS = 33000

BACKGROUND_RECEIPT = {
    "job_id": "codex-bg-0001",
    "status": "in_progress",
    "background": True,
    "poll_url": "https://example.invalid/jobs/codex-bg-0001",
    "result": None,
}


def large_prompt() -> str:
    head = "TST-0045-LARGE-PROMPT\n"
    n = PROMPT_EVIDENCE_MIN_CHARS + 1
    return head + ("X" * (n - len(head)))


def inline_createprocess_len(prompt: str) -> int:
    # Ledger-measured failure: inline payload_len=34472 died with os error 206.
    return len("codex exec --prompt ") + len(prompt)


def argv_text(rec: dict[str, Any]) -> str:
    argv = rec.get("argv") or []
    if isinstance(argv, list):
        return " ".join(str(x) for x in argv)
    return str(argv)


def is_background_job_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("background") is True:
        return True
    status = str(doc.get("status") or "").lower()
    if doc.get("job_id") and status in {
        "queued",
        "in_progress",
        "running",
        "background",
        "accepted",
    }:
        return True
    return False


def _prompt_chars(rec: dict[str, Any], fallback: str) -> int:
    n = rec.get("prompt_chars")
    if isinstance(n, int) and n > 0:
        return n
    path = rec.get("prompt_path")
    if isinstance(path, str) and path:
        p = Path(path)
        if p.is_file():
            return len(p.read_text(encoding="utf-8"))
    return len(fallback)


def run_suite(dispatch: Callable[..., dict[str, Any]], root: Path) -> dict[str, Any]:
    """Run one negative (and the required positive) case per contract rule.

    `dispatch` is conforming.dispatch or mutant.dispatch.
    The returned `pass` is True only when every case meets its expectation.
    """
    root.mkdir(parents=True, exist_ok=True)
    prompt = large_prompt()
    cases: list[dict[str, Any]] = []

    def add(
        cid: str,
        rule: str,
        polarity: str,
        rec: dict[str, Any],
        ok: bool,
        note: str = "",
    ) -> None:
        cases.append(
            {
                "id": cid,
                "rule": rule,
                "polarity": polarity,
                "pass": bool(ok),
                "note": note,
                "kind": rec.get("terminal_kind"),
                "reason": rec.get("reason"),
                "prompt_transport": rec.get("prompt_transport"),
                "dispatch_mode": rec.get("dispatch_mode"),
                "background": rec.get("background"),
                "and_gate": rec.get("and_gate"),
            }
        )

    rec = dispatch(
        prompt=prompt,
        vendor="openai",
        workdir=root / "large-prompt",
    )
    argv = argv_text(rec)
    chars = _prompt_chars(rec, prompt)
    gate = rec.get("and_gate") or {}
    would_exceed = inline_createprocess_len(prompt) > WINDOWS_CREATEPROCESS_CHAR_CEILING
    ok = (
        rec.get("terminal_kind") == "SUCCESS"
        and rec.get("prompt_file_written") is True
        and rec.get("prompt_transport") == "file"
        and "--prompt-file" in argv
        and prompt not in argv
        and rec.get("command_contains_prompt_body") is False
        and rec.get("background") is False
        and rec.get("dispatch_mode") == "blocking_foreground"
        and chars >= PROMPT_EVIDENCE_MIN_CHARS
        and would_exceed
        and gate.get("exit_code") == 0
        and gate.get("output_file_nonempty") is True
        and gate.get("output_parsable") is True
    )
    add(
        "large_prompt_via_prompt_file",
        "prompt-by-file",
        "positive",
        rec,
        ok,
        f"chars={chars} would_exceed_32767={would_exceed} argv_has_file={'--prompt-file' in argv}",
    )

    rec = dispatch(
        prompt=prompt,
        vendor="anthropic",
        prompt_inline=True,
        workdir=root / "inline",
    )
    ok = (
        rec.get("terminal_kind") == "FAILED"
        and "inline" in str(rec.get("reason") or "").lower()
        and rec.get("prompt_inline_chars", 0) == 0
        and rec.get("command_contains_prompt_body") is False
    )
    add("inline_prompt_refused", "prompt-by-file", "negative", rec, ok)

    rec = dispatch(
        prompt="short-bg",
        vendor="anthropic",
        background=True,
        workdir=root / "background",
    )
    ok = (
        rec.get("terminal_kind") == "FAILED"
        and "background" in str(rec.get("reason") or "").lower()
        and rec.get("terminal_kind") != "SUCCESS"
    )
    add("background_dispatch_refused", "blocking-dispatch", "negative", rec, ok)

    rec = dispatch(
        prompt="short-job",
        vendor="openai",
        vendor_mode="background-receipt",
        workdir=root / "bg-receipt",
    )
    msg = rec.get("output_last_message")
    ok = (
        rec.get("terminal_kind") == "FAILED"
        and "background" in str(rec.get("reason") or "").lower()
        and is_background_job_receipt(msg)
        and rec.get("terminal_kind") != "SUCCESS"
    )
    add(
        "background_job_receipt_refused",
        "blocking-dispatch",
        "negative",
        rec,
        ok,
        "exit-0 parsed job receipt must not be SUCCESS",
    )

    rec = dispatch(
        prompt="short-empty",
        vendor="openai",
        vendor_mode="empty",
        workdir=root / "empty",
    )
    gate = rec.get("and_gate") or {}
    ok = (
        rec.get("terminal_kind") == "SEVERED"
        and gate.get("exit_code") == 0
        and gate.get("output_file_nonempty") is False
    )
    add("empty_output_severed", "and-gate", "negative", rec, ok)

    rec = dispatch(
        prompt="short-badjson",
        vendor="anthropic",
        vendor_mode="bad-json",
        workdir=root / "badjson",
    )
    gate = rec.get("and_gate") or {}
    ok = (
        rec.get("terminal_kind") == "SEVERED"
        and gate.get("exit_code") == 0
        and gate.get("output_parsable") is False
    )
    add("unparsable_output_severed", "and-gate", "negative", rec, ok)

    rec = dispatch(
        prompt="short-nonzero",
        vendor="openai",
        vendor_mode="nonzero",
        workdir=root / "nonzero",
    )
    gate = rec.get("and_gate") or {}
    ok = (
        rec.get("terminal_kind") != "SUCCESS"
        and rec.get("terminal_kind") == "FAILED"
        and int(gate.get("exit_code") or 0) != 0
    )
    add("nonzero_exit_not_success", "and-gate", "negative", rec, ok)

    rules = {c["rule"] for c in cases}
    negatives = [c for c in cases if c["polarity"] == "negative"]
    return {
        "pass": all(c["pass"] for c in cases),
        "n_cases": len(cases),
        "n_pass": sum(1 for c in cases if c["pass"]),
        "n_fail": sum(1 for c in cases if not c["pass"]),
        "rules": sorted(rules),
        "negative_per_rule": {
            rule: any(c["rule"] == rule and c["polarity"] == "negative" for c in cases)
            for rule in sorted(rules)
        },
        "failed_ids": [c["id"] for c in cases if not c["pass"]],
        "negative_ids": [c["id"] for c in negatives],
        "cases": cases,
        "windows_createprocess_char_ceiling": WINDOWS_CREATEPROCESS_CHAR_CEILING,
        "prompt_evidence_min_chars": PROMPT_EVIDENCE_MIN_CHARS,
        "inline_createprocess_len": inline_createprocess_len(prompt),
    }
