r"""Shared helpers for the P2 build lane.

Deliberately a SINGLE loader for platform/lib/schema_resolver so the lane's units do not each
re-implement it (the repo dup-guard flagged exactly that). Receipt-shaped constructors here mirror
the field requirements measured off platform/schema/receipt.schema.json#/$defs/receipt_core.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
_RESOLVER = None


def resolver():
    """Load (once) the repo's own schema resolver. Raises if unavailable -- a build lane that
    cannot validate its own contract must FAIL, not silently emit unvalidated artifacts."""
    global _RESOLVER
    if _RESOLVER is None:
        p = REPO / "platform" / "lib" / "schema_resolver.py"
        sys.path.insert(0, str(p.parent))
        spec = importlib.util.spec_from_file_location("schema_resolver", p)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {p}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver"] = mod
        spec.loader.exec_module(mod)
        _RESOLVER = mod
    return _RESOLVER


def validate(doc: Any, schema: str) -> list[str]:
    return resolver().validate_artifact(doc, schema)


def eol_of(data: bytes) -> str:
    if b"\x00" in data[:8192]:
        return "BINARY"
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def art(rel: str, role: str = "supporting") -> dict:
    """Measure an artifact OFF DISK. A path in text is not proof a file exists."""
    p = REPO / rel
    data = p.read_bytes() if p.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1),
        "sha256": hashlib.sha256(data).hexdigest(),
        "exists": p.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int | None = None) -> dict:
    d = {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }
    if exit_code is not None:
        d["exit_code"] = exit_code
    return d


def evidence(
    claim: str, verdict: str, anchor: str, probes: list[dict], confidence: str | None = None
) -> dict:
    d = {"claim": claim, "verdict": verdict, "anchor": anchor, "probes": probes}
    if confidence:
        d["confidence"] = confidence
    return d


def control(
    cid: str, kind: str, description: str, fired_bad: bool, silent_good: bool, bad="", good=""
) -> dict:
    return {
        "id": cid,
        "kind": kind,
        "description": description,
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "bad_state_output": str(bad)[:16000],
        "good_state_output": str(good)[:16000],
    }


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> tuple[int, str]:
    """Run a command, return (exit_code, combined stdout+stderr). Never raises on non-zero."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def write_if_valid(doc: dict, rel_out: str, schema: str, *, also: list[str] = ()) -> int:
    """Write the artifact ONLY if it validates against its declared contract.

    An artifact that does not validate is reported FAILED and NOT persisted; persisting it would
    make this emitter the very 'guard that converts a bug into a green' the program is built to
    stop. `also` names extra schemas the document must additionally satisfy.
    """
    errs = validate(doc, schema)
    for extra in also:
        errs += [f"[{extra}] {e}" for e in validate(doc, extra)]
    if errs:
        print(f"FAILED:{doc.get('unit_id')} artifact does not satisfy its declared contract")
        for e in errs[:25]:
            print("   ", e)
        return 1
    out = REPO / rel_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    floor = doc.get("min_bytes_threshold", 1)
    if size < floor:
        print(f"FAILED:{doc.get('unit_id')} artifact {size}B below declared floor {floor}B")
        return 1
    print(f"  wrote {rel_out} ({size} B) VALID against {schema}")
    return 0
