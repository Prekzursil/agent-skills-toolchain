"""Shared helpers for wave-2 shard 7 (2026-10-25): per-unit manifest writer,
SUBAGENT-RETURN writer, probe runner, receipt save gate.

Mirrors the conventions measured on the delivered green units (BLD-0044/0045,
CC-0003): per-unit UNIT-ARTIFACT-MANIFEST.json rows hash bytes with CRLF
normalized to LF before hashing; SUBAGENT-RETURN.json carries named_probes the
measure gate re-runs verbatim.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P2WAVE = REPO / "command-center" / "p2-wave"
if str(P2WAVE) not in sys.path:
    sys.path.insert(0, str(P2WAVE))
import _p2lib as P  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fp(method: str, command: str) -> str:
    return hashlib.sha256((method + "\x1f" + command).encode()).hexdigest()[:32]


def norm_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def run_probe(uid: str, script: str) -> tuple[int, str]:
    cmd = [sys.executable, "-B", str(REPO / "command-center/p2-wave/probes" / uid / script)]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def save_valid(doc: dict, receipt_rel: str, schema: str) -> int:
    """Persist ONLY a schema-valid receipt; refuse to write a broken one."""
    errs = P.validate(doc, schema)
    if errs:
        print("FAILED:%s receipt invalid against %s" % (doc.get("unit_id"), schema))
        for e in errs[:20]:
            print("  -", e[:220])
        return 1
    out = REPO / receipt_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote %s (%d B) schema-valid against %s" % (receipt_rel, out.stat().st_size, schema))
    return 0


def write_unit_manifest(uid: str, rows: list[tuple[str, str]]) -> Path:
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": 0,
        "artifacts": [],
    }
    for rel, role in rows:
        p = REPO / rel
        data = p.read_bytes() if p.is_file() else b""
        manifest["artifacts"].append(
            {
                "path": rel,
                "sha256": norm_sha(data) if data else "absent",
                "bytes": len(data),
                "present": p.is_file(),
                "unit_id": uid,
                "receipt_path": "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid,
                "role": role,
            }
        )
        if p.is_file():
            manifest["present"] += 1
    out = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print("wrote %s (%d rows, %d present)" % (out.name, len(rows), manifest["present"]))
    return out


def write_return(
    uid: str,
    output_path: str,
    output_schema: str,
    probes: list[dict],
    note: str = "",
) -> Path:
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:" + uid,
        "registered": True,
        "output_path": output_path,
        "output_schema": output_schema,
        "named_probes": probes,
        "wave2_completion": {
            "at": now_iso(),
            "by": "claude-opus-5-5 builder shard 7 wave 2 (P2 program)",
            "note": note,
        },
    }
    out = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
    out.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    print("wrote SUBAGENT-RETURN.json (%d named probes)" % len(probes))
    return out


def measure(uid: str) -> int:
    r = subprocess.run(
        [sys.executable, str(P2WAVE / "_measure_one_delivered.py"), uid],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=3600,
    )
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    tail = "\n".join(out.splitlines()[-4:])
    print(tail)
    return r.returncode
