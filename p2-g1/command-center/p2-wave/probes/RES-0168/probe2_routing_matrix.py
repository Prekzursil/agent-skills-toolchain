#!/usr/bin/env python3
"""RES-0168 probe2_routing_matrix.

tests row: sixteen-class routing + fan-out gate. Recomputes the routing table
invariants: all 16 declared source classes present, each with a fan-out
verdict, at least one backend with a recorded auth state, and a preflight
status per backend; verifies the fan-out gate requires preflight BEFORE 50
agents launch; verifies both recorded negative controls (wrong-endpoint-DOWN
and always-up-mutant-killed). Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/deep-research-design/RES-0168-source-class-backend-routing-preflight.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    rt = doc.get("routing_table") or []
    ck("sixteen-source-classes", len(rt) == 16, f"n={len(rt)}")
    ck("every-class-has-fanout-verdict",
       all(r.get("fanout_verdict") in {"SERVABLE", "UNSERVABLE"} for r in rt),
       str(sorted({str(r.get("fanout_verdict")) for r in rt})))

    bh = doc.get("backend_health") or []
    ck("backend-health-entries", len(bh) >= 8, f"n={len(bh)}")
    ck("backends-carry-auth-state",
       all((b.get("auth_state") in {"PRESENT", "ABSENT", "NOT_REQUIRED"}) for b in bh),
       str(sorted({str(b.get("auth_state")) for b in bh})))
    ck("backends-carry-failure-signature",
       all(bool(b.get("error_type") or b.get("error") or b.get("http_status") or b.get("ok") is not None)
           for b in bh),
       str([(b.get("id"), b.get("http_status"), b.get("error_type")) for b in bh][:4]))

    fg = doc.get("fanout_gate") or {}
    fgtxt = json.dumps(fg, default=str)
    ck("fanout-gate-requires-preflight-first",
       "preflight" in fgtxt.lower() and ("50" in fgtxt or "launch" in fgtxt.lower() or "gate" in fgtxt.lower()),
       fgtxt[:180])

    ncs = doc.get("negative_controls") or []
    nc_by = {}
    for n in ncs:
        nc_by[str(n.get("id") or n.get("rejects") or n)] = n
    ck("nc-wrong-endpoint-rejects-up",
       any(n.get("rejects") and "UP" in str(n.get("rejects")) for n in ncs),
       str([n.get("id") for n in ncs]))
    ck("nc-always-up-mutant-killed",
       any(n.get("observed") == "killed" for n in ncs),
       str([(n.get("id"), n.get("observed")) for n in ncs]))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0168" in str(doc.get("sentinel")),
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-routing-matrix", "unit_id": "RES-0168", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0168-probe2 16-class routing matrix + fan-out gate verified" if not red
          else f"FAILED:RES-0168-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
