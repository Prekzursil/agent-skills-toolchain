"""Shared helpers for the p2-g1-wave-a builder shard 8 lane.

Workspace layout mirrors the estate repo layout under the workspace root
(C:/Users/Prekzursil/p2-g1): command-center/receipts/<ID>.json,
command-center/p2-wave/probes/<ID>/, tools/workflow-foundry/.

Contract notes:
- Receipts validate against the estate resolver for
  command-center/schema/receipt.schema.json -> platform/schema/receipt.schema.json#/$defs/receipt_core.
- Builders never emit state=SUCCESS (receipt_core condition 9 requires an
  independent PASS reviewer); builders emit BLOCKED with
  failure.classification ["reviewer-absent"].
- UNIT-ARTIFACT-MANIFEST.json rows hash artifact bytes with CRLF normalized
  to LF before hashing (the _measure_one_delivered.py convention).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
ESTATE = Path(r"D:\opt\search-hub-pr310")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_sha256(data: bytes) -> str:
    """sha256 over bytes with CRLF normalized to LF (manifest contract)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    """Measure an artifact OFF DISK from the workspace root."""
    p = WORKSPACE / rel
    data = p.read_bytes() if p.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1),
        "sha256": raw_sha256(data),
        "exists": p.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256((method + "\x1f" + command).encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    assert role in ("source", "verifier")
    assert method in (
        "command", "file-read", "http", "process-table", "byte-compare",
        "schema-validate", "static-analysis", "manual-inspection",
        "test-run", "other",
    )
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:60000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def evidence(claim, verdict, anchor, probes, confidence=None):
    d = {"claim": claim, "verdict": verdict, "anchor": anchor, "probes": probes}
    if confidence:
        d["confidence"] = confidence
    return d


def control(cid, kind, description, fired_bad, silent_good, bad="", good=""):
    return {
        "id": cid,
        "kind": kind,
        "description": description,
        "fired_on_bad_state": bool(fired_bad),
        "silent_on_good_state": bool(silent_good),
        "bad_state_output": str(bad)[:8000],
        "good_state_output": str(good)[:8000],
    }


def test_result(tid, command, result, assertions=0, tail=""):
    return {
        "id": tid,
        "name": tid,
        "command": command,
        "result": result,
        "assertions": assertions,
        "output_tail": tail[:8000],
    }


def residual(claim, experiment, verdict="NOT-CHECKED"):
    return {"claim": claim, "verdict": verdict, "settling_experiment": experiment}


def run(cmd, cwd=None, timeout=300):
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd or WORKSPACE), capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after {}s: {}".format(timeout, " ".join(cmd))
    except OSError as e:
        return 127, "{}: {}".format(type(e).__name__, e)


_RESOLVER = None


def validate(doc, schema="command-center/schema/receipt.schema.json"):
    global _RESOLVER
    if _RESOLVER is None:
        p = ESTATE / "platform" / "lib" / "schema_resolver.py"
        sys.path.insert(0, str(p.parent))
        spec = importlib.util.spec_from_file_location("schema_resolver", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver"] = mod
        spec.loader.exec_module(mod)
        _RESOLVER = mod
    return _RESOLVER.validate_artifact(doc, schema)


def emit_receipt(
    unit_id, spec_anchor, artifacts_rels, evidence_items, tests, controls,
    residual_unknowns, report, started_at, gate_note=None, extra_reason="",
    execution_substrate="local-parallel", retry_policy=None, min_bytes=512,
):
    """Validate + write the receipt (state=BLOCKED, reviewer-absent)."""
    if retry_policy is None:
        retry_policy = ("two strikes then pivot; enumerate >=2 alternatives "
                        "before a third attempt (AGENTS.md 4b)")
    ended = now_iso()
    reason = (
        "Builder lane has no independent reviewer: receipt_core condition 9 requires "
        "reviewer.verdict=PASS with independent=true before state=SUCCESS, and a builder "
        "reviewing its own work is not review. Artifact built and live probes re-ran to "
        "exit 0; closure waits on the independent reviewer at the fan-in barrier."
    )
    if extra_reason:
        reason = extra_reason + " " + reason
    ext = {"wave": "p2-g1-wave-a", "shard": 8}
    if gate_note:
        ext["owner_gate"] = gate_note
    doc = {
        "schema_version": 1,
        "unit_id": unit_id,
        "state": "BLOCKED",
        "sentinel": ("FAILED:{u} SUCCESS withheld by builder lane: artifact built, live probes exit 0; "
                     "closure requires an independent PASS reviewer (receipt_core condition 9)").format(u=unit_id),
        "spec_anchor": spec_anchor,
        "min_bytes_threshold": min_bytes,
        "artifacts": [art(r) for r in artifacts_rels],
        "evidence": evidence_items,
        "tests": tests,
        "negative_controls": controls,
        "reviewer": {
            "reviewer_id": "unassigned-independent-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": "No independent reviewer exists inside the builder lane. "
                     "This receipt is offered for independent review, not self-closed.",
        },
        "timestamps": {"started_at": started_at, "ended_at": ended},
        "retry": {"count": 0, "policy": retry_policy},
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": reason,
            "blocked_on": "independent reviewer closure (fan-in reviewer lane)",
        },
        "residual_unknowns": residual_unknowns,
        "produced_by": {
            "vendor": "anthropic",
            "model": "claude-opus-5-5",
            "role": "implementer",
            "execution_substrate": execution_substrate,
        },
        "report": report,
        "extensions": ext,
    }
    errs = validate(doc)
    if errs:
        return {"ok": False, "errors": errs}
    out = WORKSPACE / "command-center" / "receipts" / (unit_id + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"ok": True, "path": str(out), "doc": doc}


def write_manifest(unit_id, rels, roles=None):
    """Write probes/<ID>/UNIT-ARTIFACT-MANIFEST.json with CRLF-normalized sha256 rows."""
    rows = []
    for rel in rels:
        p = WORKSPACE / rel
        data = p.read_bytes() if p.is_file() else b""
        rows.append({
            "path": rel,
            "bytes": len(data),
            "sha256": norm_sha256(data),
            "sha256_raw": raw_sha256(data),
            "eol": eol_of(data),
            "exists": p.is_file(),
            "role": (roles or {}).get(rel, "supporting"),
        })
    manifest = {
        "unit_id": unit_id,
        "manifest_version": 1,
        "hash_convention": ("sha256 over artifact bytes with CRLF normalized to LF before hashing "
                            "(matches _measure_one_delivered.py); sha256_raw is the unnormalized hash, "
                            "recorded for drift triage"),
        "workspace_root": str(WORKSPACE),
        "generated_at": now_iso(),
        "artifacts": rows,
    }
    out = WORKSPACE / "command-center" / "p2-wave" / "probes" / unit_id / "UNIT-ARTIFACT-MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"ok": True, "path": str(out), "rows": rows}
