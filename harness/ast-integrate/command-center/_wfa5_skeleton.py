"""build/wfa-5 : write the registry SKELETON immediately (write-as-you-go mandate).

Every slot is honestly UNKNOWN until measured. Re-run at each milestone.
"""

import json
import os

OUT = os.path.join(
    "C:/Users/Prekzursil/source/ast-integrate/platform/registry",
    "workflow-candidates-5.json",
)

os.makedirs(os.path.dirname(OUT), exist_ok=True)

DEATH_NOTE = (
    "If it still reads this way, the unit died before measuring anything and no "
    "verdict here may be cited."
)

records = []
for n in range(129, 161):
    records.append(
        {
            "id": "WFC-%04d" % n,
            "registry_index": n,
            "registry_slice": "workflow-candidates-5 (candidates 129-160 of the 160 floor)",
            "unit": "build/wfa-5",
            "status": "UNKNOWN - not yet measured",
            "name": "UNKNOWN - not yet measured",
            "provenance": "UNKNOWN - not yet measured",
            "license": "UNKNOWN - not yet measured",
            "license_source": "UNKNOWN - not yet measured",
            "maintenance_state": "UNKNOWN - not yet measured",
            "task_fit": "UNKNOWN - not yet measured",
            "stages": [],
            "roles": [],
            "tools": [],
            "stop_rules": [],
            "failure_behaviour": "UNKNOWN - not yet measured",
            "benchmark_evidence": "UNKNOWN - not yet measured",
            "classification": "UNKNOWN-NEEDS-PROBE",
            "classification_basis": "UNKNOWN - not yet measured",
            "distinctness": "UNKNOWN - not yet measured",
            "coverage_note": DEATH_NOTE,
        }
    )

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(records, fh, indent=1, ensure_ascii=True)
    fh.write("\n")

print("SKELETON written:", OUT, len(records), "slots, all UNKNOWN")
