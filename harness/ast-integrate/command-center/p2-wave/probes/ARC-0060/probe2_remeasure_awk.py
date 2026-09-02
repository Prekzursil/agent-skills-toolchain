#!/usr/bin/env python3
"""Probe 2: mechanically different remeasure (awk, different field) + threshold citation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

COST = REPO / "command-center/phase3/A9/COST.json"
TSV = HERE / "inventory.tsv"
SH = HERE / "probe2_remeasure.sh"


def main() -> int:
    if not TSV.is_file():
        print("FAILED:ARC-0060-probe2 inventory.tsv absent")
        return 1
    proc = subprocess.run(
        ["bash", str(SH)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(text)
    if proc.returncode != 0:
        print(f"FAILED:ARC-0060-probe2 awk rc={proc.returncode}")
        return 1

    parsed: dict[str, int] = {}
    for line in text.splitlines():
        if "=" in line and line.split("=", 1)[0] in {
            "awk_unique_ids",
            "awk_kind_sum",
            "awk_n_kinds",
        }:
            k, v = line.split("=", 1)
            parsed[k] = int(v.strip())

    cost = I.load_cost(COST)
    headline = int((cost.get("headline") or {}).get("value"))
    id_count = parsed.get("awk_unique_ids")
    kind_sum = parsed.get("awk_kind_sum")
    print(
        f"python_headline={headline} awk_ids={id_count} awk_kind_sum={kind_sum}"
    )
    if id_count != headline:
        print(
            "FAILED:ARC-0060-probe2 readings disagree "
            f"python_ids={headline} awk_ids={id_count}"
        )
        return 1
    if kind_sum != headline:
        print(
            "FAILED:ARC-0060-probe2 readings disagree "
            f"awk_ids={id_count} awk_kind_sum={kind_sum}"
        )
        return 1

    thr = cost.get("threshold") or {}
    cites = thr.get("citations") or []
    blob = json.dumps(cites)
    if "Miller" not in blob or "1956" not in blob:
        print("FAILED:ARC-0060-probe2 threshold missing Miller 1956 citation")
        return 1
    if "ARC-0059" not in blob and "ARC-0073" not in blob:
        print("FAILED:ARC-0060-probe2 threshold missing catalog spec citation")
        return 1
    kinds = {c.get("kind") for c in cites if isinstance(c, dict)}
    if "published-source" not in kinds or "spec-statement" not in kinds:
        print(f"FAILED:ARC-0060-probe2 citation kinds={kinds}")
        return 1
    if int(thr.get("value")) != 9:
        print(f"FAILED:ARC-0060-probe2 threshold value {thr.get('value')} != 9")
        return 1
    computed = headline > int(thr["value"])
    recorded = bool(thr.get("violated_by_hybrid"))
    if computed != recorded:
        print(
            f"FAILED:ARC-0060-probe2 violated flag {recorded} != computed {computed}"
        )
        return 1
    print(
        f"threshold value={thr.get('value')} cited=True "
        f"hybrid={headline} violated={recorded}"
    )
    print("SUCCESS:ARC-0060-probe2 awk remeasure and threshold citation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
