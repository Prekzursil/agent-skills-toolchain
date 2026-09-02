#!/usr/bin/env python3
"""Probe 2: known-good SILENT, numeric FP rate, independent recount, schema."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import recount as R  # noqa: E402
from detector import repo_root  # noqa: E402

OUT = HERE / "probe2-known-good.raw.json"
ART_REL = "command-center/design/council/CNL-0094-evidence-free-majority-blocker.md"
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0094/artifact.schema.json"
)
CLEAN = (
    "known-good-majority",
    "known-good-unanimous",
    "known-good-mixed",
    "known-good-close",
)
PLANTED = (
    "planted-empty",
    "planted-fabricated",
    "planted-digest",
    "planted-support-mismatch",
)


def main() -> int:
    built = F.build_all()
    repo = repo_root()
    art_path = repo / ART_REL
    schema_path = repo / SCHEMA_REL
    local_schema_path = repo / LOCAL_SCHEMA_REL
    if not art_path.is_file():
        print("FAILED:CNL-0094-probe2 artifact missing")
        return 1
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:CNL-0094-probe2 catalog schema missing")
        return 1
    if not local_schema_path.is_file():
        print("FAILED:CNL-0094-probe2 local discriminating schema missing")
        return 1
    json.loads(schema_path.read_text(encoding="utf-8"))

    clean_rows = []
    fires = 0
    for name in CLEAN:
        rec = R.recount(built[name])
        clean_rows.append(rec)
        if rec["fired"]:
            fires += 1
            print(f"FAILED:CNL-0094-probe2 clean {name} FIRED")
            print(json.dumps(rec, sort_keys=True)[:2000])
            return 1
        if not rec["silent"]:
            print(f"FAILED:CNL-0094-probe2 clean {name} not silent")
            return 1
    fp_rate = fires / float(len(CLEAN))

    planted_rows = []
    for name in PLANTED:
        rec = R.recount(built[name])
        planted_rows.append(rec)
        if not rec["fired"]:
            print(f"FAILED:CNL-0094-probe2 reviewer planted {name} silent")
            return 1
        if rec["outcome"] != "REJECT":
            print(
                f"FAILED:CNL-0094-probe2 reviewer planted {name} "
                f"outcome={rec['outcome']}"
            )
            return 1

    primary = clean_rows[0]
    if primary["outcome"] != "ADOPT":
        print(f"FAILED:CNL-0094-probe2 known-good outcome={primary['outcome']}")
        return 1

    mixed = clean_rows[2]
    if mixed["fired"]:
        print("FAILED:CNL-0094-probe2 mixed majority with some empty votes FIRED")
        return 1
    if mixed["outcome"] != "ADOPT":
        print(f"FAILED:CNL-0094-probe2 mixed outcome={mixed['outcome']}")
        return 1

    text = art_path.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0094" not in text:
        print("FAILED:CNL-0094-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0094-probe2 self-declared {st}")
        return 1

    schema = json.loads(local_schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0094-probe2 schema errors")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"nope": True}, {}, {"unit_id": "CNL-0094"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0094-probe2 schema accepted garbage {garbage}")
            return 1

    live_fp = float(doc.get("false_positive_rate"))
    if live_fp != fp_rate:
        print(f"FAILED:CNL-0094-probe2 artifact fp={live_fp} live={fp_rate}")
        return 1
    if not isinstance(doc.get("false_positive_rate"), (int, float)):
        print("FAILED:CNL-0094-probe2 false_positive_rate is not a number")
        return 1

    both = doc.get("both_states") or {}
    if both.get("fired_on_bad") is not True:
        print("FAILED:CNL-0094-probe2 artifact both_states.fired_on_bad is not true")
        return 1
    if both.get("silent_on_good") is not True:
        print("FAILED:CNL-0094-probe2 artifact both_states.silent_on_good is not true")
        return 1

    mutant = copy.deepcopy(doc)
    mutant.pop("machine_checkable_property", None)
    if not list(validator.iter_errors(mutant)):
        print("FAILED:CNL-0094-probe2 mutant without machine_checkable_property accepted")
        return 1
    mutant2 = copy.deepcopy(doc)
    mutant2["both_states"]["fired_on_bad"] = False
    if not list(validator.iter_errors(mutant2)):
        print("FAILED:CNL-0094-probe2 mutant fired_on_bad=false accepted by schema")
        return 1
    if (doc.get("reviewer") or {}).get("reran_both_states") is not True:
        print("FAILED:CNL-0094-probe2 reviewer did not re-run both-states")
        return 1
    if (doc.get("reviewer") or {}).get("independent") is not True:
        print("FAILED:CNL-0094-probe2 reviewer.independent is not true")
        return 1

    nc = doc.get("negative_control") or {}
    observed = str(nc.get("observed") or "")
    if "SILENT" not in observed.upper():
        print("FAILED:CNL-0094-probe2 negative_control.observed missing SILENT")
        return 1

    payload = {
        "probe": "probe2-known-good",
        "method": "sha256-join-without-detector.detect",
        "false_positive_rate": fp_rate,
        "clean_n": len(CLEAN),
        "clean_fires": fires,
        "planted_fires": sum(1 for r in planted_rows if r["fired"]),
        "known_good_silent": True,
        "known_good_outcome": primary["outcome"],
        "negative_control": {
            "id": "NC-EVIDENCED-MAJORITY",
            "result": "SILENT",
            "applied_to": "known-good-majority",
            "state_meant_to_reject": (
                "evidence-free majority (raw majority with zero counting ballots)"
            ),
            "verbatim": (
                "On known-good-majority (5 backed ADOPT vs 2 backed REJECT) the "
                f"independent recount fired={primary['fired']} silent="
                f"{primary['silent']} outcome={primary['outcome']} "
                f"raw_tally={primary['raw_tally']} counting_tally="
                f"{primary['counting_tally']}. The check is SILENT on the "
                "evidenced majority it is meant not to invert."
            ),
        },
        "backed_minority_not_discarded": all(
            r["outcome"] == "REJECT" for r in planted_rows
        ),
        "schema_ok": True,
        "schema_rejects_garbage": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True)[:3500])
    print(
        f"silent_on_good=True fp_rate={fp_rate} planted_reviewer_fires="
        f"{payload['planted_fires']}/4 schema_ok=True"
    )
    print("SUCCESS:CNL-0094-probe2 known-good SILENT independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
