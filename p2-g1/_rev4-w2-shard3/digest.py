#!/usr/bin/env python3
"""Compact per-unit digest from the round-4 battery output."""
import json
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
d = json.loads((REPO / "_rev4-w2-shard3" / "verify_out.json").read_text(encoding="utf-8"))
for uid in sorted(d):
    v = d[uid]
    probes = ",".join(
        q["script"].split("/")[-1].replace(".py", "") + "=" + str(q["exit"])
        + ("S" if q.get("ok_marker") else "")
        for q in v.get("probes") or [])
    print("%s | all=%s | self_row(bytes_ok=%s sha_ok=%s) | manifest=%s | adm=%s | schema=%s | gate=%s | probes[%s]=%s | sentinel_fail=%s self_decl=%d | reviewer=%s" % (
        uid, v.get("all_checks"),
        v["checks"].get("C6_receipt_selfrow"), v.get("sha_ok_receipt"),
        v["checks"].get("C5_manifest"),
        len(v.get("admission_errors") or []),
        str(v.get("schema_resolves")) + "/" + str(v.get("schema_artifact_errors_n")),
        len(v.get("gate_blocking_now") or []),
        probes, v["checks"].get("C7_probes_live"),
        v.get("sentinel_failed_marker"), len(v.get("self_decl_hits") or []),
        str((json.loads((REPO / 'command-center' / 'receipts' / (uid + '.json')).read_bytes().decode('utf-8-sig')).get('reviewer') or {}).get('reviewer_id'))[:45],
    ))
    if not v.get("all_checks"):
        print("    fail:", v.get("fail_checks"), "|", str(v.get("fail_reason"))[:220])
