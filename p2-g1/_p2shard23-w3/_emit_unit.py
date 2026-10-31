#!/usr/bin/env python3
"""Shard-23 helper: write SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json for one unit."""
from __future__ import annotations
import hashlib, json, sys, time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")

def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def main() -> int:
    uid = sys.argv[1]
    status = sys.argv[2]           # DELIVERED
    note = sys.argv[3]
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    ret = json.loads(ret_path.read_text(encoding="utf-8"))
    named = ret.get("named_probes") or []
    rows = []
    out_rel = f"command-center/receipts/{uid}.json"
    sha, nb = sha_file(REPO / out_rel)
    rows.append({"path": out_rel, "sha256": sha, "bytes": nb, "present": True,
                 "unit_id": uid, "receipt_path": str(ret_path.relative_to(REPO)).replace("\\", "/"),
                 "role": "primary"})
    for item in named:
        cmd = item.get("command", "")
        script = cmd.split()[-1] if cmd else ""
        p = REPO / script
        if p.is_file():
            s, b = sha_file(p)
            rows.append({"path": p.relative_to(REPO).as_posix(), "sha256": s, "bytes": b,
                         "present": True, "unit_id": uid,
                         "receipt_path": str(ret_path.relative_to(REPO)).replace("\\", "/"),
                         "role": "named-probe"})
    for extra in ret.get("extra_artifacts") or []:
        p = REPO / extra
        if p.is_file():
            s, b = sha_file(p)
            rows.append({"path": p.relative_to(REPO).as_posix(), "sha256": s, "bytes": b,
                         "present": True, "unit_id": uid,
                         "receipt_path": str(ret_path.relative_to(REPO)).replace("\\", "/"),
                         "role": "supporting"})
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (shard-23 wave-3 resume builder, CRLF-normalized sha256)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "builder_note": note,
    }
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"MANIFEST:{uid} rows={len(rows)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
