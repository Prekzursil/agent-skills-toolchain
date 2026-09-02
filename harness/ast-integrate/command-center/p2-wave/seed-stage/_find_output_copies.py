#!/usr/bin/env python3
"""Find catalog output_path copies sitting inside probe dirs (wrong place)."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PROBES = REPO / "command-center" / "p2-wave" / "probes"
EXTRACT = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull" / "extracted"
DELTA = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull" / "extracted-delta"


def main() -> None:
    found_probe = found_extract = none = 0
    emit = 0
    samples = []
    for u in CATALOG.get("work_units") or []:
        uid = u["id"]
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if (REPO / rel).is_file():
            continue
        name = Path(rel).name
        probe = PROBES / uid
        hit = None
        if probe.is_dir():
            cand = probe / name
            if cand.is_file():
                hit = "probe-basename"
            else:
                for p in probe.rglob(name):
                    if p.is_file():
                        hit = "probe-rglob"
                        break
        if hit is None:
            for root in (EXTRACT, DELTA):
                hits = list(root.glob(f"*/probes/{uid}/{name}"))
                if hits:
                    hit = "extract"
                    break
        if (probe / "emit.py").is_file() or (probe / "write_receipts.py").is_file() or (probe / "emit_receipt.py").is_file():
            emit += 1
        if hit == "probe-basename" or hit == "probe-rglob":
            found_probe += 1
            if len(samples) < 8:
                samples.append((uid, rel, hit))
        elif hit == "extract":
            found_extract += 1
        else:
            none += 1
    print(f"missing_outputs copies_in_probe={found_probe} copies_in_extract={found_extract} none={none} have_emit={emit}")
    print("samples", samples)


if __name__ == "__main__":
    main()
