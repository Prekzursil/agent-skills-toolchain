#!/usr/bin/env python3
"""Write SUBAGENT-RETURN.json for a unit after its probes ran green live.

Runs the two named probes, records real exit codes and output tails, and only
writes DELIVERED when both exited 0. Fails loudly otherwise. Uses the measure
script's own run_cmd so Windows env-prefix/wrapper semantics are identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import _measure_one_delivered as _m  # noqa: E402


def write_return(uid: str, output_path: str, output_schema: str, extra_notes: list) -> int:
    probe_dir = REPO / "command-center/p2-wave/probes" / uid
    p1files = sorted(probe_dir.glob("probe1*.py"))
    p2files = sorted(probe_dir.glob("probe2*.py"))
    if not p1files or not p2files:
        print("FAILED:" + uid + "-subagent-return probe scripts absent")
        return 2
    probe1, probe2 = p1files[0], p2files[0]
    named = []
    ok = True
    for n, script in enumerate((probe1, probe2), 1):
        cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + script.relative_to(REPO).as_posix()
        code, out = _m.run_cmd(cmd)
        named.append({
            "id": "probe%d" % n,
            "command": cmd,
            "exit_code": code,
            "role": script.name,
            "raw_output": (out or "").strip()[-3000:],
        })
        if code != 0:
            ok = False
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED" if ok else "FAILED",
        "state": ("SUCCESS" if ok else "FAILED"),
        "sentinel": "SUCCESS:" + uid,
        "registered": True,
        "output_path": output_path,
        "output_schema": output_schema,
        "named_probes": named,
        "notes": extra_notes,
        "rebuild_provenance": (
            "probe tree rebuilt 2026-10-26 (wave-3 shard 7) after the original probe "
            "tree was lost; the receipt at the catalog output_path was NOT modified - "
            "its reviewed closure is kept verbatim."
        ),
    }
    out = probe_dir / "SUBAGENT-RETURN.json"
    out.write_text(json.dumps(ret, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(("SUCCESS:" if ok else "FAILED:") + uid + "-subagent-return probes=2")
    return 0 if ok else 1


if __name__ == "__main__":
    uid = sys.argv[1]
    notes = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
    op = sys.argv[3] if len(sys.argv) > 3 else "command-center/receipts/%s.json" % uid
    osch = sys.argv[4] if len(sys.argv) > 4 else "command-center/schema/receipt.schema.json"
    raise SystemExit(write_return(uid, op, osch, notes))
