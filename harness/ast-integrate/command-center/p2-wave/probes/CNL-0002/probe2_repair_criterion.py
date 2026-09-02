#!/usr/bin/env python3
"""Probe 2: implement the losing tagged union far enough to show the predicted
failure, then show the two-schema repair at 0 errors, plus a vacuity control.

Independent of probe 1: this probe does not re-assert the 13-error headline
except as the negative control (the check must still FIRE on the mismatched
catalogue).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

from fixtures import write_all  # noqa: E402
from measure import (  # noqa: E402
    losing_tagged_union,
    negative_control_v1_still_fires,
    winning_two_schemas,
)

ART = REPO / (
    "command-center/design/council/"
    "CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md"
)
FIX = HERE / "fixtures"
SENT = "SUCCESS:CNL-0002"
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"


def n_errors(schema_name: str, inst_name: str) -> int:
    schema = json.loads((FIX / schema_name).read_text(encoding="utf-8"))
    inst = json.loads((FIX / inst_name).read_text(encoding="utf-8"))
    return len(list(Draft202012Validator(schema).iter_errors(inst)))


def main() -> int:
    write_all()
    lose = losing_tagged_union()
    win = winning_two_schemas()
    neg = negative_control_v1_still_fires()
    untagged = n_errors("tagged-union.schema.json", "catalogue-v1-mismatch.json")
    tagged = n_errors("tagged-union.schema.json", "catalogue-synthetic-tag.json")
    repaired = n_errors("catalogue.schema.json", "catalogue-repaired.json")
    charter = n_errors("v1-charter.schema.json", "charter-valid.json")
    bad = n_errors("catalogue.schema.json", "protocol-invalid.json")
    # protocol-invalid is not a catalogue root; count against $defs.protocol_record
    cat_schema = json.loads((FIX / "catalogue.schema.json").read_text(encoding="utf-8"))
    invalid = json.loads((FIX / "protocol-invalid.json").read_text(encoding="utf-8"))
    bad_rec = len(
        list(
            Draft202012Validator(cat_schema["$defs"]["protocol_record"]).iter_errors(
                invalid
            )
        )
    )
    print(
        json.dumps(
            {
                "probe": "probe2-repair-criterion",
                "untagged_union_errors": untagged,
                "synthetic_tag_union_errors": tagged,
                "repaired_catalogue_errors": repaired,
                "valid_charter_errors": charter,
                "invalid_protocol_errors": bad_rec,
                "negative_control_v1_errors": neg["error_count"],
                "protocol_records": win["protocol_records"],
                "preset_records": win["preset_records"],
            },
            sort_keys=True,
        )
    )
    if untagged < 1:
        print("FAILED:CNL-0002-probe2 tagged union accepted untagged catalogue")
        return 1
    if tagged != 0:
        print("FAILED:CNL-0002-probe2 synthetic tag did not satisfy union")
        return 1
    if not lose["cm01_rejected"]:
        print("FAILED:CNL-0002-probe2 C-M01 was accepted by file-grain union")
        return 1
    if repaired != 0 or charter != 0:
        print(f"FAILED:CNL-0002-probe2 winning option errors cat={repaired} charter={charter}")
        return 1
    if win["protocol_records"] != 58 or win["preset_records"] != 72:
        print(
            f"FAILED:CNL-0002-probe2 record sweep "
            f"{win['protocol_records']}/{win['preset_records']}"
        )
        return 1
    if win["protocol_nonzero"] or win["preset_nonzero"]:
        print("FAILED:CNL-0002-probe2 a reconstructed record failed its own schema")
        return 1
    if bad_rec < 1:
        print("FAILED:CNL-0002-probe2 invalid protocol produced 0 errors (vacuous)")
        return 1
    unused_bad = bad  # catalogue schema over a protocol record should also fail
    if unused_bad < 1:
        print("FAILED:CNL-0002-probe2 catalogue schema accepted a protocol-shaped invalid")
        return 1
    if not neg["fires"] or neg["error_count"] != 13:
        print("FAILED:CNL-0002-probe2 negative control did not fire at 13")
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0002-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENT not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0002-probe2 sentinel absent")
        return 1
    if doc.get("decision") != "TWO_SCHEMAS_PLUS_TYPED_REFERENCE_EDGE":
        print(f"FAILED:CNL-0002-probe2 decision {doc.get('decision')}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0002-probe2 self-declared {doc.get('state')}")
        return 1
    note_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    note_errs = list(Draft202012Validator(note_schema).iter_errors(doc))
    if note_errs:
        print("FAILED:CNL-0002-probe2 design note fails its schema")
        print(note_errs[0].message)
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = list(Draft202012Validator(note_schema).iter_errors(garbage))
    if not g_errs:
        print("FAILED:CNL-0002-probe2 design-note schema is vacuous")
        return 1
    print(
        "losing untagged rejected; synthetic tag accepted; "
        "two-schema 0 errors on 58+72; invalid record fires; "
        "negative control 13 errors on catalogue-as-charter"
    )
    print("SUCCESS:CNL-0002-probe2 repair criterion and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
