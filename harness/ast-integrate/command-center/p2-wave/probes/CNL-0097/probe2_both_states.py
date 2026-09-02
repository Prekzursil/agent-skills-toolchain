#!/usr/bin/env python3
"""Probe 2: independent both-states re-run + numeric false-positive rate.

This process re-executes planted-bad then known-good itself. A review that
did not execute the control is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import scenario as S  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"
ART = REPO / (
    "command-center/design/council/"
    "CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0097-probe2 {msg}")
    return 1


def validate_artifact(fp: dict, bad: dict, good: dict) -> str | None:
    if not ART.is_file():
        return None
    import jsonschema
    from jsonschema.exceptions import RefResolutionError, ValidationError

    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator(schema).validate(doc)
    except RefResolutionError as exc:
        return f"schema-ref: {exc}"
    except ValidationError as exc:
        return f"schema: {exc.message}"
    if "SUCCESS:CNL-0097" not in ART.read_text(encoding="utf-8"):
        return "sentinel missing from artifact"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {doc.get('state')}"
    art_fp = doc.get("false_positive_rate") or {}
    if float(art_fp.get("value")) != float(fp["value"]):
        return f"artifact FP {art_fp.get('value')} != live {fp['value']}"
    if int(art_fp.get("numerator")) != int(fp["numerator"]):
        return "artifact FP numerator mismatch"
    if int(art_fp.get("denominator")) != int(fp["denominator"]):
        return "artifact FP denominator mismatch"
    both = doc.get("both_states") or {}
    if both.get("planted_bad", {}).get("fired") is not True:
        return "artifact planted_bad.fired is not true"
    if both.get("known_good", {}).get("silent") is not True:
        return "artifact known_good.silent is not true"
    if not (doc.get("reviewer") or {}).get("executed_both_states_control"):
        return "artifact reviewer did not execute both-states"
    if not bad["fired"] or not good["silent"]:
        return "live both-states disagree with artifact"
    return "ok"


def main() -> int:
    S.write_all()
    D.reset_control()

    bad = D.detector_control_known_present(S.planted_bad())
    if not bad["fired"]:
        return fail("independent reviewer: planted-bad did not FIRE")
    good = D.detect_after_control(S.known_good())
    if good["fired"] or not good["silent"]:
        return fail(f"independent reviewer: known-good fired lost={good.get('lost_ids')}")

    clean_results = []
    for name, builder in S.CLEAN.items():
        council = builder()
        result = D.detect(council)
        result["fixture_id"] = council["id"]
        if result["fired"]:
            return fail(f"false positive on clean fixture {name}: {result.get('lost_ids')}")
        clean_results.append(result)
    fp = D.false_positive_rate(clean_results)
    if fp["denominator"] < 1:
        return fail("FP denominator is zero")
    print(
        f"false_positive_rate={fp['value']} "
        f"numerator={fp['numerator']} denominator={fp['denominator']}"
    )

    art_status = validate_artifact(fp, bad, good)
    if art_status not in (None, "ok"):
        return fail(art_status)

    bad_verbatim = (
        f"planted-bad id={bad.get('fixture_id', S.planted_bad()['id'])} "
        f"fired={bad['fired']} lost_ids={bad['lost_ids']} "
        f"self_attestation_ignored={bad['ignored_synthesizer_self_attestation']}"
    )
    good_verbatim = (
        f"known-good id={S.known_good()['id']} fired={good['fired']} "
        f"silent={good['silent']} preserved_ids={good['preserved_ids']}"
    )
    print(bad_verbatim)
    print(good_verbatim)

    doc = {
        "pass": True,
        "independent_reviewer": True,
        "executed_both_states_control": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "false_positive_rate": fp,
        "planted_bad_verbatim": bad_verbatim,
        "known_good_verbatim": good_verbatim,
        "artifact_check": art_status or "absent-skip",
        "reviewer_id": "CNL-0097-probe2-independent-both-states",
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad=True silent_on_good=True false_positive_rate={fp['value']} "
        f"artifact={doc['artifact_check']}"
    )
    print("SUCCESS:CNL-0097-probe2 both-states and numeric false-positive rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
