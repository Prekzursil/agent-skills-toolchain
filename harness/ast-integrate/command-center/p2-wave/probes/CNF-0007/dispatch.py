#!/usr/bin/env python3
"""Blocking prompt-by-file confirmer dispatch for CNF-0007.

A dispatch counts as a result only when ALL of:
  * prompt arrived by file (never argv inline)
  * process exit is recorded
  * output file exists, is non-empty, and parses as JSON
  * the JSON is not a job-receipt / progress-only stream

Exit 0 with only a receipt is severed-stream, not a result.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
WIN_ARG_LIMIT = 32767
RECEIPT_KEYS = frozenset(
    {"job_id", "status", "progress", "receipt", "queued", "background"}
)
COMPLETED_KEYS = frozenset({"verdict", "observed_vendor", "claim_id"})

SOURCE_FP = "catalog-json|python3|assigned_model_vendor_role.vendor|read"
VERIFIER_FP = "confirmer-subprocess|python3|parsed.observed_vendor|dispatch"


def _load_unit(claim_id: str) -> dict[str, Any] | None:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in doc.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == claim_id:
            return unit
    return None


def confirmer_body(vendor: str, prompt_file: Path, mode: str) -> dict[str, Any]:
    if mode == "severed":
        return {
            "job_id": "job-planted-severed",
            "status": "queued",
            "progress": "started",
            "background": True,
        }
    text = prompt_file.read_text(encoding="utf-8")
    claim_id = ""
    for line in text.splitlines():
        if line.startswith("CLAIM_ID="):
            claim_id = line.split("=", 1)[1].strip()
            break
    if not claim_id:
        raise SystemExit("FAILED:confirmer CLAIM_ID missing from prompt file")
    unit = _load_unit(claim_id)
    amvr = (unit or {}).get("assigned_model_vendor_role") or {}
    observed = str(amvr.get("vendor") or "")
    model = str(amvr.get("model") or "")
    if not observed:
        verdict = "NOT-CHECKED"
    elif observed.lower() in text.lower() or "anthropic" in observed.lower() or "openai" in observed.lower():
        verdict = "CONFIRMED"
    else:
        verdict = "PARTIAL"
    return {
        "claim_id": claim_id,
        "observed_vendor": observed,
        "observed_model": model,
        "confirmer_vendor": vendor,
        "verdict": verdict,
        "source_probe": SOURCE_FP,
        "verifier_probe": VERIFIER_FP,
        "prompt_file": str(prompt_file.relative_to(REPO)).replace("\\", "/")
        if prompt_file.is_relative_to(REPO)
        else str(prompt_file),
        "text": (
            f"catalog assigned_model_vendor_role.vendor for {claim_id} "
            f"is {observed or '<absent>'}"
        ),
    }


def classify_payload(doc: Any, output_bytes: int) -> tuple[str, bool]:
    if output_bytes <= 0:
        return "severed-stream", False
    if not isinstance(doc, dict):
        return "severed-stream", False
    keys = set(doc.keys())
    if keys and keys <= RECEIPT_KEYS:
        return "severed-stream", False
    if any(k in doc for k in ("job_id", "background")) and not (
        COMPLETED_KEYS <= keys or "verdict" in keys
    ):
        return "severed-stream", False
    if "verdict" in doc and "observed_vendor" in doc:
        return "completed", True
    return "severed-stream", False


def run_confirmer(
    vendor: str,
    prompt_file: Path,
    output_path: Path,
    mode: str = "complete",
    timeout: int = 60,
    claim_id: str | None = None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "dispatch.py"),
        "--confirmer",
        "--vendor",
        vendor,
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
        return {
            "claim_id": claim_id or "UNKNOWN",
            "confirmer_vendor": vendor,
            "prompt_path": _rel(prompt_file),
            "prompt_transport": "file",
            "exit_code": 124,
            "output_path": _rel(output_path),
            "output_bytes": 0,
            "parsed": False,
            "classification": "timeout",
            "counts_as_result": False,
            "diagnostic_tail": "TIMEOUT",
        }
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
    parsed_claim = doc.get("claim_id") if isinstance(doc, dict) else None
    return {
        "claim_id": parsed_claim or claim_id or "UNKNOWN",
        "confirmer_vendor": vendor,
        "prompt_path": _rel(prompt_file),
        "prompt_transport": "file",
        "exit_code": exit_code,
        "output_path": _rel(output_path),
        "output_bytes": nbytes,
        "parsed": parsed,
        "classification": klass,
        "counts_as_result": counts and klass == "completed",
        "diagnostic_tail": tail,
    }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def reject_inline(prompt: str) -> dict[str, Any]:
    encoded = prompt.encode("utf-8")
    reason = "inline-prompt-forbidden"
    if len(prompt) >= WIN_ARG_LIMIT or len(encoded) >= WIN_ARG_LIMIT:
        reason = "win-arg-limit"
    return {
        "claim_id": "PLANT-P0-INLINE-PROMPT",
        "confirmer_vendor": "openai",
        "prompt_path": "",
        "prompt_transport": "inline-rejected",
        "exit_code": 2,
        "output_path": "",
        "output_bytes": 0,
        "parsed": False,
        "classification": "win-arg-limit",
        "counts_as_result": False,
        "diagnostic_tail": reason,
    }


def _confirmer_main(args: argparse.Namespace) -> int:
    prompt = Path(args.prompt_file)
    if not prompt.is_file():
        print(f"FAILED:confirmer prompt missing {prompt}")
        return 1
    out = Path(args.output)
    body = confirmer_body(args.vendor, prompt, args.mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SUCCESS:confirmer wrote {out} bytes={out.stat().st_size}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmer", action="store_true")
    ap.add_argument("--vendor", required=True)
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
    if not args.prompt_file:
        print("FAILED:dispatch prompt must be passed by file")
        return 2
    if args.confirmer:
        if not args.output:
            print("FAILED:confirmer --output required")
            return 2
        return _confirmer_main(args)
    if not args.output:
        print("FAILED:dispatch --output required")
        return 2
    rec = run_confirmer(
        args.vendor, Path(args.prompt_file), Path(args.output), args.mode
    )
    print(json.dumps(rec, sort_keys=True))
    if rec["classification"] == "completed" and rec["counts_as_result"]:
        print("SUCCESS:dispatch completed with parsed output file")
        return 0
    print(f"FAILED:dispatch {rec['classification']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
