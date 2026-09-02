#!/usr/bin/env python3
"""Probe 2: silent-substitution detector + independent gap recount + schema.

Does not call adapter.compute_gaps. Gap sets are recomputed from fixture dicts
via fixtures.expected_gaps. Disagreement with the artifact blocks the unit.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0126-cross-vendor-participant-adapter-boundary-and-loud-degrada.md"
)
SCHEMA = HERE / "note.schema.json"
SCHEMA_CATALOG = REPO / "command-center/schema/council-design-note.schema.json"


def work_sha() -> str:
    return hashlib.sha256(F.PARTIAL_WORK.replace(b"\r\n", b"\n")).hexdigest()


def independent_fires(result: dict, intended: dict) -> dict:
    """Second mechanism: identity tuple compare + verdict field, not adapter.seat_id."""
    seat = result.get("seat") or {}
    swapped = (
        str(seat.get("vendor_id") or ""),
        str(seat.get("model_id") or ""),
    ) != (
        str(intended.get("vendor_id") or ""),
        str(intended.get("model_id") or ""),
    )
    audit = result.get("audit") or []
    kinds = {str(e.get("kind") or "") for e in audit if isinstance(e, dict)}
    has_record = bool(kinds & {"SILENT_SUBSTITUTION_ATTEMPT", "LOUD_RESEAT", "LOUD_DEGRADATION"})
    success_after_swap = swapped and result.get("verdict") == "SUCCESS"
    missing_audit = swapped and not has_record
    claimed = result.get("interchangeability_claimed") is True
    fires = bool(success_after_swap or missing_audit or claimed)
    return {
        "fires": fires,
        "swapped": swapped,
        "success_after_swap": success_after_swap,
        "missing_audit": missing_audit,
        "claimed": claimed,
    }


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0126-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0126" not in text:
        print("FAILED:CNL-0126-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0126-probe2 self-declared {doc.get('state')}")
        return 1

    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    ids = [row["id"] for row in tax["categories"]]
    if ids != ["tool_access", "context_length", "structured_output"]:
        print(f"FAILED:CNL-0126-probe2 taxonomy ids {ids}")
        return 1
    if tax.get("closed") is not True:
        print("FAILED:CNL-0126-probe2 taxonomy not closed")
        return 1

    assumed = F.SPEC["assumed"]
    live_gaps = {}
    for name, seat in F.GAP_SEATS.items():
        g = F.expected_gaps(assumed, seat["advertised"])
        live_gaps[name] = g
        print(f"recount {name}: gaps={g}")
        if g != [name]:
            print(f"FAILED:CNL-0126-probe2 expected single gap {name} got {g}")
            return 1
    capable_gaps = F.expected_gaps(assumed, F.CAPABLE["advertised"])
    print(f"recount capable: gaps={capable_gaps}")
    if capable_gaps:
        print("FAILED:CNL-0126-probe2 capable is not empty")
        return 1

    scores = doc.get("fixture_scores") or {}
    for name, g in live_gaps.items():
        rec = scores.get(name) or {}
        if rec.get("gaps") != g:
            print(
                f"FAILED:CNL-0126-probe2 disagreement {name}.gaps "
                f"artifact={rec.get('gaps')} recount={g}"
            )
            return 1
    if (scores.get("capable") or {}).get("gaps") != []:
        print("FAILED:CNL-0126-probe2 capable gaps not empty in artifact")
        return 1

    want_sha = work_sha()
    art_sha = str(doc.get("partial_work_sha256") or "")
    if art_sha != want_sha:
        print(f"FAILED:CNL-0126-probe2 partial sha artifact={art_sha} recount={want_sha}")
        return 1

    planted = A.buggy_silent_success(F.CAPABLE, F.SUBSTITUTE)
    indep = independent_fires(planted, F.CAPABLE)
    via_adapter = A.silent_substitution_fires(planted, F.CAPABLE)
    print(
        f"PLANTED-BAD silent-swap SUCCESS: indep_fires={indep['fires']} "
        f"adapter_fires={via_adapter['fires']} swapped={indep['swapped']} "
        f"claimed={indep['claimed']}"
    )
    if not indep["fires"] or not via_adapter["fires"]:
        print("FAILED:CNL-0126-probe2 planted silent swap did not FIRE")
        return 1
    if indep["fires"] != via_adapter["fires"]:
        print("FAILED:CNL-0126-probe2 detector mechanisms disagree on planted-bad")
        return 1

    good = {
        "verdict": "SUCCESS",
        "seat": F.CAPABLE,
        "audit": [{"kind": "CAPABLE", "user_visible": True}],
        "interchangeability_claimed": False,
        "partial": {"present": True},
    }
    good_indep = independent_fires(good, F.CAPABLE)
    good_ad = A.silent_substitution_fires(good, F.CAPABLE)
    print(
        f"KNOWN-GOOD capable no-swap: indep_fires={good_indep['fires']} "
        f"adapter_fires={good_ad['fires']} (check SILENT on the state it must accept)"
    )
    if good_indep["fires"] or good_ad["fires"]:
        print("FAILED:CNL-0126-probe2 known-good was not SILENT")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnl0126-p2-") as td:
        honest = A.dispatch(
            F.SPEC,
            F.CAPABLE,
            F.SUBSTITUTE,
            F.PARTIAL_WORK,
            Path(td) / "swap",
            silent_swap=True,
        )
        honest_fire = A.silent_substitution_fires(honest, F.CAPABLE)
        preserved_swap = A.preservation_ok(honest, F.PARTIAL_WORK)
        print(
            f"HONEST adapter silent_swap attempt: verdict={honest.get('verdict')} "
            f"fires={honest_fire['fires']} preserved={preserved_swap}"
        )
        if honest.get("verdict") == "SUCCESS":
            print("FAILED:CNL-0126-probe2 honest adapter returned SUCCESS on swap")
            return 1
        if not preserved_swap:
            print("FAILED:CNL-0126-probe2 honest swap dropped the partial")
            return 1

    coverage_types = set()
    for name, g in live_gaps.items():
        coverage_types.update(g)
    coverage = len(coverage_types) / float(len(ids))
    shim_lpi = A.lpi(
        [{"loud": False, "preserved": False} for _ in live_gaps],
        silent_sub=True,
    )
    honest_lpi = A.lpi(
        [{"loud": True, "preserved": True} for _ in live_gaps],
        silent_sub=False,
    )
    print(
        f"coverage-only: coverage={coverage:.3f} shim_LPI={shim_lpi} "
        f"honest_LPI={honest_lpi} (coverage does not pass a silent shim)"
    )
    if coverage != 1.0:
        print("FAILED:CNL-0126-probe2 gap-type coverage is not 1.0")
        return 1
    if shim_lpi != 0.0 or honest_lpi != 1.0:
        print("FAILED:CNL-0126-probe2 LPI coverage-alone control broken")
        return 1
    meas = doc.get("measurement") or {}
    if meas.get("coverage_alone_insufficient") is not True:
        print("FAILED:CNL-0126-probe2 measurement missing coverage_alone_insufficient")
        return 1
    if float(meas.get("threshold_reject_below") or 0) != 1.0:
        print("FAILED:CNL-0126-probe2 threshold is not 1.0")
        return 1
    if abs(float(doc.get("measured_lpi") or -1) - 1.0) > 1e-12:
        print(f"FAILED:CNL-0126-probe2 artifact LPI {doc.get('measured_lpi')}")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0126", "state": "SUCCESS"},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            rejected += 1
            continue
        print(f"FAILED:CNL-0126-probe2 schema accepted garbage {garbage}")
        return 1
    if rejected != 3:
        print(f"FAILED:CNL-0126-probe2 garbage rejected {rejected}/3")
        return 1

    signed = A.owner_signed_cnl0126(REPO)
    owner_claim = None
    for row in (doc.get("evidence") or []) + (doc.get("claims") or []):
        blob = str(row.get("claim") or "") + " " + str(row.get("anchor") or "")
        if "OWNER-DECISIONS.md" in blob or "CNL-0126 sign-off" in blob:
            owner_claim = row
            break
    if owner_claim is None:
        print("FAILED:CNL-0126-probe2 owner sign-off claim missing")
        return 1
    if signed and owner_claim.get("verdict") != "CONFIRMED":
        print("FAILED:CNL-0126-probe2 CNL-0126 is in OWNER-DECISIONS.md but not CONFIRMED")
        return 1
    if not signed and owner_claim.get("verdict") not in {"REFUTED", "NOT-CHECKED"}:
        print("FAILED:CNL-0126-probe2 owner sign-off was not honestly recorded")
        return 1
    if "answers" not in doc or len(doc.get("answers") or {}) < 3:
        print("FAILED:CNL-0126-probe2 answers shape missing")
        return 1
    if len(doc.get("claims") or []) < 2:
        print("FAILED:CNL-0126-probe2 claims shape missing")
        return 1

    print("schema garbage rejected 3/3")
    print(
        "verbatim negative control: silent-substitution check FIRES on "
        "SUCCESS-after-unrecorded-reseat and is SILENT on capable identical-seat"
    )
    print("SUCCESS:CNL-0126-probe2 silent-substitution recount schema-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
