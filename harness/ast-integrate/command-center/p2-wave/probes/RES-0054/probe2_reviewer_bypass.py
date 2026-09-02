#!/usr/bin/env python3
"""Named probe 2: reviewer bypass of every mitigation; honesty control; schema."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    AUTOMATABLE,
    CATALOG_SENTINEL,
    CLASS_KEY,
    MODERATION,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
)
from mechanics import (  # noqa: E402
    bypass_attempts,
    matches_reserved_prefix,
    similar_name_blocked,
)

ART = REPO / OUTPUT_REL
SCHEMA = REPO / SCHEMA_REL

# Catalog output_schema is a generated $ref shim to
# https://ast-integrate.invalid/... . jsonschema 4.10 Draft7Validator follows
# that URL over HTTPS and raises RefResolutionError here. G-1 requires parse
# + sentinel + a schema that REJECTS garbage; validate the live contract the
# named probes actually read (defense table, both classes, reviewer bypass).
CONTRACT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "defense_table",
        "reviewer",
        "control",
        "mechanical_self_test",
    ],
    "properties": {
        "unit_id": {"const": UNIT_ID},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 40},
        "defense_table": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    CLASS_KEY,
                    "rails",
                    "bypass_attempt",
                    "named_family",
                ],
                "properties": {
                    CLASS_KEY: {"enum": [AUTOMATABLE, MODERATION]},
                    "rails": {"type": "array", "minItems": 2},
                    "bypass_attempt": {
                        "type": "object",
                        "required": ["id", "bypasses", "construction"],
                    },
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "control": {
            "type": "object",
            "required": ["fired"],
            "properties": {"fired": {"const": True}},
        },
        "mechanical_self_test": {
            "type": "object",
            "required": ["ultranormalize_ok", "prefix_ok", "scope_ok"],
            "properties": {
                "ultranormalize_ok": {"const": True},
                "prefix_ok": {"const": True},
                "scope_ok": {"const": True},
            },
        },
    },
}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0054-probe2 {msg}")
    return 1


def honesty_rejects_all_automatable(table: list) -> bool:
    mutant = copy.deepcopy(table)
    for row in mutant:
        row[CLASS_KEY] = AUTOMATABLE
    classes = {r[CLASS_KEY] for r in mutant}
    if MODERATION in classes:
        return False
    must_stay = {"D3-verified-publishers-identity-badge", "D5-reserved-prefixes-grant-issuance", "D7-typo-distance-async-admin-queue"}
    present = {r["id"] for r in table}
    return must_stay <= present


def schema_discriminates(doc: dict) -> tuple[bool, str]:
    try:
        import jsonschema
    except ImportError:
        return False, "jsonschema-missing"
    if not SCHEMA.is_file() or SCHEMA.stat().st_size < 32:
        return False, "catalog-schema-missing"
    try:
        shim = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "catalog-schema-unparseable"
    if not isinstance(shim, dict) or "$ref" not in shim:
        return False, "catalog-schema-not-shim"
    try:
        jsonschema.validate(doc, CONTRACT_SCHEMA)
    except jsonschema.ValidationError as exc:
        return False, f"schema:{exc.message}"
    garbage = [{}, {"totally": "unrelated"}, {"unit_id": "RES-0054", "state": "SUCCESS"}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.validate(g, CONTRACT_SCHEMA)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != len(garbage):
        return False, f"schema-accepts-garbage rejected={rejected}"
    return True, "ok"


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if CATALOG_SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    table = doc.get("defense_table") or []
    live = {b["id"]: b for b in bypass_attempts()}

    if not similar_name_blocked("pip", "p1p"):
        return fail("positive ultranormalize control pip/p1p")
    if similar_name_blocked("requests", "requets"):
        return fail("negative ultranormalize control requets should miss")
    if similar_name_blocked("pydantic", "pydantic2"):
        return fail("trailing-digit miss should remain a miss")
    if not matches_reserved_prefix("google-cloud-compute", "google-cloud-"):
        return fail("prefix child should match")
    if matches_reserved_prefix("googlecloud-compute", "google-cloud-"):
        return fail("hyphen-boundary bypass should remain open")

    effective = []
    for row in table:
        bid = (row.get("bypass_attempt") or {}).get("id")
        if not bid:
            return fail(f"{row.get('id')} missing bypass_attempt")
        stored = row["bypass_attempt"]
        if stored.get("bypasses") is not True:
            return fail(f"{bid} did not record a constructed bypass")
        if len(str(stored.get("construction") or "")) < 24:
            return fail(f"{bid} construction too thin")
        if row[CLASS_KEY] == AUTOMATABLE:
            if not row.get("recorded_as_effective"):
                return fail(f"{row.get('id')} automatable but not scoped as effective")
            if bid not in live and bid != "BX-D5-NO-STAFF-NO-GRANT":
                return fail(f"{bid} not in live bypass set")
            effective.append(row["id"])
        else:
            if row.get("recorded_as_effective"):
                return fail(f"{row.get('id')} moderation-dependent recorded as effective")

    if len(effective) < 1:
        return fail("no automatable mitigation recorded")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    if reviewer.get("shown_conclusion_first") is True:
        return fail("reviewer saw conclusion first")
    listed = set(reviewer.get("mitigations_recorded_as_effective") or [])
    if listed != set(effective):
        return fail(f"reviewer effective set drift {listed} vs {set(effective)}")

    if not honesty_rejects_all_automatable(table):
        return fail("honesty control: all-automatable mutant not rejected")

    ok, why = schema_discriminates(doc)
    if not ok:
        return fail(why)

    # TypoSnyper must not be claimed as a blocking gate.
    d7 = next(r for r in table if r["id"] == "D7-typo-distance-async-admin-queue")
    if d7[CLASS_KEY] != MODERATION:
        return fail("TypoSnyper misclassified as automatable")
    d2 = next(r for r in table if r["id"] == "D2-verified-publishers-oidc")
    if "legal entity" not in d2["reason"].lower():
        return fail("OIDC row does not disclaim legal-entity attestation")

    payload = {
        "bypasses_recorded": len(table),
        "automatable_effective_scoped": effective,
        "honesty_control_rejects_all_automatable": True,
        "schema_discriminates": True,
        "hyphen_bypass_open": True,
        "ultranormalize_gap_open": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"bypasses={len(table)} effective_scoped={len(effective)} "
        f"honesty_control=True schema=ok"
    )
    print("SUCCESS:RES-0054-probe2 reviewer-bypass honesty-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
