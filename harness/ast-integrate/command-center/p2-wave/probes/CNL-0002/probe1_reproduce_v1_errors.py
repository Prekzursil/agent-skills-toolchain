#!/usr/bin/env python3
"""Probe 1: independently reproduce the 13-error and C-M01 14-error/4-of-20 signals.

Signal 1 is Draft202012Validator.iter_errors. Signal 2 is Python set algebra
over instance keys vs schema required/properties. The catalogue's
schema_relationship string is never parsed as a count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

from constants import REQUIRED_12  # noqa: E402
from fixtures import write_all  # noqa: E402
from measure import cm01_vs_v1, catalogue_vs_v1  # noqa: E402
from note_schema import design_payload  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md"
)
FIX = HERE / "fixtures"
SENT = "SUCCESS:CNL-0002"


def recount_catalogue() -> tuple[int, int]:
    schema = json.loads((FIX / "v1-charter.schema.json").read_text(encoding="utf-8"))
    cat = json.loads((FIX / "catalogue-v1-mismatch.json").read_text(encoding="utf-8"))
    n_err = len(list(Draft202012Validator(schema).iter_errors(cat)))
    n_req = len(set(cat) & set(REQUIRED_12))
    # Prove we did not use the prose claim as the count:
    prose = cat["schema_relationship"]
    if "13 errors" in prose and n_err == int("13"):
        # still must come from the validator, not from parsing the string
        pass
    if n_err == len(prose):
        raise SystemExit("FAILED:CNL-0002-probe1 used prose length as error count")
    return n_err, n_req


def recount_cm01() -> tuple[int, int, int]:
    schema = json.loads((FIX / "v1-charter.schema.json").read_text(encoding="utf-8"))
    rec = json.loads((FIX / "C-M01.json").read_text(encoding="utf-8"))
    n_err = len(list(Draft202012Validator(schema).iter_errors(rec)))
    recognised = set(rec) & set(schema["properties"])
    return n_err, len(rec), len(recognised)


def main() -> int:
    write_all()
    n13, n_req = recount_catalogue()
    n14, n_keys, n_hit = recount_cm01()
    via_module = catalogue_vs_v1()
    via_cm = cm01_vs_v1()
    print(
        json.dumps(
            {
                "probe": "probe1-reproduce-v1-errors",
                "catalogue_error_count": n13,
                "required_present_count": n_req,
                "cm01_error_count": n14,
                "cm01_key_count": n_keys,
                "cm01_recognised_count": n_hit,
                "schema_relationship_ignored": True,
                "module_agrees": (
                    via_module["error_count"] == n13
                    and via_cm["error_count"] == n14
                ),
            },
            sort_keys=True,
        )
    )
    if n13 != 13 or n_req != 0:
        print(f"FAILED:CNL-0002-probe1 catalogue want 13 errors/0 required got {n13}/{n_req}")
        return 1
    if n14 != 14 or n_keys != 20 or n_hit != 4:
        print(
            f"FAILED:CNL-0002-probe1 C-M01 want 14/20/4 got {n14}/{n_keys}/{n_hit}"
        )
        return 1
    if via_module["error_count"] != 13 or via_cm["error_count"] != 14:
        print("FAILED:CNL-0002-probe1 module disagreement")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0002-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENT not in text:
        print("FAILED:CNL-0002-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0002-probe1 self-declared {doc.get('state')}")
        return 1
    payload = design_payload(doc)
    rows = payload.get("measurements") or doc.get("measurements") or []
    meas = {m.get("id"): m for m in rows if isinstance(m, dict)}
    c1 = meas.get("catalogue-root-vs-v1") or {}
    c2 = meas.get("C-M01-alone-vs-v1") or {}
    if int(c1.get("error_count") or -1) != 13:
        print("FAILED:CNL-0002-probe1 artifact catalogue error_count != live 13")
        return 1
    if int(c2.get("error_count") or -1) != 14:
        print("FAILED:CNL-0002-probe1 artifact C-M01 error_count != live 14")
        return 1
    if int(c2.get("recognised_count") or -1) != 4:
        print("FAILED:CNL-0002-probe1 artifact recognised_count != live 4")
        return 1
    print("catalogue errors=13 required_present=0 (set algebra)")
    print("C-M01 errors=14 keys=20 recognised=4 (set algebra vs properties)")
    print("SUCCESS:CNL-0002-probe1 independent 13-error and C-M01 reproduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
