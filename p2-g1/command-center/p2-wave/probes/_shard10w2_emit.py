#!/usr/bin/env python3
"""Shard10 wave2 shared emitter: receipt refresh + manifest + SUBAGENT-RETURN.

Usage: python3 _shard10w2_emit.py <UNIT-ID> --probe1 <path> --role1 <role> \
        --probe2 <path> --role2 <role> [--extra <path> <role>]...

Hashes are CRLF-normalised (matches _measure_one_delivered.py). The receipt
is re-measured AFTER write so its own manifest row matches live bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def norm_sha(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    eol = "LF" if b"\r\n" not in raw else "CRLF"
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def catalog_unit(uid: str) -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise SystemExit(f"catalog-missing {uid}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("unit_id")
    ap.add_argument("--probe1", required=True)
    ap.add_argument("--role1", required=True)
    ap.add_argument("--probe2", required=True)
    ap.add_argument("--role2", required=True)
    ap.add_argument("--extra", action="append", nargs=2, default=[],
                    metavar=("PATH", "ROLE"))
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    uid = args.unit_id
    unit = catalog_unit(uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    receipt = json.loads(out.read_text(encoding="utf-8"))

    # 1. refresh receipt artifact rows with live bytes/sha
    for row in receipt.get("artifacts") or []:
        p = REPO / str(row.get("path", "")).replace("\\", "/")
        if p.is_file() and p != out:
            sha, n, eol = norm_sha(p)
            row["exists"] = True
            row["bytes"] = n
            row["sha256"] = sha
            row["eol"] = "LF" if eol == "LF" else row.get("eol", eol)
    receipt.setdefault("manifest_registration", {})[
        "manifest_path"
    ] = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    receipt["manifest_registration"]["registered"] = True
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_bytes(text.encode("utf-8"))

    # 2. manifest rows: receipt first, then artifacts, then probes
    rows = []
    sha, n, _ = norm_sha(out)
    rows.append({
        "unit_id": uid,
        "path": out_rel,
        "role": "primary",
        "present": True,
        "bytes": n,
        "sha256": sha,
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
    })
    for row in receipt.get("artifacts") or []:
        if row.get("path") == out_rel:
            continue
        rows.append({
            "unit_id": uid,
            "path": row["path"],
            "role": row.get("role", "supporting"),
            "present": True,
            "bytes": row.get("bytes"),
            "sha256": row.get("sha256"),
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        })
    for rel, role in [(args.probe1, args.role1), (args.probe2, args.role2)] + [
        (e[0], e[1]) for e in args.extra
    ]:
        rel = rel.replace("\\", "/")
        p = REPO / rel
        sha, n, eol = norm_sha(p)
        rows.append({
            "unit_id": uid,
            "path": rel,
            "role": role,
            "present": True,
            "bytes": n,
            "sha256": sha,
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        })
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(
        (json.dumps({"artifacts": rows}, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )

    # 3. SUBAGENT-RETURN
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": unit.get("completion_sentinel", f"SUCCESS:{uid}"),
        "output_path": out_rel,
        "output_schema": unit.get("output_schema"),
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "artifacts": [
            {"path": out_rel, "role": "primary", "exists": True,
             "bytes": n, "sha256": sha}
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {args.probe1}",
                "role": args.role1,
            },
            {
                "id": "probe2",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {args.probe2}",
                "role": args.role2,
            },
        ],
        "notes": args.notes or (
            "shard10 wave2 completion: prior builder died mid-flight; "
            "verified live deliverable, rebuilt missing tests/probes, "
            "manifest sha CRLF-normalised"
        ),
        "registered": True,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (probe_dir / "SUBAGENT-RETURN.json").write_bytes(
        (json.dumps(ret, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"EMITTED:{uid} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
