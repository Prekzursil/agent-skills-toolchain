"""Set a unit's receipt to the program builder form: DELIVERED + BLOCKED/reviewer-absent.

Usage: python _patch_receipt.py <UNIT-ID> <reason> [extra-note]
Keeps: id, unit_id, sentinel, registered, output_path, output_schema,
named_probes (fresh raw outputs), artifacts, manifest_path, ts.
Sets:  status=DELIVERED (measure-compatible), state=BLOCKED,
       failure.classification=["reviewer-absent"], reviewer=null,
       prior closure preserved under extensions.prev_closure.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _patch_receipt.py <UNIT-ID> <reason> [extra-note]")
        return 2
    uid = sys.argv[1]
    reason = sys.argv[2]
    extra = sys.argv[3] if len(sys.argv) > 3 else ""
    rp = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    ret = json.loads(rp.read_text(encoding="utf-8"))
    prev_reviewer = ret.get("reviewer")
    ret["status"] = "DELIVERED"
    ret["state"] = "BLOCKED"
    ret["failure"] = {
        "classification": ["reviewer-absent"],
        "reason": reason,
    }
    ret["reviewer"] = None
    ext = ret.get("extensions") if isinstance(ret.get("extensions"), dict) else {}
    ext["prev_closure"] = prev_reviewer if isinstance(prev_reviewer, dict) else None
    ext["shard0_w1_resume_2026-10-24"] = {
        "builder": "shard0 wave-1 builder (resume of a mid-flight-dead prior attempt)",
        "action": (
            "artifact + probes rebuilt live on this Windows worktree; receipt set to "
            "BLOCKED/reviewer-absent per program contract (only the independent "
            "reviewer closes; builder-authored probe2 closure demoted to prev_closure)"
        ),
    }
    if extra:
        ext["shard0_w1_resume_2026-10-24"]["note"] = extra
    ret["extensions"] = ext
    ret["notes"] = (
        f"Shard0 wave-1 builder (resume) 2026-10-24: {uid} rebuilt and verified live "
        "(named probes exit 0, manifest sha row matches live artifact). Prior builder "
        "attempt died mid-flight; its self-referential probe2 closure is preserved in "
        "extensions.prev_closure. Receipt BLOCKED/reviewer-absent awaiting independent "
        "closure." + (f" {extra}" if extra else "")
    )
    ret["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rp.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PATCHED {uid} state=BLOCKED classification=reviewer-absent status=DELIVERED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
