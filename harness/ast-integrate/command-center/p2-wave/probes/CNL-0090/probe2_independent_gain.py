#!/usr/bin/env python3
"""Probe 2: independent id-set gain vs Jaccard-backed detector.

Mechanically different from probe 1: this script never uses detect().fired
as its primary measurement. It recomputes G_t from claim_id/evidence_id
set difference only, then compares that curve to the detector.

On planted-paraphrase the two signals MUST diverge: id-set-only sees new
ids (would stay SILENT), the detector sees duplicate text and no new
evidence (FIRE). If they agree on paraphrase, the corroboration is inert
and the unit fails.

Negative control (verbatim): the productive fixture is the state the
check is meant to reject as circling — id-set and detector must both
stay SILENT there.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe2-independent-gain.raw.json"
ART = REPO / "command-center/design/council/CNL-0090-circular-debate-information-gain-per-round.md"
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"
SCHEMA_LOCAL = HERE / "artifact.schema.json"
SENTINEL = "SUCCESS:CNL-0090"

FIXTURES = {
    "loop": "planted_loop.json",
    "paraphrase": "planted_paraphrase.json",
    "productive": "clean_productive.json",
    "refinement": "clean_refinement.json",
}


def load(name: str) -> dict:
    return json.loads(D.fixture_path(name).read_text(encoding="utf-8"))


def curve_units(result: dict) -> list[int]:
    return [int(g["information_units"]) for g in result["gain_curve"]]


def main() -> int:
    docs = {k: load(v) for k, v in FIXTURES.items()}
    det = {k: D.detect(doc) for k, doc in docs.items()}
    ids = {k: D.id_set_gain(doc) for k, doc in docs.items()}

    # Primary independent measurement: id-set curves.
    print(
        "id-set loop",
        ids["loop"]["fired"],
        curve_units(ids["loop"]),
        "paraphrase",
        ids["paraphrase"]["fired"],
        curve_units(ids["paraphrase"]),
        "productive",
        ids["productive"]["fired"],
        curve_units(ids["productive"]),
        "refinement",
        ids["refinement"]["fired"],
        curve_units(ids["refinement"]),
    )
    print(
        "detector loop",
        det["loop"]["fired"],
        curve_units(det["loop"]),
        "paraphrase",
        det["paraphrase"]["fired"],
        curve_units(det["paraphrase"]),
        "productive",
        det["productive"]["fired"],
        curve_units(det["productive"]),
        "refinement",
        det["refinement"]["fired"],
        curve_units(det["refinement"]),
    )

    if not det["loop"]["fired"] or not det["paraphrase"]["fired"]:
        print("FAILED:CNL-0090-probe2 detector missed a planted pathology")
        return 1
    if det["productive"]["fired"] or det["refinement"]["fired"]:
        print("FAILED:CNL-0090-probe2 detector fired on known-good")
        return 1

    # Id-set-only must FIRE on verbatim loop (same ids) and SILENT on productive.
    if not ids["loop"]["fired"]:
        print("FAILED:CNL-0090-probe2 id-set missed verbatim loop")
        return 1
    if ids["productive"]["fired"] or ids["refinement"]["fired"]:
        print("FAILED:CNL-0090-probe2 id-set fired on known-good")
        return 1

    # Divergence that proves Jaccard is load-bearing.
    if ids["paraphrase"]["fired"]:
        print(
            "FAILED:CNL-0090-probe2 id-set fired on paraphrase; "
            "fixture does not separate the two signals"
        )
        return 1
    if det["paraphrase"]["fired"] == ids["paraphrase"]["fired"]:
        print("FAILED:CNL-0090-probe2 paraphrase signals did not diverge")
        return 1

    # Paraphrase round 2+ must show id-set units > 0 while detector units == 0.
    para_id = curve_units(ids["paraphrase"])
    para_det = curve_units(det["paraphrase"])
    if para_det[0] < 1:
        print("FAILED:CNL-0090-probe2 paraphrase round 1 has no detector gain")
        return 1
    if any(u != 0 for u in para_det[1:]):
        print(f"FAILED:CNL-0090-probe2 detector paraphrase tail not zero {para_det}")
        return 1
    if any(u < 1 for u in para_id[1:]):
        print(f"FAILED:CNL-0090-probe2 id-set paraphrase tail not positive {para_id}")
        return 1

    fp_num = int(det["productive"]["fired"]) + int(det["refinement"]["fired"])
    fpr = fp_num / 2.0
    print(f"false_positive_rate={fpr} numerator={fp_num} denominator=2")
    print(
        "negative_control: on clean-productive (the state circling must reject) "
        f"id-set silent={ids['productive']['silent']} "
        f"detector silent={det['productive']['silent']}"
    )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            print("FAILED:CNL-0090-probe2 sentinel-absent in artifact")
            return 1
        try:
            spec = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"FAILED:CNL-0090-probe2 artifact-unparseable {exc}")
            return 1
        if not SCHEMA_LOCAL.is_file():
            print("FAILED:CNL-0090-probe2 local-schema-missing")
            return 1
        schema = json.loads(SCHEMA_LOCAL.read_text(encoding="utf-8"))
        errors = sorted(
            jsonschema.Draft7Validator(schema).iter_errors(spec),
            key=lambda e: list(e.path),
        )
        if errors:
            print(f"FAILED:CNL-0090-probe2 schema-errors {len(errors)} {errors[0].message}")
            return 1
        if SCHEMA.is_file():
            try:
                jsonschema.Draft7Validator(
                    json.loads(SCHEMA.read_text(encoding="utf-8"))
                ).validate(spec)
            except RefResolutionError:
                print("catalog_schema=shim-unresolved local_schema=ok")
        if spec.get("state") != "SUCCESS":
            print(f"FAILED:CNL-0090-probe2 artifact state={spec.get('state')}")
            return 1
        live_fpr = spec.get("false_positive_rate")
        if live_fpr != fpr:
            print(f"FAILED:CNL-0090-probe2 artifact FPR {live_fpr} != live {fpr}")
            return 1
        th = spec.get("thresholds") or {}
        if th.get("floor_information_units") != D.FLOOR:
            print("FAILED:CNL-0090-probe2 artifact floor mismatch")
            return 1
        if th.get("consecutive_subfloor_rounds") != D.WINDOW:
            print("FAILED:CNL-0090-probe2 artifact window mismatch")
            return 1
        if spec.get("both_states", {}).get("detector_control_first") is not True:
            print("FAILED:CNL-0090-probe2 detector_control_first missing")
            return 1
        print("artifact_schema=ok sentinel=ok fpr_match=ok")
    else:
        print("artifact_absent_skip_schema")

    payload = {
        "probe": "probe2-independent-gain",
        "unit_id": "CNL-0090",
        "pass": True,
        "false_positive_rate": fpr,
        "divergence": {
            "fixture": "planted_paraphrase.json",
            "id_set_fired": ids["paraphrase"]["fired"],
            "detector_fired": det["paraphrase"]["fired"],
            "id_set_units": para_id,
            "detector_units": para_det,
            "why": (
                "new claim_ids on paraphrased text look like gain to id-set-only; "
                "token/char4 corroboration zeros G_t so the detector FIREs"
            ),
        },
        "agreement": {
            "loop_both_fire": True,
            "productive_both_silent": True,
            "refinement_both_silent": True,
        },
        "negative_control": {
            "state_rejected": "clean-productive-counterexamples (circling absent)",
            "id_set_silent": ids["productive"]["silent"],
            "detector_silent": det["productive"]["silent"],
        },
        "id_set": {k: {"fired": v["fired"], "units": curve_units(v)} for k, v in ids.items()},
        "detector": {k: {"fired": v["fired"], "units": curve_units(v)} for k, v in det.items()},
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUCCESS:CNL-0090-probe2 independent id-set gain vs Jaccard corroboration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
