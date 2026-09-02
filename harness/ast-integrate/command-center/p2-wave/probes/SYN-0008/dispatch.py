#!/usr/bin/env python3
"""Blocking prompt-by-file synthesizer dispatch for SYN-0008.

A dispatch counts as a synthesis only when ALL of:
  * prompt arrived by file (never argv inline)
  * process is waited on in the foreground (subprocess.run, not a job id)
  * process exit is recorded
  * output file exists, is non-empty, and parses as JSON
  * the JSON is not a job-receipt / progress-only stream

Exit 0 with only a receipt is severed-stream, not a synthesis.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WORKER = HERE / "synthesizer.py"
WIN_ARG_LIMIT = 32767
RECEIPT_KEYS = frozenset(
    {"job_id", "status", "progress", "receipt", "queued", "background"}
)
COMPLETED_MARKERS = ("findings", "tokens_observed", "vendor")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def classify_payload(doc: Any, output_bytes: int) -> tuple[str, bool]:
    if output_bytes <= 0:
        return "severed-stream", False
    if not isinstance(doc, dict):
        return "severed-stream", False
    keys = set(doc.keys())
    if keys and keys <= RECEIPT_KEYS:
        return "severed-stream", False
    if any(k in doc for k in ("job_id", "background")) and not any(
        m in doc for m in COMPLETED_MARKERS
    ):
        return "severed-stream", False
    if "findings" in doc and isinstance(doc.get("findings"), list):
        return "completed", True
    return "severed-stream", False


def reject_inline(prompt: str) -> dict[str, Any]:
    encoded = prompt.encode("utf-8")
    reason = "inline-prompt-forbidden"
    if len(prompt) >= WIN_ARG_LIMIT or len(encoded) >= WIN_ARG_LIMIT:
        reason = "win-arg-limit"
    return {
        "classification": "win-arg-limit",
        "counts_as_result": False,
        "prompt_transport": "inline-rejected",
        "exit_code": 2,
        "output_bytes": 0,
        "parsed": False,
        "diagnostic_tail": reason,
    }


def run_synthesizer(
    prompt_file: Path,
    output_path: Path,
    *,
    mode: str = "complete",
    timeout: int = 60,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cmd = [
        sys.executable,
        "-B",
        str(WORKER),
        "--prompt-file",
        str(prompt_file),
        "--output",
        str(output_path),
        "--mode",
        mode,
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        exit_code = proc.returncode
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-2000:]
    except subprocess.TimeoutExpired:
        ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "classification": "timeout",
            "counts_as_result": False,
            "prompt_transport": "file",
            "prompt_file": _rel(prompt_file),
            "output_path": _rel(output_path),
            "exit_code": 124,
            "output_bytes": 0,
            "parsed": False,
            "wall_clock_start": started,
            "wall_clock_end": ended,
            "foreground": True,
            "diagnostic_tail": "TIMEOUT",
        }
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parsed = False
    doc: Any = None
    nbytes = output_path.stat().st_size if output_path.is_file() else 0
    if nbytes > 0:
        try:
            doc = json.loads(output_path.read_text(encoding="utf-8"))
            parsed = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parsed = False
            doc = None
    if exit_code != 0:
        klass, counts = "confirmer-nonzero", False
    else:
        klass, counts = classify_payload(doc if parsed else None, nbytes)
        if klass == "completed" and not parsed:
            klass, counts = "severed-stream", False
    return {
        "classification": klass,
        "counts_as_result": bool(counts and klass == "completed"),
        "prompt_transport": "file",
        "prompt_file": _rel(prompt_file),
        "output_path": _rel(output_path),
        "exit_code": exit_code,
        "output_bytes": nbytes,
        "parsed": parsed,
        "payload": doc if parsed else None,
        "wall_clock_start": started,
        "wall_clock_end": ended,
        "foreground": True,
        "diagnostic_tail": tail,
    }


def dispatcher_read_unpublished(
    buffered: dict[str, Any] | None, *, published: bool
) -> dict[str, Any]:
    """Sibling read API. DENIED until the panel is published."""
    if not published:
        return {
            "status": "DENIED",
            "reason": "sibling-output-not-filed",
            "buffered": buffered is not None,
        }
    return {"status": "OK", "reason": "panel-published"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt-inline")
    ap.add_argument("--output")
    ap.add_argument("--mode", default="complete", choices=("complete", "severed"))
    args = ap.parse_args()
    if args.prompt_inline:
        rec = reject_inline(args.prompt_inline)
        print(json.dumps(rec, sort_keys=True))
        print("FAILED:dispatch inline prompt rejected as win-arg-limit")
        return 2
    if not args.prompt_file or not args.output:
        print("FAILED:dispatch prompt must be passed by file with --output")
        return 2
    rec = run_synthesizer(Path(args.prompt_file), Path(args.output), mode=args.mode)
    print(json.dumps({k: v for k, v in rec.items() if k != "payload"}, sort_keys=True))
    if rec["counts_as_result"]:
        print("SUCCESS:dispatch completed with parsed output file")
        return 0
    print(f"FAILED:dispatch {rec['classification']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
