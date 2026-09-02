#!/usr/bin/env python3
"""Probe 2: Draft 2020-12 schema + timeout-is-not-secure negative control."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import instantiate as I  # noqa: E402
import schema_util as S  # noqa: E402

SCHEMA_PATH = HERE / "council-preset.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-preset.schema.json"
OUT_PATH = (
    REPO
    / "command-center"
    / "design"
    / "council"
    / "CNL-0107-security-red-blue-council-preset.md"
)


def error_count(validator: Draft202012Validator, doc: object) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def main() -> int:
    schema = S.load_local_schema()
    Draft202012Validator.check_schema(schema)
    doc_validator = S.envelope_validator()
    preset_validator = S.preset_validator()

    ours = I.load_preset("preset_cnl0107.json")
    sibling = I.load_preset("preset_sibling_p08.json")
    catalog = I.load_preset("preset_catalog_class.json")
    invalid = I.load_preset("invalid_preset.json")

    counts = {
        "ours": error_count(preset_validator, ours),
        "sibling": error_count(preset_validator, sibling),
        "catalog_class": error_count(preset_validator, catalog),
        "invalid": error_count(preset_validator, invalid),
    }

    mutant = copy.deepcopy(ours)
    mutant["id"] = "NEG.timeout-maps-to-blue-win"
    mutant["stopping"]["timeout_outcome"] = "BLUE_WINS"
    mutant["stopping"]["timeout_may_not_map_to_blue_win"] = False
    mutant_timeout = I.evaluate_stop(mutant, I.timeout_without_coverage_state())
    ours_timeout = I.evaluate_stop(ours, I.timeout_without_coverage_state())

    artifact_errors: list[str] = []
    artifact_checked = OUT_PATH.is_file()
    if not artifact_checked:
        artifact_errors = ["artifact-absent"]
    else:
        try:
            artifact = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            artifact_errors = [f"unparseable:{exc}"]
        else:
            artifact_errors = error_count(doc_validator, artifact)
            if artifact.get("sentinel") != "SUCCESS:CNL-0107":
                artifact_errors.append("sentinel-absent")
            inner = artifact.get("preset") if isinstance(artifact, dict) else None
            if not (
                isinstance(inner, dict)
                and inner.get("stopping", {}).get("timeout_outcome") == "INCONCLUSIVE"
            ):
                artifact_errors.append("artifact-timeout-not-inconclusive")
            if str(artifact.get("state") or "").upper() in {
                "BLOCKED",
                "FAILED",
                "SEVERED",
                "TIMEOUT",
            }:
                artifact_errors.append(f"self-declared:{artifact.get('state')}")

    schema_ok = (
        len(counts["ours"]) == 0
        and len(counts["sibling"]) == 0
        and len(counts["catalog_class"]) == 0
        and len(counts["invalid"]) > 0
        and len(artifact_errors) == 0
    )
    timeout_ok = (
        ours["stopping"]["timeout_outcome"] == "INCONCLUSIVE"
        and ours["stopping"]["timeout_may_not_map_to_blue_win"] is True
        and ours_timeout == "INCONCLUSIVE"
        and mutant_timeout == "BLUE_WINS"
    )
    ok = schema_ok and timeout_ok
    verbatim_negative = (
        "Draft202012Validator on fixtures/invalid_preset.json (missing required "
        f"roles/stopping/win_conditions/...) yields {len(counts['invalid'])} errors; "
        "first="
        + (counts["invalid"][0] if counts["invalid"] else "<none>")
        + ". Evaluator on timeout + blue_claims_secure + no red coverage_ack returns "
        f"{ours_timeout} (must be INCONCLUSIVE). Mutant timeout_outcome=BLUE_WINS "
        f"evaluates to {mutant_timeout} and is rejected as not CNL-0107."
    )
    payload = {
        "probe": "probe2-schema-timeout",
        "unit_id": "CNL-0107",
        "schema_path": SCHEMA_PATH.relative_to(REPO).as_posix(),
        "catalog_schema_path": CATALOG_SCHEMA,
        "error_counts": {k: len(v) for k, v in counts.items()},
        "invalid_errors_head": counts["invalid"][:4],
        "artifact_checked": artifact_checked,
        "artifact_error_count": len(artifact_errors),
        "timeout_ours": ours_timeout,
        "timeout_mutant": mutant_timeout,
        "negative_control_verbatim": verbatim_negative,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"schema ours={len(counts['ours'])} sibling={len(counts['sibling'])} "
        f"catalog={len(counts['catalog_class'])} invalid={len(counts['invalid'])} "
        f"timeout_ours={ours_timeout} mutant={mutant_timeout}"
    )
    print(f"NEGATIVE-CONTROL: {verbatim_negative}")
    if not ok:
        if counts["ours"]:
            print("ours errors:", counts["ours"][:8])
        if counts["sibling"]:
            print("sibling errors:", counts["sibling"][:8])
        if counts["catalog_class"]:
            print("catalog errors:", counts["catalog_class"][:8])
        if artifact_errors:
            print("artifact errors:", artifact_errors[:8])
        print("FAILED:CNL-0107-probe2 schema/timeout")
        return 1
    print("SUCCESS:CNL-0107-probe2 schema timeout-not-secure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
