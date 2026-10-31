#!/usr/bin/env python3
"""Copy leftover catalog output_paths (and thin probe receipts) from extracted deltas."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
REPO = WAVE.parent.parent
PULL = WAVE / "ovh-monitor" / "delivery-pull"
LEFT = json.loads((WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json").read_text(encoding="utf-8"))
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PROBE_NAMES = ("SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json")


def main() -> int:
    ids = [i for i in (LEFT.get("remaining_ids") or []) if isinstance(i, str)]
    by = {u["id"]: u for u in CAT.get("work_units") or [] if isinstance(u, dict) and u.get("id")}
    boxes = [d / "delta" for d in PULL.iterdir() if d.is_dir() and (d / "delta").is_dir()]
    copied = 0
    probes = 0
    present = 0
    missing = []
    for uid in ids:
        rel = str((by.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        dest = REPO / rel if rel else None
        if dest is not None and dest.is_file() and dest.stat().st_size > 0:
            present += 1
        elif dest is not None:
            src_hit = None
            for box in boxes:
                cand = box / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    src_hit = cand
                    break
            if src_hit is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_hit, dest)
                copied += 1
                present += 1
            else:
                missing.append(uid)
        else:
            missing.append(uid)
        for name in PROBE_NAMES:
            dprobe = REPO / "command-center" / "p2-wave" / "probes" / uid / name
            if dprobe.is_file():
                continue
            for box in boxes:
                cand = box / "command-center" / "p2-wave" / "probes" / uid / name
                if cand.is_file() and cand.stat().st_size > 0:
                    dprobe.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, dprobe)
                    probes += 1
                    break
    all_present = 0
    for u in CAT.get("work_units") or []:
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if rel and (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0:
            all_present += 1
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "boxes": len(boxes),
        "leftover": len(ids),
        "leftover_present": present,
        "copied_outputs": copied,
        "copied_probes": probes,
        "leftover_missing": len(missing),
        "missing_ids": missing,
        "catalog_output_present": all_present,
        "catalog_units": len(CAT.get("work_units") or []),
    }
    out = WAVE / "ovh-monitor" / "leftover-local-census.json"
    out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(
        f"SUCCESS:merge leftover_present={present}/{len(ids)} copied={copied} "
        f"probes={probes} catalog_output={all_present}/{rec['catalog_units']} missing={len(missing)}",
        flush=True,
    )
    if missing:
        print("MISSING", " ".join(missing[:40]), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
