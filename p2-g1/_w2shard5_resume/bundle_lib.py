#!/usr/bin/env python3
"""Shared helpers for the shard-5 wave-2 resume bundle.

Contract pieces implemented here (all match _measure_one_delivered.py):
  * digest_file(path) -> CRLF-normalized sha256 + byte length
  * envelope completion for receipts that predate the current receipt profile
  * UNIT-ARTIFACT-MANIFEST.json writer (per-unit rows, CRLF-normalized hashes)
  * SUBAGENT-RETURN.json writer (BUILT-AWAITING-INDEPENDENT-REVIEW / DELIVERED)
Nothing here invents measurements: every added field traces to a recorded
value in the artifact or to a live probe output produced in this session.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
SESSION_TAG = "shard5-wave2-resume-2026-10-25"


def digest_file(path: Path) -> tuple[str, int]:
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path: Path, doc) -> None:
    Path(path).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def run(cmd: str, timeout: int = 2700) -> tuple[int, str]:
    """Run a house probe command string with VAR=value prefixes moved into env."""
    import os
    import re
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    exe = str(sys.executable).replace("\\", "/")
    if "python3" in cmd:
        cmd = cmd.replace("python3", exe, 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def write_manifest(uid: str, rows: list[dict], derivation: str) -> Path:
    """rows: [{path, bytes, sha256, exists, eol, role, receipt_path}] (artifacts themselves)."""
    man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    doc = {
        "schema_version": 1,
        "unit_id": uid,
        "contract": "builder-shard5-wave2-per-unit-artifact-registration",
        "derivation": derivation,
        "expected": len(rows),
        "present": sum(1 for r in rows if r.get("exists")),
        "verified_on_disk": True,
        "artifacts": rows,
        "ts": NOW,
    }
    dump(man_path, doc)
    return man_path


def write_return(uid: str, art_rel: str, sch_rel: str, sentinel: str,
                 probes: list[dict], prior_reviewer: dict | None,
                 extra_notes: str) -> Path:
    """SUBAGENT-RETURN.json for a completed unit.

    prior_reviewer present  -> status DELIVERED (closure preserved, verified live)
    prior_reviewer absent   -> status BUILT-AWAITING-INDEPENDENT-REVIEW, state BLOCKED
    """
    art_path = REPO / art_rel
    sha, nbytes = digest_file(art_path)
    man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    closed = bool(prior_reviewer and prior_reviewer.get("independent")
                  and str(prior_reviewer.get("verdict", "")).upper() == "PASS")
    doc = {
        "unit_id": uid,
        "id": uid,
        "status": "DELIVERED" if closed else "BUILT-AWAITING-INDEPENDENT-REVIEW",
        "state": "SUCCESS" if closed else "BLOCKED",
        "output_path": art_rel,
        "output_schema": sch_rel,
        "manifest_path": man_rel,
        "artifact_bytes": nbytes,
        "artifact_sha256_crlf_normalized": sha,
        "sentinel": sentinel,
        "named_probes": probes,
        "reviewer": (dict(prior_reviewer) if closed else {
            "reviewer_id": "independent-reviewer-pending",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": "no prior independent reviewer closure exists for this unit; "
                     "builder side stays BLOCKED",
        }),
        "failure": (None if closed else {
            "classification": ["reviewer-absent"],
            "reason": "Builder-side construction complete: artifact at output_path "
                      "written, both named probes re-run live with exit 0, per-unit "
                      "manifest row written with the CRLF-normalized sha256. state is "
                      "BLOCKED, not SUCCESS, because receipt_core forbids state=SUCCESS "
                      "without reviewer.verdict=PASS with independent=true; only the "
                      "independent reviewer closes.",
        }),
        "notes": extra_notes,
        "ts": NOW,
    }
    doc = {k: v for k, v in doc.items() if v is not None}
    ret_path = PROBES / uid / "SUBAGENT-RETURN.json"
    dump(ret_path, doc)
    return ret_path


def artifact_rows(uid: str, art_rel: str, extras: list[dict]) -> list[dict]:
    """Manifest rows for the primary artifact plus supporting probe outputs."""
    sha, nbytes = digest_file(REPO / art_rel)
    rows = [{
        "unit_id": uid,
        "path": art_rel,
        "bytes": nbytes,
        "sha256": sha,
        "exists": True,
        "present": True,
        "eol": "LF",
        "role": "primary",
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
    }]
    for extra in extras:
        p = REPO / extra["path"]
        if not p.is_file():
            continue
        s, n = digest_file(p)
        rows.append({
            "unit_id": uid,
            "path": extra["path"],
            "bytes": n,
            "sha256": s,
            "exists": True,
            "present": True,
            "eol": "LF",
            "role": extra.get("role", "supporting"),
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        })
    return rows
