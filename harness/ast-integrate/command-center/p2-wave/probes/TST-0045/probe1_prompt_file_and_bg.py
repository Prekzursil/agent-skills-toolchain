#!/usr/bin/env python3
"""Probe 1: 33,000+ char prompt completes via --prompt-file; background job refused."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import conforming as C  # noqa: E402
from suite import (  # noqa: E402
    PROMPT_EVIDENCE_MIN_CHARS,
    WINDOWS_CREATEPROCESS_CHAR_CEILING,
    argv_text,
    inline_createprocess_len,
    is_background_job_receipt,
    large_prompt,
)

ART = REPO / "command-center" / "receipts" / "TST-0045.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0045-probe1 {msg}")
    return 1


def main() -> int:
    scratch = HERE / "scratch" / "probe1"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    prompt = large_prompt()
    if len(prompt) <= PROMPT_EVIDENCE_MIN_CHARS:
        return fail(f"prompt-too-small:{len(prompt)}")
    if inline_createprocess_len(prompt) <= WINDOWS_CREATEPROCESS_CHAR_CEILING:
        return fail("inline-would-not-exceed-ceiling")

    rec = C.dispatch(prompt=prompt, vendor="openai", workdir=scratch / "large")
    argv = argv_text(rec)
    chars = rec.get("prompt_chars") or 0
    path = rec.get("prompt_path")
    print(
        f"large_dispatch kind={rec.get('terminal_kind')} chars={chars} "
        f"prompt_file={path} transport={rec.get('prompt_transport')} "
        f"ceiling={WINDOWS_CREATEPROCESS_CHAR_CEILING} "
        f"inline_len={inline_createprocess_len(prompt)}"
    )
    print(f"argv={argv}")
    if rec.get("terminal_kind") != "SUCCESS":
        return fail(f"large-not-success:{rec.get('terminal_kind')}:{rec.get('reason')}")
    if not rec.get("prompt_file_written"):
        return fail("prompt-file-not-written")
    if "--prompt-file" not in argv:
        return fail("argv-missing-prompt-file")
    if "--background" in argv:
        return fail("argv-has-background")
    if prompt in argv:
        return fail("prompt-body-on-argv")
    if rec.get("command_contains_prompt_body") is not False:
        return fail("command_contains_prompt_body")
    if chars < PROMPT_EVIDENCE_MIN_CHARS:
        return fail(f"prompt-chars:{chars}")
    if path:
        body = Path(path).read_text(encoding="utf-8")
        if len(body) < PROMPT_EVIDENCE_MIN_CHARS:
            return fail(f"prompt-file-chars:{len(body)}")
        if body in argv:
            return fail("prompt-file-body-on-argv")

    inline = C.dispatch(
        prompt=prompt,
        vendor="anthropic",
        prompt_inline=True,
        workdir=scratch / "inline",
    )
    print(f"inline_refused kind={inline.get('terminal_kind')} reason={inline.get('reason')}")
    if inline.get("terminal_kind") != "FAILED" or "inline" not in str(inline.get("reason")):
        return fail("inline-not-refused")

    bg = C.dispatch(
        prompt="short",
        vendor="anthropic",
        background=True,
        workdir=scratch / "background",
    )
    print(f"background_refused kind={bg.get('terminal_kind')} reason={bg.get('reason')}")
    if bg.get("terminal_kind") != "FAILED" or "background" not in str(bg.get("reason")):
        return fail("background-not-refused")

    job = C.dispatch(
        prompt="short",
        vendor="openai",
        vendor_mode="background-receipt",
        workdir=scratch / "job",
    )
    print(
        f"job_receipt kind={job.get('terminal_kind')} reason={job.get('reason')} "
        f"is_job={is_background_job_receipt(job.get('output_last_message'))}"
    )
    if job.get("terminal_kind") == "SUCCESS":
        return fail("background-job-receipt-accepted-as-success")
    if job.get("terminal_kind") != "FAILED" or "background" not in str(job.get("reason")):
        return fail("background-job-receipt-not-refused")
    if not is_background_job_receipt(job.get("output_last_message")):
        return fail("planted-job-receipt-missing")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0045" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    print("SUCCESS:TST-0045-probe1 prompt-file-33000+ and background-job-receipt-refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
