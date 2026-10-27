#!/usr/bin/env python3
"""CNF-0184 named probe 2 (wave-2 reconstruction): over-normalization + triple run.

  OVER-NORMALIZATION  a planted CLAIM-BODY change (alpha -> beta) must NOT be
                      absorbed by ANY named normalizer — a normalizer that
                      erases content differences turns real diffs into noise.
  CLASS FIRE          each normalizer DOES fold its own class (proves it is
                      live, not a stub).
  TRIPLE-RUN          the borderline clock-seconds reproduction is forced
                      through a THIRD run (recorded run_count=3).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "CNF-0184.json"

from normalizers import NORMALIZERS, over_normalization_control  # noqa: E402

CLASS_FIRE_FIXTURES = {
    "norm.timestamps.iso-and-labeled-unix": ("now_s=1750000000", "now_s=1750000001"),
    "norm.temp_paths.tmp-and-var-folders": ("/tmp/tmpAbc123", "/tmp/tmpXyz789"),
    "norm.ordering.json-sort-keys": ('{"b": 1, "a": 2}', '{"a": 2, "b": 1}'),
    "norm.seeds.labeled-draw": ("seed_draw=0.5", "seed_draw=0.9"),
    "norm.host_identifiers.labeled-host": ("host=alpha-box", "host=beta-box"),
}


def main():
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0184" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0184-probe2 sentinel absent")
        return 1
    rec_norm_ids = [n["id"] for n in (doc.get("normalizers") or [])]
    live_norm_ids = [n["id"] for n in NORMALIZERS]
    if sorted(rec_norm_ids) != sorted(live_norm_ids):
        print("FAILED:CNF-0184-probe2 normalizer id set drifted: " + json.dumps({"recorded": rec_norm_ids, "live": live_norm_ids}))
        return 1

    per_normalizer = []
    for n in NORMALIZERS:
        refused = over_normalization_control(n["fn"])
        fires = n["fn"](CLASS_FIRE_FIXTURES[n["id"]][0]) == n["fn"](CLASS_FIRE_FIXTURES[n["id"]][1])
        per_normalizer.append({
            "normalizer_id": n["id"],
            "class": n["class"],
            "planted_change": "CLAIM-BODY: alpha -> beta",
            "absorbed": not refused,
            "class_fixture_fired": fires,
        })
        if not refused or not fires:
            print("FAILED:CNF-0184-probe2 normalizer control " + json.dumps(per_normalizer[-1]))
            return 1

    # triple-run: borderline clock-seconds through a THIRD run
    outs = []
    for _ in range(3):
        p = subprocess.run(
            [sys.executable, "-c", "import time; print('now_s=' + str(int(time.time())))"],
            capture_output=True, text=True,
        )
        outs.append(p.stdout.strip())
        time.sleep(1.05)
    distinct = len(set(outs))
    if len(set(outs)) < 2:
        print("FAILED:CNF-0184-probe2 clock-seconds triple-run saw one value: " + json.dumps(outs))
        return 1

    report = {
        "probe": "probe2-over-normalization-and-triple-run",
        "unit_id": "CNF-0184",
        "per_normalizer": per_normalizer,
        "all_normalizers_refused_content": True,
        "triple_run": {"reproduction_id": "fam3.clock-seconds", "run_count": 3, "distinct_raw": len(set(outs)), "outputs": outs},
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0184-probe2 over-normalization control and triple-run")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
