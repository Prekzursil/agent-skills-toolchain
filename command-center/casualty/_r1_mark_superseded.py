"""Stamp ADV-LIVENESS.json and ADV-COMPLETENESS-CENSUS.json as SUPERSEDED.

Deliberately NOT deleting them: deleting the evidence of a defect is how the defect comes
back. But a reader must not be able to lift the 6 false CASUALTY verdicts out of the old
file without seeing why they are wrong, so the banner goes at the top of each document.
"""
import json
import os

CAS = r"C:/Users/Prekzursil/source/ast-integrate/command-center/casualty"

BANNERS = {
    "ADV-LIVENESS.json": {
        "_SUPERSEDED_BY": "command-center/casualty/ADV-LIVENESS-V2.json",
        "_SUPERSEDED_AT": "2026-08-12T09:40+03:00",
        "_DO_NOT_CITE": (
            "SIX of the eight CASUALTY verdicts in this file are FALSE: ADV-0031, ADV-0032, "
            "ADV-0035, ADV-0036, ADV-0039 and ADV-0042 are all complete 6/6 artifacts of "
            "40-166 KB. Cause: the generator (_probe_liveness.py:41-46) reads its G1 substance "
            "score out of a census FILE with no freshness check, so once a wave ages, every unit "
            "that was mid-flight when that census was written keeps its stale score of 0 while "
            "G2 and G3 both go true - and is silently promoted to dead. Only ADV-0021 and "
            "ADV-0022 are real casualties. Retained as evidence of the defect, not as a result."
        ),
    },
    "ADV-COMPLETENESS-CENSUS.json": {
        "_SUPERSEDED_BY": "command-center/casualty/ADV-COMPLETENESS-CENSUS-V2.json",
        "_SUPERSEDED_AT": "2026-08-12T09:40+03:00",
        "_DO_NOT_CITE": (
            "This census was taken at 2026-08-11T22:35Z, while the wave was still running. NINE "
            "units scored 0-1 here and had ALL completed by 06:35Z the next morning: ADV-0031, "
            "0032, 0035, 0036, 0037, 0039, 0040, 0041, 0042. The scores are not wrong for the "
            "instant they were taken - they are simply mid-flight, which is exactly the "
            "live-wave caveat the file itself carries. Do not treat any low score here as a "
            "casualty verdict."
        ),
    },
}

for name, banner in BANNERS.items():
    p = os.path.join(CAS, name)
    if not os.path.isfile(p):
        print(f"SKIP (absent): {name}")
        continue
    doc = json.load(open(p, encoding="utf-8"))
    if doc.get("_SUPERSEDED_BY"):
        print(f"already stamped: {name}")
        continue
    stamped = {**banner, **doc}
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(stamped, fh, indent=2)
    print(f"stamped: {name} -> superseded by {banner['_SUPERSEDED_BY']}")
print("SUCCESS:mark-superseded")
