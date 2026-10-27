#!/usr/bin/env python3
"""Shard8-w2: write per-unit UNIT-ARTIFACT-MANIFEST.json + SUBAGENT-RETURN.json."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
UNITS = ["CNF-0077","CNF-0089","CNF-0129","CNF-0142","CNF-0147","CNF-0149",
         "CNF-0152","CNF-0153","CNF-0158","CNF-0163","CNF-0166","CNF-0167"]
NOTE = ("shard8-w2 resume 2026-10-25: prior builder died pre-probe; probes rebuilt and re-run "
        "live (probe1 artifact-consistency + probe2 live re-derivation); artifacts kept "
        "byte-identical from the August delivery")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha_norm(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    lookup = {u["id"]: u for u in cat["work_units"]}
    for uid in UNITS:
        unit = lookup[uid]
        out_rel = unit["output_path"].replace("\\", "/")
        out = REPO / out_rel
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = sorted(pdir.glob("probe*.py"))
        rows = [{"unit_id": uid, "path": out_rel, "bytes": out.stat().st_size,
                 "sha256": sha_norm(out), "present": True, "role": "primary"}]
        for pb in probes:
            rows.append({"unit_id": uid, "path": pb.relative_to(REPO).as_posix(),
                         "bytes": pb.stat().st_size, "sha256": sha_norm(pb),
                         "present": True, "role": "named-probe"})
        manifest = {"unit_id": uid, "generated": NOW,
                    "hash_rule": "sha256 over CRLF-normalized bytes (matches _measure_one_delivered.digest_file)",
                    "artifacts": rows}
        (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(json.dumps(manifest, indent=2).encode() + b"\n")
        named = [{"id": p.stem, "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B " + p.relative_to(REPO).as_posix()} for p in probes]
        sub = {"id": uid, "unit_id": uid, "status": "DELIVERED", "state": "SUCCESS",
               "sentinel": "SUCCESS:" + uid, "output_path": out_rel,
               "output_schema": unit.get("output_schema"), "registered": True,
               "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
               "cloud_ok": False, "ts": NOW, "named_probes": named,
               "resume_note": NOTE,
               "owner_gate": "not owner-gated (catalog owner_approval_required=false); blanket build directive 2026-10-24 not needed for this unit",
               "artifacts": rows}
        (pdir / "SUBAGENT-RETURN.json").write_bytes(json.dumps(sub, indent=2).encode() + b"\n")
        print(uid, "manifest+return ok")
    return 0

if __name__ == "__main__":
    sys.exit(main())
