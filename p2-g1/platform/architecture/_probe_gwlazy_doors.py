#!/usr/bin/env python3
"""Enumerate the ACTUAL registered commands per event so the migration section can say
exactly which registrations the gateway must absorb and which must stay carved out.

Terminal state: SUCCESS:gwlazy-doors / FAILED:gwlazy-doors <reason>
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_doors_out.json"
res: dict = {"probe": "gwlazy-doors"}

p = REPO / "agent-self/config/settings.json"
s = json.loads(p.read_text(encoding="utf-8"))

rows = {}
for ev, lst in (s.get("hooks") or {}).items():
    cmds = []
    if isinstance(lst, list):
        for entry in lst:
            matcher = (entry or {}).get("matcher")
            for h in (entry or {}).get("hooks", []) or []:
                cmd = h.get("command", "")
                # name the leaf script, not the whole command line
                m = re.findall(r"[\w\-./\\]+\.(?:py|ps1|sh|cmd|mjs|js)", cmd)
                leaf = Path(m[-1].replace("\\", "/")).name if m else cmd[:60]
                cmds.append({
                    "leaf": leaf,
                    "matcher": matcher,
                    "timeout": h.get("timeout"),
                    "is_dispatch_gateway": "dispatch.py" in cmd,
                })
    rows[ev] = cmds

res["events"] = rows
res["summary"] = {
    ev: {
        "registrations": len(c),
        "has_dispatch_gateway": any(x["is_dispatch_gateway"] for x in c),
        "non_gateway_leaves": sorted({x["leaf"] for x in c if not x["is_dispatch_gateway"]}),
        "timeout_sum": sum(x["timeout"] or 0 for x in c),
    }
    for ev, c in sorted(rows.items())
}
res["totals"] = {
    "events": len(rows),
    "registrations": sum(len(c) for c in rows.values()),
    "events_with_gateway": sum(1 for c in rows.values() if any(x["is_dispatch_gateway"] for x in c)),
    "registrations_the_gateway_would_absorb": sum(
        1 for c in rows.values() for x in c if not x["is_dispatch_gateway"]
    ),
    "gateway_registrations": sum(1 for c in rows.values() for x in c if x["is_dispatch_gateway"]),
}

# the security carve-out: which leaves are BLOCKING guards that must NOT be absorbed
SECURITY = {"deny-credential-reads", "no-force-push", "deny_credential_reads", "guard.py"}
res["security_carveout_candidates"] = sorted(
    {
        x["leaf"]
        for c in rows.values()
        for x in c
        if any(k in x["leaf"] for k in ("deny", "force-push", "force_push", "credential"))
    }
)

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res["summary"], indent=2))
print(json.dumps(res["totals"], indent=2))
print("security carve-out candidates:", res["security_carveout_candidates"])
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-doors")
