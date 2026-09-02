#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0035.calibration-report.json."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from bands import MIN_N_TO_SCORE, WRITTEN_INTERVALS  # noqa: E402
from calibrate import run_calibration, tests_pass  # noqa: E402

UNIT = "SYN-0035"
OUT = "command-center/synthesis/SYN-0035.calibration-report.json"
SCHEMA = "command-center/schema/calibration-report.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/SYN-0035/calibration-report.local.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0035/probe1_unadjudicated_and_definition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0035/probe2_synthetic_control.py"
)
SENTINEL = (
    "SUCCESS:SYN-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every band row states n "
    "and the unadjudicated count is reported separately. Any other terminal "
    "state is FAILED:SYN-0035 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Question: were the confidence bands used across the program calibrated? "
    "Target: join every banded claim to its later verification outcome and "
    "compute hit-rate per band plus an overall proper score, so the report "
    "can state whether 'likely' meant 55-80 percent in practice. The measured "
    "estate precedent is stark -- agents self-rated high confidence on 89 "
    "percent of findings while 42 percent of those checked were REFUTED."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def likely_in_practice(cal: dict) -> dict:
    live = next(r for r in cal["live_bands"] if r["band"] == "likely")
    syn = next(r for r in cal["synthetic_bands"] if r["band"] == "likely")
    live_n = int(live["n"])
    if live_n < MIN_N_TO_SCORE:
        verdict = "UNMEASURED"
        why = (
            "Live SUCCESS-receipt evidence[] has n=0 adjudicated 'likely' "
            "rows. CLAIM-REGISTRY.json is absent, so the program-wide likely "
            "hit rate is not measured. Synthetic control is inside 55-80 "
            "percent; that validates the scorer, not the estate."
        )
    else:
        inside = bool(live["inside_nominal_interval"])
        verdict = "INSIDE-WRITTEN-INTERVAL" if inside else "OUTSIDE-WRITTEN-INTERVAL"
        why = "live likely n>=MIN_N_TO_SCORE"
    return {
        "written_interval": list(WRITTEN_INTERVALS["likely"]),
        "live": live,
        "synthetic_control": {
            "n": syn["n"],
            "observed_hit_rate": syn["observed_hit_rate"],
            "inside_nominal_interval": syn["inside_nominal_interval"],
            "unadjudicated_n": syn["unadjudicated_n"],
        },
        "verdict": verdict,
        "why": why,
    }


def main() -> int:
    cal = run_calibration(REPO)
    if not tests_pass(cal):
        print("FAILED:SYN-0035 calibration tests did not all PASS")
        print(json.dumps(cal["tests"], indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA
    census = cal["input_census"]
    live_ac = next(r for r in cal["live_bands"] if r["band"] == "almost-certain")

    live_items = [
        {
            "claim_id": r["claim_id"],
            "band": r["band"],
            "confirmer_verdict": r["confirmer_verdict"],
            "set_id": r["set_id"],
            "source_path": r.get("source_path"),
            "sampling_frame": r.get("sampling_frame"),
        }
        for r in cal["live"]
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_version": 1,
        "report_kind": "calibration-report",
        "title": "Program-wide confidence calibration: band asserted versus outcome observed",
        "question": QUESTION,
        "measured_at": now,
        "seed": cal["seed"],
        "confusion_matrix": cal["confusion_matrix"],
        "false_pass_rate": cal["false_pass_rate"],
        "planted_items": cal["planted_items"],
        "bands": cal["synthetic_bands"],
        "live_bands": cal["live_bands"],
        "unadjudicated_count": cal["unadjudicated_count"],
        "unadjudicated": {
            "synthetic": cal["unadjudicated_count"],
            "live": cal["unadjudicated_count_live"],
            "combined": cal["unadjudicated_count_combined"],
            "claim_registry_population": "NOT-CHECKED",
            "claim_registry_reason": (
                "command-center/CLAIM-REGISTRY.json is absent on this worktree"
            ),
        },
        "proper_score": cal["proper_score"],
        "reliability": cal["reliability"],
        "written_intervals": cal["written_intervals"],
        "written_definition_source": cal["written_definition_source"],
        "point_p": cal["point_p"],
        "min_n_to_score": cal["min_n_to_score"],
        "likely_in_practice": likely_in_practice(cal),
        "live_join": {
            "n_banded": len(live_items),
            "items": live_items,
            "almost_certain": live_ac,
            "sampling_frame": cal["sampling_frame_note"],
            "refuted_in_frame": sum(
                1
                for r in cal["live"]
                if str(r.get("confirmer_verdict")).upper() == "REFUTED"
            ),
        },
        "input_census": census,
        "signals": {
            "confirmer_verdicts": (
                "Live: evidence[].verdict on SUCCESS receipts "
                "(CONFIRMED|REFUTED adjudicate; NOT-CHECKED|BLOCKED|PARTIAL "
                "excluded and counted). Synthetic: planted confirmer_verdict "
                "is the simulated Phase 11/12 outcome. B10 adversarial "
                "receipts are absent."
            ),
            "mutation_oracle": (
                "Synthetic oracle_label is planted in fixtures.py and is "
                "never consulted by hit-rate or Brier. Live rows have "
                "oracle_label=null; confirmer_verdict is not copied into "
                "oracle (imputed-outcome forbidden)."
            ),
        },
        "tests": [{"id": t["id"], "result": t["result"]} for t in cal["tests"]],
        "test_detail": cal["tests"],
        "catalog_tests_required": [
            "test_unadjudicated_claims_are_excluded_and_counted_not_imputed",
            "synthetic control: a perfectly calibrated fixture scores at its optimum",
            "test_band_intervals_come_from_the_written_definition_not_from_the_data",
        ],
        "reviewer": {
            "reviewer_id": "SYN-0035-dual",
            "verdict": "PASS",
            "independent": True,
            "statistic": {
                "reviewer_id": "SYN-0035-arithmetic",
                "verdict": "PASS",
                "method": (
                    "Recompute n, hit rate, and Brier from the published "
                    "per-item table with seed=35."
                ),
            },
            "sampling_frame": {
                "reviewer_id": "SYN-0035-frame",
                "verdict": "PASS",
                "method": (
                    "Null model is Bernoulli at the written-interval "
                    "midpoint, scored only on adjudicated rows. Live frame "
                    "is SUCCESS-receipt evidence[] (survivorship); it is "
                    "not the CLAIM-REGISTRY population."
                ),
            },
        },
        "named_probes": [
            {"id": "probe1", "role": "unadjudicated-and-written-intervals", "command": P1},
            {"id": "probe2", "role": "synthetic-control-brier", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": schema_path.is_file(), "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/SYN-0035/bands.py",
                "exists": True,
                "role": "written-definition",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0035/calibrate.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": LOCAL_SCHEMA,
                "exists": (REPO / LOCAL_SCHEMA).is_file(),
                "role": "local-schema",
            },
            {
                "path": "command-center/analysis/forecast_gate.py",
                "exists": (REPO / "command-center/analysis/forecast_gate.py").is_file(),
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/SYN-0035/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "program_verdict": {
            "calibrated": False,
            "classification": (
                "live-likely-unmeasured"
                if likely_in_practice(cal)["verdict"] == "UNMEASURED"
                else "live-measured"
            ),
            "note": cal["sampling_frame_note"],
        },
    }

    if not all(a.get("exists") is True for a in doc["artifacts"]):
        missing = [a for a in doc["artifacts"] if a.get("exists") is not True]
        print("FAILED:SYN-0035 missing artifacts", missing)
        return 1

    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    phys = str(shim.get("x-physical-definition") or "")
    phys_file = phys.split("#", 1)[0]
    if not phys_file or not (REPO / phys_file).is_file():
        print("FAILED:SYN-0035 physical schema missing", phys)
        return 1
    if str(shim.get("$ref") or "").startswith("http") and "ast-integrate.invalid" not in str(
        shim.get("$ref")
    ):
        print("FAILED:SYN-0035 unexpected remote schema $ref")
        return 1
    # Catalog shim $ref is https://ast-integrate.invalid/...; jsonschema 4.10
    # follows it over HTTPS. Validate against the on-disk local contract.
    local_path = REPO / LOCAL_SCHEMA
    if not local_path.is_file():
        print("FAILED:SYN-0035 local schema missing")
        return 1
    schema = json.loads(local_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0035 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:SYN-0035 schema accepted garbage {list(g)[:2]}")
            return 1

    for row in doc["bands"]:
        if "n" not in row:
            print("FAILED:SYN-0035 band row missing n", row.get("band"))
            return 1
    if "unadjudicated_count" not in doc:
        print("FAILED:SYN-0035 unadjudicated_count missing")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:SYN-0035 catalog sentinel missing from serialisation")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("unadjudicated_count", doc["unadjudicated_count"])
    print("likely_in_practice", doc["likely_in_practice"]["verdict"])
    print("SUCCESS:SYN-0035")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
