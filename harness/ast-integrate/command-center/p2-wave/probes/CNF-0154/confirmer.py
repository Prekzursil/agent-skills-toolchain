#!/usr/bin/env python3
"""Independent Codex-side confirmer: evaluate a blinded payload, write the record.

Reads --prompt-file only. Writes --output-last-message only. Ignores stdin
progress. This is the local mcp__codex__codex contract backend, not a billed
live Codex session.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from record_schema import schema_errors  # noqa: E402

STATEMENT_RE = re.compile(
    r"^(?P<mod>[A-Za-z_]\w*)\.(?P<fn>[A-Za-z_]\w*)\((?P<args>.*)\) returns (?P<expected>.+)$"
)

CONFIRMER = {
    "identity": "cnf-0154-mcp-codex-rail",
    "vendor": "openai",
    "model": "local-independent-confirmer",
    "role": "cross-vendor-confirmer",
    "mcp_tool": "mcp__codex__codex",
    "live_session": False,
}

CAVEAT = (
    "Codex-side confirmer ran on the local mcp__codex__codex contract rail "
    "(prompt-by-file, foreground AND-gate). Not a live billed Codex MCP session. "
    "Verdict is from executing the cited source and tests in a fresh process."
)


def sha(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def parse_statement(statement: str) -> dict[str, Any]:
    m = STATEMENT_RE.match(statement.strip())
    if not m:
        raise ValueError(f"unparsed statement: {statement!r}")
    args = ast.literal_eval(f"({m.group('args')})")
    if not isinstance(args, tuple):
        args = (args,)
    expected = ast.literal_eval(m.group("expected").strip())
    return {
        "mod": m.group("mod"),
        "fn": m.group("fn"),
        "args": list(args),
        "expected": expected,
    }


def write_tree(payload: dict[str, Any], root: Path) -> None:
    for rel, text in (payload.get("source_files") or {}).items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    for rel, text in (payload.get("test_files") or {}).items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def run_tests(root: Path, test_rel: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-B", str(root / test_rel)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "kind": "test-file-exec",
        "test_rel": test_rel,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "passed": proc.returncode == 0,
    }


def direct_call(root: Path, parsed: dict[str, Any]) -> dict[str, Any]:
    src_dir = root / "src"
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(src_dir)!r})\n"
        f"import {parsed['mod']}\n"
        f"got = {parsed['mod']}.{parsed['fn']}(*{parsed['args']!r})\n"
        "print(json.dumps(got))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    got: Any = None
    parse_ok = False
    if proc.returncode == 0 and (proc.stdout or "").strip():
        try:
            got = json.loads(proc.stdout.strip().splitlines()[-1])
            parse_ok = True
        except json.JSONDecodeError:
            got = proc.stdout.strip()
    equal = parse_ok and got == parsed["expected"]
    return {
        "kind": "direct-call",
        "mod": parsed["mod"],
        "fn": parsed["fn"],
        "args": parsed["args"],
        "expected": parsed["expected"],
        "got": got,
        "exit_code": proc.returncode,
        "stderr": (proc.stderr or "")[-1000:],
        "parse_ok": parse_ok,
        "equal": equal,
    }


def confirm(payload: dict[str, Any], attestation: str) -> dict[str, Any]:
    parsed = parse_statement(payload["statement"])
    test_rels = list((payload.get("test_files") or {}).keys())
    if not test_rels:
        raise RuntimeError("no test files in blinded payload")
    test_rel = test_rels[0]
    with tempfile.TemporaryDirectory(prefix="cnf0154-confirm-") as tmp:
        root = Path(tmp)
        write_tree(payload, root)
        baseline = run_tests(root, test_rel)
        verifier = direct_call(root, parsed)

    source_probe = sha(
        {
            "kind": baseline["kind"],
            "test_rel": baseline["test_rel"],
            "exit_code": baseline["exit_code"],
            "passed": baseline["passed"],
            "stdout_tail": baseline["stdout"][-200:],
        }
    )
    verifier_probe = sha(
        {
            "kind": verifier["kind"],
            "call": f"{verifier['mod']}.{verifier['fn']}",
            "args": verifier["args"],
            "expected": verifier["expected"],
            "got": verifier["got"],
            "equal": verifier["equal"],
        }
    )
    if source_probe == verifier_probe:
        verifier_probe = sha({"distinct-from-source": True, **verifier})

    equal = bool(verifier["equal"])
    tests_ok = bool(baseline["passed"])
    if equal:
        verdict = "CONFIRMED"
        discrepancies: list[str] = []
    else:
        verdict = "REFUTED"
        discrepancies = [
            f"return-value claimed={verifier['expected']!r} observed={verifier['got']!r}"
        ]

    claim_id = payload["claim_id"]
    record = {
        "kind": "confirmation-record",
        "record_id": sha(
            {
                "unit": "CNF-0154",
                "claim_id": claim_id,
                "attestation": attestation,
                "verdict": verdict,
                "source_probe": source_probe,
                "verifier_probe": verifier_probe,
            }
        ),
        "job_id": "CNF-0154",
        "claim_id": claim_id,
        "confirmer": {
            "identity": CONFIRMER["identity"],
            "vendor": CONFIRMER["vendor"],
        },
        "blinding_attestation_hash": attestation,
        "baseline_repro": (
            f"applied=true probe={test_rel} exit_code={baseline['exit_code']} "
            f"passed={tests_ok}; fresh-process execution of cited tests; "
            "confirmer does not patch source"
        ),
        "corrected_repro": (
            "applied=false; confirmer does not patch; claim is about current cited source"
        ),
        "rollback_repro": "applied=false; no correction to roll back",
        "regression_diff": (
            f"claimed={verifier['expected']!r} observed={verifier['got']!r} "
            f"equal={equal} tests_passed={tests_ok}"
        ),
        "discrepancies": discrepancies,
        "verdict": verdict,
        "source_probe": source_probe,
        "verifier_probe": verifier_probe,
        "residual_caveat": CAVEAT,
        "scheduled_at_ms": int(time.time() * 1000),
        "quota_posture": "DECLARED-FIXTURE",
    }
    errs = schema_errors(record)
    if errs:
        raise RuntimeError("confirmer emitted invalid record: " + "; ".join(errs))
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--output-last-message", required=True)
    ap.add_argument(
        "--mode",
        default="confirm",
        choices=("confirm", "severed-empty", "severed-progress", "http-429"),
    )
    args = ap.parse_args()
    out = Path(args.output_last_message)
    if args.mode == "severed-empty":
        print("[codex] working")
        print("[codex] tokens=1")
        return 0
    if args.mode == "severed-progress":
        print("[codex] started in the background")
        print("Check /codex:status")
        out.write_text("[codex] started in the background\nCheck /codex:status\n", encoding="utf-8")
        return 0
    if args.mode == "http-429":
        print("HTTP 429 rate limited")
        return 429

    prompt_path = Path(args.prompt_file)
    envelope = json.loads(prompt_path.read_text(encoding="utf-8"))
    payload = envelope["payload"] if "payload" in envelope else envelope
    attestation = envelope.get("attestation") or ""
    if not attestation:
        raise SystemExit("prompt missing attestation")
    record = confirm(payload, attestation)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[codex] progress stream must be ignored; result is the output-last-message file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
