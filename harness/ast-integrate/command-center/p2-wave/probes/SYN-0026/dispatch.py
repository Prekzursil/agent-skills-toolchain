#!/usr/bin/env python3
"""Prompt-by-file second-vendor dispatch for SYN-0026.

A dispatch counts as a result only when ALL of:
  * prompt arrived by file (never argv inline)
  * process exit is recorded
  * output file exists, is non-empty, and parses as JSON
  * the JSON is not a job-receipt / progress-only stream

Exit 0 with only a receipt is severed-stream. The unit terminal state for
that case is FAILED, not SUCCESS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT_KEYS = frozenset(
    {"job_id", "status", "progress", "receipt", "queued", "background"}
)
COMPLETED_KEYS = frozenset({"verdict", "reviewer_vendor", "lens_id"})


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def parse_prompt(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def observe_output(rel: str) -> dict[str, Any]:
    path = REPO / rel.replace("\\", "/")
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "label": "LENS-OUTPUT-ABSENT",
            "present": False,
            "bytes": 0,
            "sha256": None,
            "parsed": False,
            "state": None,
            "excerpt": f"absent:{rel}",
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "label": "LENS-OUTPUT-UNPARSEABLE",
            "present": True,
            "bytes": len(raw),
            "sha256": sha,
            "parsed": False,
            "state": None,
            "excerpt": raw[:120].decode("utf-8", errors="replace"),
        }
    if not isinstance(doc, dict):
        return {
            "label": "LENS-OUTPUT-UNPARSEABLE",
            "present": True,
            "bytes": len(raw),
            "sha256": sha,
            "parsed": False,
            "state": None,
            "excerpt": "non-object JSON",
        }
    state = str(doc.get("state") or "").upper() or None
    label = state or "PRESENT-STATE-UNSTATED"
    return {
        "label": label,
        "present": True,
        "bytes": len(raw),
        "sha256": sha,
        "parsed": True,
        "state": state,
        "excerpt": f"state={state or '<none>'}",
    }


def confirmer_body(vendor: str, prompt_file: Path, mode: str) -> dict[str, Any]:
    if mode == "severed":
        return {
            "job_id": "job-planted-severed-SYN-0026",
            "status": "queued",
            "progress": "started in the background",
            "background": True,
        }
    fields = parse_prompt(prompt_file.read_text(encoding="utf-8"))
    lens_id = fields.get("LENS_ID") or ""
    rel = fields.get("OUTPUT_PATH") or ""
    author = (fields.get("AUTHOR_VENDOR") or "").strip().lower()
    wanted = (fields.get("REVIEWER_VENDOR") or vendor).strip().lower()
    if not lens_id or not rel:
        raise SystemExit("FAILED:confirmer LENS_ID or OUTPUT_PATH missing")
    if wanted != vendor.strip().lower():
        raise SystemExit("FAILED:confirmer --vendor does not match prompt REVIEWER_VENDOR")
    if author and author == vendor.strip().lower():
        raise SystemExit("FAILED:confirmer same-vendor review refused")
    obs = observe_output(rel)
    return {
        "lens_id": lens_id,
        "reviewer_vendor": vendor,
        "author_vendor": author,
        "verdict": obs["label"],
        "output_path": rel.replace("\\", "/"),
        "output_present": obs["present"],
        "output_bytes": obs["bytes"],
        "sha256": obs["sha256"],
        "parsed": obs["parsed"],
        "excerpt": obs["excerpt"],
        "prompt_file": _rel(prompt_file),
        "prompt_transport": "file",
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
        COMPLETED_KEYS <= keys
    ):
        return "severed-stream", False
    if COMPLETED_KEYS <= keys:
        return "completed", True
    return "severed-stream", False


def terminal_state(rec: dict[str, Any]) -> str:
    """Unit terminal state. Severed-stream is FAILED, never SUCCESS."""
    if (
        rec.get("counts_as_result") is True
        and rec.get("classification") == "completed"
        and         rec.get("parsed") is True
        and int(rec.get("exit_code", 1)) == 0
        and int(rec.get("output_bytes") or 0) > 0
    ):
        return "SUCCESS"
    return "FAILED"


def run_confirmer(
    vendor: str,
    prompt_file: Path,
    output_path: Path,
    mode: str = "complete",
    timeout: int = 60,
    lens_id: str | None = None,
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
            "lens_id": lens_id or "UNKNOWN",
            "reviewer_vendor": vendor,
            "prompt_path": _rel(prompt_file),
            "prompt_transport": "file",
            "exit_code": 124,
            "output_path": _rel(output_path),
            "output_bytes": 0,
            "parsed": False,
            "classification": "timeout",
            "counts_as_result": False,
            "terminal_state": "FAILED",
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
    parsed_lens = doc.get("lens_id") if isinstance(doc, dict) else None
    rec = {
        "lens_id": parsed_lens or lens_id or "UNKNOWN",
        "reviewer_vendor": vendor,
        "prompt_path": _rel(prompt_file),
        "prompt_transport": "file",
        "exit_code": exit_code,
        "output_path": _rel(output_path),
        "output_bytes": nbytes,
        "parsed": parsed,
        "classification": klass,
        "counts_as_result": bool(counts and klass == "completed"),
        "diagnostic_tail": tail,
    }
    rec["terminal_state"] = terminal_state(rec)
    return rec


def write_prompt(
    dest: Path,
    lens_id: str,
    output_rel: str,
    author_vendor: str,
    reviewer_vendor: str,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (
            f"LENS_ID={lens_id}\n"
            f"OUTPUT_PATH={output_rel}\n"
            f"AUTHOR_VENDOR={author_vendor}\n"
            f"REVIEWER_VENDOR={reviewer_vendor}\n"
            "TASK=independently re-observe the lens output_path; "
            "do not copy a sibling verdict.\n"
        ),
        encoding="utf-8",
    )
    return dest


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
        print("FAILED:dispatch inline prompt rejected")
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
    if rec["terminal_state"] == "SUCCESS":
        print("SUCCESS:dispatch completed with parsed output file")
        return 0
    print(f"FAILED:dispatch {rec['classification']} terminal={rec['terminal_state']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
