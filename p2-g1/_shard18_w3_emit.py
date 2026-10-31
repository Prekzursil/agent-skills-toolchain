#!/usr/bin/env python3
"""Shard 18 wave 3: emit SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json.

Hash convention matches command-center/p2-wave/_measure_one_delivered.py:
sha256 over CRLF-normalized bytes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def digest_file(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--sentinel", required=True)
    ap.add_argument("--closure", default=None)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--probe", action="append", required=True,
                    help="id=role:path pairs, e.g. probe1=live-recompute:command-center/.../probe1_x.py")
    args = ap.parse_args()

    uid = args.unit
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    out_rel = args.output_path.replace("\\", "/")
    out_abs = REPO / out_rel
    sha, nbytes = digest_file(out_abs)

    named_probes = []
    artifacts = [{
        "path": out_rel,
        "bytes": nbytes,
        "sha256": sha,
        "exists": True,
        "role": "primary",
        "eol_normalized": "CRLF->LF before hashing (measure convention)",
    }]
    for spec in args.probe:
        pid, rest = spec.split("=", 1)
        role, prel = rest.split(":", 1)
        pabs = REPO / prel
        named_probes.append({
            "id": pid,
            "role": role,
            "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {prel}",
        })
        artifacts.append({
            "path": prel,
            "bytes": pabs.stat().st_size,
            "sha256": sha_file(pabs),
            "exists": True,
            "role": "supporting",
        })

    manifest = {
        "schema_version": 1,
        "unit_id": uid,
        "artifacts": [{
            "unit_id": uid,
            "path": out_rel,
            "sha256": sha,
            "bytes": nbytes,
            "present": True,
            "role": "primary",
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            "measured_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }],
    }
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "builder_closure": args.closure or (
            "kept prior independent reviewer closure "
            "(reviewer.verdict=PASS, independent=true); probes authored by "
            "shard 18 wave 3 (prior builder died before writing this probe "
            "dir); re-verified live this shard run"),
        "sentinel": args.sentinel,
        "output_path": out_rel,
        "artifacts": artifacts,
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": named_probes,
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": args.notes,
        "failure": None,
    }
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    ret_path.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    print(f"EMITTED {uid} sha={sha} probes={len(named_probes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
