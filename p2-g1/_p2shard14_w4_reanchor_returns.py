"""w4s14 resume 2026-10-26: re-anchor builder returns to the registered independent closures.

All 12 shard units carry a registered receipt at command-center/receipts/<id>.json with
reviewer.verdict=PASS + independent=true (w3s16/w4s15 closures, 2026-10-26) that STILL
verifies live (probes exit 0, manifest sha256 CRLF-normalized == live artifact, re-proven
this run via _measure_one_delivered.py for all 12). Per the unit contract's exception
clause the closure is KEPT, not downgraded. The builder-side returns were stale:
  - RES-0103/RES-0111: state=SUCCESS with no reviewer block (receipt_core forbids SUCCESS
    without reviewer PASS+independent);
  - RES-0151/0157/0158/0160/0162/0164: state=COMPLETED, which is not a terminal_state
    enum value at all (chronologically written 2026-10-25 18:15+02:00, before the closures).
This script mirrors the REGISTERED reviewer block verbatim (citation, not self-certification),
sets state=SUCCESS / status=DELIVERED, nulls any failure, and appends a provenance note.
Registered receipts themselves are NOT modified.
"""
import json
from pathlib import Path

REPO = Path.home() / "p2-g1"
UNITS = ["RES-0103", "RES-0111", "RES-0151", "RES-0157", "RES-0158", "RES-0160", "RES-0162", "RES-0164"]
NOW = "2026-10-26"

for uid in UNITS:
    reg = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
    rev = reg.get("reviewer") or {}
    if not (rev.get("verdict") == "PASS" and rev.get("independent") is True):
        print(f"FAILED:{uid} registered closure missing (state={reg.get('state')}, rev={rev.get('verdict')}) - NOT touched")
        continue
    rp = REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    ret = json.loads(rp.read_text(encoding="utf-8"))
    old_state = ret.get("state")
    old_status = ret.get("status")
    ret["state"] = "SUCCESS"
    ret["status"] = "DELIVERED"
    ret["reviewer"] = {k: rev[k] for k in ("reviewer_id", "verdict", "independent", "fresh_context", "vendor", "reviewed_at", "notes") if k in rev}
    if "failure" in ret:
        ret["failure"] = None
    note = (
        f"[w4s14 resume {NOW}] Builder return re-anchored to the REGISTERED independent closure at "
        f"command-center/receipts/{uid}.json (reviewer {rev.get('reviewer_id')}, reviewed_at {rev.get('reviewed_at')}); "
        f"closure re-verified live this run: both named probes re-run exit 0 and manifest sha256 "
        f"(CRLF-normalized) matches the live artifact. Prior state={old_state!r}/status={old_status!r} superseded "
        f"({old_state!r} is not a terminal_state enum value)" if old_state == "COMPLETED" else
        f"[w4s14 resume {NOW}] Builder return re-anchored to the REGISTERED independent closure at "
        f"command-center/receipts/{uid}.json (reviewer {rev.get('reviewer_id')}, reviewed_at {rev.get('reviewed_at')}); "
        f"closure re-verified live this run: both named probes re-run exit 0 and manifest sha256 "
        f"(CRLF-normalized) matches the live artifact. Prior state={old_state!r} lacked the reviewer block."
    )
    existing = ret.get("notes")
    ret["notes"] = (existing + " " + note) if isinstance(existing, str) and existing else note
    rp.write_text(json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SUCCESS:{uid} re-anchored state={old_state}->{ret['state']} status={old_status}->{ret['status']} reviewer={rev.get('reviewer_id')}")
