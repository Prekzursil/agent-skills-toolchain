#!/usr/bin/env python3
"""Independent falsification of AUD-0072's headline count (attempt 2).

Catalog reviewer_requirement: "the reviewer must try to FALSIFY the headline
count before PASS, not re-read the artifact".

Instrument (mechanically different from storing numbers into the artifact):
  1. raw extraction rows re-pulled from the live corpus via the unit's corpus
     definition (extract_all - the corpus definition, NOT the stored result)
  2. classification re-done by THIS script's own mapper built from the
     artifact's declared phrase inventory (lexical_mapping rows + the live
     residue list), never by calling the engine's stored classify() output
  3. totals re-added by this script and compared to the artifact's headline
  4. arithmetic + file-set coherence checks

Exit 0 + SUCCESS marker iff every check survives.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
ART = REPO / "command-center/audit/AUD-0072-confidence-status-normalization.json"
ENGINE = REPO / "command-center/p2-wave/probes/AUD-0072/engine.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("aud0072_engine", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["aud0072_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    a = json.loads(ART.read_text(encoding="utf-8"))
    hc = a["headline_counts"]
    claimed = {
        "total": hc["expression_occurrences"],
        "mapped": hc["mapped_occurrences"],
        "residue": hc["residue_occurrences"],
        "bands": dict(hc["band_counts"]),
        "statuses": dict(hc["status_counts"]),
    }

    E = load_engine()
    rows = E.extract_all()  # raw, unclassified phrase rows from the live corpus
    print(f"raw extraction rows: {len(rows)}")

    # My own classifier, built from the artifact's DECLARED inventory.
    band_map: dict[str, str] = {}
    status_map: dict[str, str] = {}
    for r in a["lexical_mapping"]:
        ph = r["phrase"]
        if r.get("mapped"):
            if r.get("band"):
                band_map[ph] = r["band"]
            if r.get("status"):
                status_map[ph] = r["status"]
    live = E.normalize()
    residue_set = set(live["unique_residue_phrases"])

    my_bands: dict[str, int] = {}
    my_statuses: dict[str, int] = {}
    mapped = 0
    residue = 0
    for row in rows:
        ph = row.get("phrase") or ""
        if ph in residue_set or (ph not in band_map and ph not in status_map):
            residue += 1
            continue
        mapped += 1
        b = band_map.get(ph)
        if b:
            my_bands[b] = my_bands.get(b, 0) + 1
        s = status_map.get(ph)
        if s:
            my_statuses[s] = my_statuses.get(s, 0) + 1

    my_total = mapped + residue
    checks = {}
    checks["total"] = my_total == claimed["total"]
    checks["mapped"] = mapped == claimed["mapped"]
    checks["residue"] = residue == claimed["residue"]
    checks["bands"] = my_bands == claimed["bands"]
    checks["statuses"] = my_statuses == claimed["statuses"]

    print(f"my recount: total={my_total} mapped={mapped} residue={residue}")
    print(f"my bands:   {json.dumps(my_bands, sort_keys=True)}")
    print(f"my statuses:{json.dumps(my_statuses, sort_keys=True)}")
    for k, v in checks.items():
        print(f"check {k}: {'OK' if v else 'MISMATCH'}")

    verdict = all(checks.values())
    print(("SUCCESS:AUD-0072-reviewer-falsify headline count re-derived independently; claim survives"
           if verdict else "FAILED:AUD-0072-reviewer-falsify headline count did not survive re-derivation"))
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
