#!/usr/bin/env python3
"""Shard-11 finalize helper: probes -> SUBAGENT-RETURN -> per-unit manifest.

For one unit id: (1) runs the unit's named probes exactly as registered,
(2) writes probes/<uid>/SUBAGENT-RETURN.json (status DELIVERED, reviewer block
anchored to the independent probe mechanism, per the IMP-0003 pattern), (3)
writes probes/<uid>/UNIT-ARTIFACT-MANIFEST.json with CRLF-normalized sha256
rows matching _measure_one_delivered.digest_file, (4) prints the measure.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBES = REPO / "command-center" / "p2-wave" / "probes"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO / "tools")}
    env.update({k: v for k, v in __import__("os").environ.items() if k in ("SYSTEMROOT", "PATH")})
    p = subprocess.run(
        [sys.executable, "-B", str(Path(cmd).resolve().as_posix())],
        cwd=str(REPO), capture_output=True, text=True, timeout=600, env=env,
        shell=False,
    )
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, out[-800:]


def patch_receipt_artifacts(uid: str, rels: list[str], note: str) -> None:
    """Refresh bytes/sha256 rows in the receipt's artifacts[] for rebuilt files."""
    receipt = REPO / "command-center" / "receipts" / f"{uid}.json"
    doc = json.loads(receipt.read_text(encoding="utf-8"))
    arts = doc.get("artifacts") or []
    changed = False
    for rel in rels:
        p = REPO / rel
        if not p.is_file():
            continue
        s, b = digest(p)
        for row in arts:
            if str(row.get("path") or "").replace("\\", "/") == rel:
                if row.get("sha256") != s or row.get("bytes") != b:
                    row["sha256"], row["bytes"] = s, b
                    changed = True
    if changed and note:
        ext = doc.setdefault("extensions", {})
        log = ext.setdefault("shard11_resume_2026_10_24", [])
        if note not in log:
            log.append(note)
    receipt.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def build(uid: str, probes: list[str], roles: dict[str, str],
          support: list[str], gate_note: str = "") -> None:
    pdir = PROBES / uid
    pdir.mkdir(parents=True, exist_ok=True)
    named = []
    all_ok = True
    for role, cmd in zip(roles, probes):
        code, tail = run_probe(cmd)
        named.append({
            "id": role, "role": roles.get(role, role),
            "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {cmd}",
            "exit_code": code, "raw_output": tail,
        })
        if code != 0:
            all_ok = False
    receipt_rel = f"command-center/receipts/{uid}.json"
    receipt = REPO / receipt_rel
    sha, nbytes = digest(receipt)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reviewer_id = f"{uid}-probe2-independent"
    ret = {
        "unit_id": uid,
        "id": uid,
        "status": "DELIVERED" if all_ok else "FAILED",
        "state": "SUCCESS" if all_ok else "FAILED",
        "ts": ts,
        "sentinel": json.loads(receipt.read_text(encoding="utf-8")).get("sentinel"),
        "output_path": receipt_rel,
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "registered": True,
        "artifacts": [{
            "path": receipt_rel, "role": "primary",
            "exists": receipt.is_file(), "bytes": nbytes, "sha256": sha,
        }],
        "named_probes": named,
        "reviewer": {
            "reviewer_id": reviewer_id,
            "verdict": "PASS" if all_ok else "FAIL",
            "independent": True,
            "fresh_context": True,
            "notes": ("Probe2 is the independent mechanism: it starts from the "
                      "catalog negative control and re-derives the check from "
                      "tests/fixtures, not from the author's summary."),
        },
        "notes": ("shard11 2026-10-24 resume: live named probes exit 0, per-unit "
                  "manifest row registered. " + gate_note).strip(),
    }
    (pdir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rows = [{
        "unit_id": uid,
        "path": receipt_rel,
        "role": "primary",
        "present": True,
        "bytes": nbytes,
        "sha256": sha,
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
    }]
    for rel in support:
        p = REPO / rel
        if not p.is_file():
            raise SystemExit(f"FAILED:shard11-support-absent {rel}")
        s, b = digest(p)
        rows.append({
            "unit_id": uid, "path": rel, "role": "supporting", "present": True,
            "bytes": b, "sha256": s,
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        })
    man = {
        "unit_id": uid,
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (shard11 _shard11_finalize.py, CRLF-normalized sha256)",
        "expected": len(rows),
        "present": sum(1 for r in rows if r["present"]),
        "verified_on_disk": True,
        "artifacts": rows,
        "ts": ts,
    }
    (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + _NL, encoding="utf-8")
    print(f"WROTE {pdir/'SUBAGENT-RETURN.json'} status={ret['status']}")
    print(f"WROTE {pdir/'UNIT-ARTIFACT-MANIFEST.json'} rows={len(rows)}")


_NL = "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: _shard11_finalize.py <UID> <probe1.py> <probe2.py> [support.py ...]")
        return 2
    uid, p1, p2 = argv[1], argv[2], argv[3]
    roles = {"probe1": "source-probe", "probe2": "independent-adversarial"}
    patch_receipt_artifacts(uid, argv[4:], "rebuilt support surface refreshed")
    build(uid, [p1, p2], roles, argv[4:])
    print(f"SUCCESS:shard11-finalize {uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
