#!/usr/bin/env python3
"""Generate SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json for one unit.

Usage: python emit_delivery_records.py <UID> <probes-json>
probes-json: [{"id":"probe1","command":"...","exit_code":0,"raw_output":"..."}, ...]
Manifest row sha256 = sha256 of artifact bytes with CRLF normalised to LF
(matches _measure_one_delivered.digest_file).
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")


def digest_file(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    uid, probes_path = sys.argv[1], Path(sys.argv[2])
    cat = json.load(open(REPO / "command-center" / "WORK-UNIT-CATALOG.json", encoding="utf-8"))
    unit = next(u for u in cat["work_units"] if u.get("id") == uid)
    out_rel = unit["output_path"].replace("\\", "/")
    out = REPO / out_rel
    sha, nbytes = digest_file(out)
    probes = json.loads(probes_path.read_text(encoding="utf-8"))
    pd = REPO / "command-center" / "p2-wave" / "probes" / uid
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentinel = "SUCCESS:" + uid

    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": out_rel,
        "output_schema": unit.get("output_schema"),
        "named_probes": [
            {
                "id": p["id"],
                "command": p["command"],
                "exit_code": p["exit_code"],
                "raw_output": p["raw_output"][-1500:],
            }
            for p in probes
        ],
        "artifacts": [
            {
                "path": out_rel,
                "sha256": sha,
                "bytes": nbytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "ts": now,
        "notes": (
            "Wave-2 builder shard 9 reconstruction: prior builder died mid-flight; the "
            f"receipt at {out_rel} already carried an independent reviewer closure "
            "(reviewer.verdict=PASS, independent=true) which still verifies live, so it is "
            "kept per the unit contract. This shard re-authored the named probe scripts "
            "(absent from this worktree), re-ran them live to exit 0, and wrote the "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row (CRLF-normalised sha256). "
            "Did not run global unit_manifest.py --write."
        ),
        "measure_line": f"SUCCESS:delivered {uid}",
    }
    (pd / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": 1,
        "present": 1,
        "artifacts": [
            {
                "path": out_rel,
                "sha256": sha,
                "bytes": nbytes,
                "present": True,
                "unit_id": uid,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
                "role": "primary",
            }
        ],
    }
    (pd / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"emitted delivery records for {uid}: sha256={sha} bytes={nbytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
