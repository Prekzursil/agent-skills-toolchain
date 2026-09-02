#!/usr/bin/env python3
"""Probe 2: consumer call site — missing required provenance must be rejected.

Loads registry_entry_schema from the live contract (not schema.py) and
instantiates Draft202012Validator against it. Both-states: published fixture
accepts; the same entry with provenance removed is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0079.json"
RAW = HERE / "probe2-negative-provenance.raw.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def schema_errors(validator: Draft202012Validator, instance: dict) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def main() -> int:
    errs: list[str] = []
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0079-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print("FAILED:ARC-0079-probe2 artifact not an object")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        errs.append(f"contract-state={st}")
    if "SUCCESS:ARC-0079" not in json.dumps(doc):
        errs.append("sentinel-absent")

    schema = doc.get("registry_entry_schema")
    if not isinstance(schema, dict):
        print("FAILED:ARC-0079-probe2 registry_entry_schema missing from contract")
        return 1
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 — surface metaschema failure
        print(f"FAILED:ARC-0079-probe2 schema not Draft-2020-12: {exc}")
        return 1
    validator = Draft202012Validator(schema)

    good = F.published()
    good_errs = schema_errors(validator, good)
    missing = F.missing_provenance()
    miss_errs = schema_errors(validator, missing)
    sha_missing = F.missing_artifact_sha256()
    sha_errs = schema_errors(validator, sha_missing)

    silent_on_good = not good_errs
    fired_on_bad = bool(miss_errs) and bool(sha_errs)
    if not silent_on_good:
        errs.append("good-rejected")
    if not miss_errs:
        errs.append("missing-provenance-accepted")
    if not sha_errs:
        errs.append("missing-artifact-sha256-accepted")
    prov_related = any("provenance" in e.lower() for e in miss_errs)
    if miss_errs and not prov_related:
        errs.append("missing-provenance-rejected-for-other-reason")

    payload = {
        "probe": "probe2-negative-provenance",
        "unit_id": "ARC-0079",
        "consumer_call_site": "Draft202012Validator(contract['registry_entry_schema'])",
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "good_error_count": len(good_errs),
        "missing_provenance_errors": miss_errs[:8],
        "missing_sha256_errors": sha_errs[:8],
        "errors": errs,
        "pass": not errs,
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"silent_on_good={silent_on_good} fired_on_bad={fired_on_bad} "
        f"missing_n={len(miss_errs)} sha_n={len(sha_errs)} "
        f"call_site=Draft202012Validator"
    )
    if errs:
        print("FAILED:ARC-0079-probe2 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0079-probe2 missing provenance rejected; published accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
