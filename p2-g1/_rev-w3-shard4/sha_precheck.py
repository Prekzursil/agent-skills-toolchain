#!/usr/bin/env python3
"""Pre-check manifest + receipt sha rows against live artifacts (no probes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}

print(f"{'unit':9} {'live_bytes':>10} {'eol':5} {'manifest_row':14} {'receipt_row':14} {'min_bytes':>9}")
for uid in MY:
    e = byid[uid]
    out_rel = e["output_path"].replace("\\", "/")
    out_path = REPO / out_rel
    raw = out_path.read_bytes()
    live = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    man = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json")
                     .read_text(encoding="utf-8"))
    rows = [a for a in man.get("artifacts", [])
            if str(a.get("path", "")).replace("\\", "/") == out_rel]
    prim = [a for a in rows if a.get("role") == "primary"] or rows
    msha = (prim[0].get("sha256") if prim else None)
    rec = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
    rr = [a for a in (rec.get("artifacts") or [])
          if str(a.get("path", "")).replace("\\", "/") == out_rel]
    rsha = (rr[0].get("sha256") if rr else None)
    print(f"{uid:9} {len(raw):>10} {'CRLF' if b'\r\n' in raw else 'LF':5} "
          f"{'MATCH' if msha == live else 'MISMATCH':14} "
          f"{'MATCH' if rsha == live else 'MISMATCH':14} {rec.get('min_bytes_threshold'):>9}")
