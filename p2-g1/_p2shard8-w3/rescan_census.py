#!/usr/bin/env python3
"""Dry census for CNF-0167 live_scan refresh (shard8-w3 builder 2026-10-26).
Mirrors the recorded derivation rules: declared receipt ts vs cited artifact
disk mtime, 2s skew, aware-UTC only. Classifies export-rewrite-explained
inversions as clock-artifact, not fabrication."""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKEW = 2.0
EXPORT_WINDOW = (datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc),
                 datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc))

def parse_ts(s):
    if not isinstance(s, str) or not s.strip():
        return None, "missing"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, "missing"
    if dt.tzinfo is None:
        return None, "naive"
    return dt.astimezone(timezone.utc), "ok"

inv_rows = []      # declared < mtime - skew
clock_rows = []    # declared > mtime + skew (receipt-vs-mtime)
missing, naive_ct = [], 0
scanned = 0
files = sorted((REPO / "command-center/receipts").glob("*.json"))
for f in files:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    scanned += 1
    subject = d.get("unit_id") or f.stem
    ts_raw = d.get("ts")
    if not isinstance(ts_raw, str) or not ts_raw.strip():
        ts_raw = (d.get("timestamps") or {}).get("ended_at")
    dt, how = parse_ts(ts_raw)
    if how == "missing":
        missing.append(subject); continue
    if how == "naive":
        naive_ct += 1; continue
    seen = set()
    for a in d.get("artifacts") or []:
        p = a.get("path")
        if not p or p in seen:
            continue
        seen.add(p)
        t = REPO / p
        if not t.is_file():
            continue
        mtime = datetime.fromtimestamp(t.stat().st_mtime, timezone.utc)
        delta = (mtime - dt).total_seconds()
        if delta > SKEW:
            export_explained = (dt < EXPORT_WINDOW[0]) and (EXPORT_WINDOW[0] <= mtime < EXPORT_WINDOW[1])
            inv_rows.append({
                "subject": subject, "receipt_ts": dt.isoformat().replace("+00:00", "Z"),
                "artifact_mtime": mtime.isoformat().replace("+00:00", "Z"),
                "cited_path": p, "export_explained": export_explained,
                "gap_seconds": round(delta, 3)})
        elif delta < -SKEW:
            clock_rows.append({"subject": subject, "cited_path": p,
                               "gap_seconds": round(delta, 3)})

genuine = [r for r in inv_rows if not r["export_explained"]]
expl = [r for r in inv_rows if r["export_explained"]]
print(f"scanned={scanned} missing_declared={len(missing)} naive={naive_ct}")
print(f"causal_inversion_rows={len(inv_rows)} export_explained={len(expl)} genuine={len(genuine)}")
print(f"clock_rows(other-direction)={len(clock_rows)}")
for r in genuine[:10]:
    print("  GENUINE:", json.dumps(r))
print("sample export-explained:", json.dumps(expl[:2], indent=1) if expl else "none")
