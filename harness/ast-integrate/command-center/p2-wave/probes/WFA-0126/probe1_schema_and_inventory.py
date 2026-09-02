#!/usr/bin/env python3
"""Probe 1: independent inventory, schema both-states, residuals, did-not."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inventory as I  # noqa: E402

ART = I.REPO / I.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0126-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    doc = I.load_json(ART)
    if doc.get("unit_id") != "WFA-0126":
        return fail(f"unit_id={doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:WFA-0126" not in json.dumps(doc):
        return fail("sentinel-absent")

    ok, reason = I.validate_handoff(doc)
    if not ok:
        return fail(f"schema {reason}")
    mutant = I.both_states_schema(doc)
    mok, mreason = I.validate_handoff(mutant)
    if mok:
        return fail("both-states mutant still valid")
    extra = json.loads(json.dumps(doc))
    extra["not_in_schema"] = True
    eok, _ = I.validate_handoff(extra)
    if eok:
        return fail("additionalProperties allowed extra key")

    catalog = I.load_catalog()
    units = I.wfa_units(catalog)
    indep = I.build_rows()
    declared = doc.get("declared_artifacts") or []
    if len(declared) != len(units) or len(declared) != len(indep):
        return fail(
            f"declared-count catalog={len(units)} contract={len(declared)} "
            f"indep={len(indep)}"
        )
    by_c = {r["unit_id"]: r for r in declared}
    by_i = {r["unit_id"]: r for r in indep}
    for uid, row in by_i.items():
        crow = by_c.get(uid)
        if crow is None:
            return fail(f"missing-row {uid}")
        if crow["path"] != row["path"]:
            return fail(f"path-mismatch {uid}")
        if uid == "WFA-0126":
            if not crow["present"] or not row["present"]:
                return fail("self-not-present")
            continue
        if crow["present"] != row["present"]:
            return fail(f"present-mismatch {uid}")
        if crow["sha256"] != row["sha256"]:
            return fail(f"sha-mismatch {uid}")

    delivered = doc.get("delivered_artifacts") or []
    for row in delivered:
        if not (row.get("present") and row.get("parseable") and row.get("schema_valid")):
            return fail(f"overclaim-delivered {row.get('unit_id')}")
        live = I.measure_path(row["path"])
        if not live["present"] or not live["parseable"]:
            return fail(f"delivered-missing {row.get('unit_id')}")

    if not I.delivered_subset(indep) and not any(
        r.get("unit_id") == "WFA-0126" for r in delivered
    ):
        return fail("self-not-in-delivered")

    unknowns = doc.get("residual_unknowns") or []
    if not unknowns:
        return fail("residuals-absent")
    for ru in unknowns:
        if not str(ru.get("settling_experiment") or "").strip():
            return fail(f"residual-no-settling {ru.get('id')}")
        if not str(ru.get("owner_visible_impact") or "").strip():
            return fail(f"residual-no-impact {ru.get('id')}")
        if not ru.get("inherited_by"):
            return fail(f"residual-no-inherit {ru.get('id')}")

    did_not = doc.get("bucket_did_not") or []
    if len(did_not) < 3:
        return fail("did-not-too-thin")
    joined = " ".join(str(x.get("statement") or "") for x in did_not).lower()
    for needle in ("schema pack", "query interface", "owner"):
        if needle not in joined:
            return fail(f"did-not-missing:{needle}")

    buckets = doc.get("downstream_buckets") or {}
    for name in ("implementation", "testing", "council"):
        b = buckets.get(name)
        if not isinstance(b, dict):
            return fail(f"bucket-missing {name}")
        if not b.get("named_consumer_unit_id"):
            return fail(f"bucket-no-consumer {name}")
        if b.get("measured_unit_count") in (None, 0):
            return fail(f"bucket-count-zero {name}")

    sign = doc.get("owner_signoff") or {}
    if sign.get("granted") is True:
        return fail("overclaim-owner-signoff")
    if sign.get("this_artifact_self_certifies_completeness") is True:
        return fail("overclaim-completeness")

    check = doc.get("manifest_registration_check") or {}
    live_check = I.manifest_check(declared)
    if check.get("global_artifact_manifest_present") != live_check[
        "global_artifact_manifest_present"
    ]:
        return fail("manifest-present-mismatch")
    if check.get("wfa0083_artifact_present") is True and not (
        I.REPO / I.WFA0083_REL
    ).is_file():
        return fail("overclaim-wfa0083")

    cat_sha = I.catalog_sha256()
    if doc.get("catalog_sha256") != cat_sha:
        return fail("catalog-sha-stale")

    print(
        json.dumps(
            {
                "probe": "probe1-schema-and-inventory",
                "unit_id": "WFA-0126",
                "schema_ok": True,
                "both_states_mutant_rejected": True,
                "additional_properties_rejected": True,
                "declared": len(declared),
                "independent_present": sum(1 for r in indep if r["present"]),
                "delivered": len(delivered),
                "residuals": len(unknowns),
                "did_not": len(did_not),
                "impl_measured": buckets["implementation"]["measured_unit_count"],
                "tst_measured": buckets["testing"]["measured_unit_count"],
                "cnl_measured": buckets["council"]["measured_unit_count"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0126-probe1 schema both-states inventory residuals did-not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
