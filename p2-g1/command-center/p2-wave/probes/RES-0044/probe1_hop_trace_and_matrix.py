#!/usr/bin/env python3
"""RES-0044 delivery predicate: hop-by-hop token-location trace + client matrix.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0044"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    tr = doc.get("hop_by_hop_token_location_trace") or {}
    hops = tr.get("hops") or []
    c.append(("hop trace complete with >=8 hops naming a storage location each",
              tr.get("complete") is True and len(hops) >= 8
              and all(str(h.get("storage_location") or "").strip() for h in hops),
              f"hops={len(hops)} complete={tr.get('complete')}"))
    cm = doc.get("client_matrix") or {}
    rows = cm.get("rows") or []
    ok_m = len(rows) >= 2
    for r in rows:
        if not r.get("full_flow_in_source"):
            continue  # partial/absent rows legitimately carry empty check maps
        ch = r.get("checks") or {}
        if not {"bearer_header", "pkce", "prm_discovery", "resource_indicator"} <= set(ch):
            ok_m = False
    c.append(("client matrix rows carry the four flow checks", ok_m, f"{len(rows)} rows"))
    full = [r.get("client") for r in rows if r.get("full_flow_in_source")]
    c.append(("at least two clients implement the full HTTP flow in captured source",
              len(full) >= 2, f"full-flow={full}"))
    cl = doc.get("claims") or []
    ok_r = len(cl) >= 4
    for x in cl:
        rails = x.get("rails") or []
        if len(rails) < 2:
            ok_r = False
            continue
        for r in rails:
            if not (str(r.get("permalink") or "").startswith("http")
                    and r.get("fetched_at") and r.get("http_status")
                    and (r.get("sha256") or r.get("decoded_sha256"))):
                ok_r = False
    c.append(("every claim carries >=2 rails with permalink+fetch-time+status+sha", ok_r,
              f"{len(cl)} claims"))
    tp = doc.get("this_program") or {}
    files = tp.get("mcp_json_files") or []
    c.append(("this program's MCP surface is STDIO-only (no url servers, all parseable)",
              bool(files) and all(f.get("parseable") for f in files)
              and not any(f.get("has_url_server") for f in files),
              f"{len(files)} .mcp.json files scanned"))
    ru = doc.get("residual_unknowns") or []
    c.append(("residual unknowns recorded", len(ru) >= 1, f"{len(ru)} entries"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
