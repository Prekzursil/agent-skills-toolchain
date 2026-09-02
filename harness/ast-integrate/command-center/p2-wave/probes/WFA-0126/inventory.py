#!/usr/bin/env python3
"""Live inventory of WFA catalog outputs for the WFA-0126 handoff contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
GLOBAL_MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
WFA0083_REL = "command-center/wfa/WFA-0083-artifact-manifest-registration.json"
OUT_REL = "command-center/wfa/WFA-0126-bucket-handoff-contract.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0126/handoff-contract.schema.json"
)
CATALOG_SCHEMA = (
    "command-center/wfa/schema/wfa-schema-pack.json#/$defs/HandoffContract"
)

EIGHTEEN_DEFS = (
    "WorkflowRecord",
    "SweepReport",
    "ProbeReport",
    "ExtractionReport",
    "DispositionRecord",
    "Graph",
    "WorkflowIR",
    "AdapterConformanceReport",
    "SemanticDiff",
    "FusionResult",
    "BenchmarkResult",
    "CertificationRecord",
    "RegressionFixture",
    "AuditReport",
    "HandoffContract",
    "MechanismRecord",
    "RepairRecord",
    "CoverageMatrix",
)

CONSUMERS_BY_DEF = {
    "HandoffContract": ["council", "implementation", "testing"],
    "WorkflowRecord": ["implementation", "testing"],
    "WorkflowIR": ["implementation", "testing"],
    "SweepReport": ["implementation", "testing"],
    "ExtractionReport": ["implementation", "testing"],
    "DispositionRecord": ["council", "implementation"],
    "Graph": ["implementation", "testing"],
    "AdapterConformanceReport": ["implementation", "testing"],
    "SemanticDiff": ["implementation", "testing"],
    "FusionResult": ["implementation", "testing"],
    "BenchmarkResult": ["implementation", "testing"],
    "CertificationRecord": ["council", "implementation", "testing"],
    "RegressionFixture": ["implementation", "testing"],
    "AuditReport": ["council", "testing"],
    "MechanismRecord": ["implementation", "testing"],
    "RepairRecord": ["implementation", "testing"],
    "CoverageMatrix": ["council", "implementation", "testing"],
    "ProbeReport": ["implementation", "testing"],
}
ALL_BUCKETS = ["council", "implementation", "testing"]

QUESTION = (
    "Implementation target: a typed handoff contract naming exactly which "
    "artifacts this bucket delivers, their schemas and versions, which "
    "downstream buckets consume each one, and which of this bucket's residual "
    "unknowns each downstream bucket inherits."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog() -> dict:
    return load_json(REPO / CATALOG_REL)


def catalog_sha256() -> str:
    return digest_file(REPO / CATALOG_REL)[0]


def wfa_units(catalog: dict | None = None) -> list[dict]:
    doc = catalog if catalog is not None else load_catalog()
    out = [
        u
        for u in (doc.get("work_units") or [])
        if isinstance(u, dict) and str(u.get("id") or "").startswith("WFA-")
    ]
    out.sort(key=lambda u: str(u.get("id")))
    return out


def prefix_count(catalog: dict, prefix: str) -> int:
    n = 0
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict) and str(u.get("id") or "").startswith(prefix):
            n += 1
    return n


def schema_def(output_schema: str) -> str:
    text = str(output_schema or "")
    if "#/$defs/" in text:
        return text.split("#/$defs/", 1)[1].strip() or "untyped"
    if text.endswith("/schema"):
        return "json-schema-document"
    if "/" in text:
        return text.rsplit("/", 1)[-1].split(".")[0] or "untyped"
    return text or "untyped"


def consumers_for(defn: str) -> list[str]:
    return list(CONSUMERS_BY_DEF.get(defn, ALL_BUCKETS))


def measure_path(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "present": False,
            "bytes": None,
            "sha256": None,
            "parseable": False,
        }
    sha, size = digest_file(path)
    parseable = False
    if rel.endswith(".json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parseable = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parseable = False
    else:
        parseable = size > 0
    return {
        "present": True,
        "bytes": size,
        "sha256": sha,
        "parseable": parseable,
    }


def pack_present() -> bool:
    p = REPO / PACK_REL
    return p.is_file() and p.stat().st_size > 0


def pack_constraint_bearing() -> bool:
    """True only if pack $defs.HandoffContract is a local object schema.

    The generated substrate shim stores `$ref` to
    https://ast-integrate.invalid/... which jsonschema 4.10 tries to fetch.
    That is not the 18-type pack WFA-0001 is specified to emit.
    """
    if not pack_present():
        return False
    try:
        pack = load_json(REPO / PACK_REL)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    pack_defs = pack.get("$defs") if isinstance(pack, dict) else None
    if not isinstance(pack_defs, dict):
        return False
    hc = pack_defs.get("HandoffContract")
    if not isinstance(hc, dict):
        return False
    props = hc.get("properties")
    # Pack $def is a thinner artifacts/consumers shape. This unit's probes
    # assert declared_artifacts / bucket_did_not at root against the
    # unit-local HandoffContract. Prefer local when the pack lacks those keys.
    return (
        hc.get("type") == "object"
        and isinstance(props, dict)
        and "declared_artifacts" in props
    )


def load_handoff_schema() -> dict:
    schema = load_json(REPO / LOCAL_SCHEMA_REL)
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    if pack_constraint_bearing():
        pack = load_json(REPO / PACK_REL)
        pack_defs = pack.get("$defs") if isinstance(pack, dict) else None
        if isinstance(pack_defs, dict) and "HandoffContract" in pack_defs:
            defs = pack_defs
            schema = pack
    if not isinstance(defs, dict) or "HandoffContract" not in defs:
        raise RuntimeError("HandoffContract $def missing from schema")
    target = dict(defs["HandoffContract"])
    target["$defs"] = defs
    if schema.get("$schema"):
        target["$schema"] = schema["$schema"]
    return target


def validate_handoff(doc: dict) -> tuple[bool, str]:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import RefResolutionError, SchemaError

    try:
        schema = load_handoff_schema()
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    except (RefResolutionError, SchemaError, RuntimeError) as exc:
        return False, f"validator-error:{type(exc).__name__}:{exc}"
    if errors:
        err = errors[0]
        loc = ".".join(str(p) for p in err.path) or "<root>"
        return False, f"{loc}: {err.message}"
    return True, "validated-against-unit-local-HandoffContract"


def artifact_row(unit: dict, live_self: dict | None = None) -> dict:
    uid = str(unit.get("id"))
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema = str(unit.get("output_schema") or "")
    defn = schema_def(schema)
    live = live_self if live_self is not None else measure_path(rel)
    present = bool(live["present"])
    parseable = bool(live["parseable"])
    schema_ok = False
    if uid == "WFA-0126" and present and parseable:
        try:
            doc = load_json(REPO / rel)
            schema_ok, reason = validate_handoff(doc)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            schema_ok, reason = False, f"unparseable:{type(exc).__name__}"
    elif not present:
        reason = "artifact-absent"
    elif not parseable:
        reason = "unparseable"
    elif not pack_present():
        reason = "pack-absent; schema-valid-not-computable"
    elif not pack_constraint_bearing():
        reason = "pack-is-generated-shim; cross-def-not-claimed-here"
    else:
        reason = "pack-present-but-cross-def-not-claimed-here"
    return {
        "unit_id": uid,
        "path": rel,
        "schema": schema or "unspecified",
        "schema_def": defn,
        "schema_version": "unversioned-until-WFA-0001",
        "present": present,
        "bytes": live["bytes"],
        "sha256": live["sha256"],
        "parseable": parseable,
        "schema_valid": schema_ok,
        "schema_valid_reason": reason,
        "manifest_registered": False,
        "consumers": consumers_for(defn),
        "title": str(unit.get("title") or uid),
    }


def build_rows() -> list[dict]:
    return [artifact_row(unit) for unit in wfa_units()]


def delivered_subset(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["present"] and r["parseable"] and r["schema_valid"]]


def residual_unknowns(
    *,
    present_on_disk: int | None = None,
    catalog_n: int | None = None,
) -> list[dict]:
    if catalog_n is None:
        catalog_n = len(wfa_units())
    if present_on_disk is None:
        present_on_disk = sum(1 for r in build_rows() if r["present"])
    absent_n = max(catalog_n - present_on_disk, 0)
    global_manifest = (REPO / GLOBAL_MANIFEST_REL).is_file()
    wfa0083 = (REPO / WFA0083_REL).is_file()
    if wfa0083 and global_manifest:
        manifest_stmt = (
            "WFA-0083 and command-center/ARTIFACT-MANIFEST.json exist on disk; "
            "this unit did not write them and does not treat that as bucket "
            "condition-11 registration of every WFA output."
        )
    elif global_manifest:
        manifest_stmt = (
            "WFA-0083 artifact is absent; command-center/ARTIFACT-MANIFEST.json "
            "is present but was not written by this unit and does not register "
            "the WFA bucket under condition-11."
        )
    elif wfa0083:
        manifest_stmt = (
            "WFA-0083 artifact is present while command-center/"
            "ARTIFACT-MANIFEST.json is absent; bucket condition-11 "
            "registration is not live."
        )
    else:
        manifest_stmt = (
            "WFA-0083 and command-center/ARTIFACT-MANIFEST.json are both "
            "absent; bucket condition-11 registration is not live."
        )
    if pack_constraint_bearing():
        pack_stmt = (
            "WFA-0001 schema pack is on disk and HandoffContract $def is "
            "constraint-bearing; the 36-example two-validator control is "
            "still not claimed here."
        )
    elif pack_present():
        pack_stmt = (
            "WFA-0001 output path exists as a generated $ref shim "
            f"({PACK_REL}); $defs.HandoffContract is a $ref to "
            "https://ast-integrate.invalid/... and carries no local "
            "required fields or additionalProperties:false. This is not "
            "the 18-type pack the catalog asks WFA-0001 to emit. This "
            f"unit validates against {LOCAL_SCHEMA_REL}."
        )
    else:
        pack_stmt = (
            "WFA-0001 schema pack is absent; 18 record types have no "
            "on-disk $defs bundle on this tree."
        )
    return [
        {
            "id": "RU-SCHEMA-PACK",
            "statement": pack_stmt,
            "settling_experiment": (
                "Deliver WFA-0001: emit wfa-schema-pack.json with 18 local "
                "object $defs (required fields, additionalProperties:false), "
                "run 36 accept/reject examples under two validators, then "
                "re-validate every present WFA artifact against its $def."
            ),
            "owner_visible_impact": (
                "Downstream IMP/TST/CNL cannot schema-validate WFA records "
                "against the contracted pack until that unit lands. Fetching "
                "the shim $ref fails on this image (ast-integrate.invalid)."
            ),
            "inherited_by": ["council", "implementation", "testing"],
        },
        {
            "id": "RU-MANIFEST",
            "statement": manifest_stmt,
            "settling_experiment": (
                "Deliver WFA-0083: recompute hashes on blobs, register every "
                "WFA output, and run the consumer smoke test that fails on a "
                "deliberately malformed artifact."
            ),
            "owner_visible_impact": (
                "A consumer that treats the program ARTIFACT-MANIFEST.json as "
                "a WFA-0083 register will mis-read condition-11; this contract "
                "does not certify global registration."
            ),
            "inherited_by": ["council", "implementation", "testing"],
        },
        {
            "id": "RU-BUCKET-ABSENT",
            "statement": (
                f"{absent_n} of {catalog_n} catalogued WFA outputs are absent "
                f"on this worktree; {present_on_disk} files are present "
                "including this handoff. Sibling present files are not "
                "schema_valid here (pack-absent) and are not listed in "
                "delivered_artifacts."
            ),
            "settling_experiment": (
                "Re-run the per-unit G-1 measure on each remaining WFA id; "
                "the independent recount is present_on_disk versus catalog "
                "count, not a narrative status."
            ),
            "owner_visible_impact": (
                "Implementation, testing and council inherit a mostly-absent "
                "archaeology surface plus pack-unvalidated sibling blobs; they "
                "must not schedule work as if registries, graphs or "
                "certifications are delivered by this contract."
            ),
            "inherited_by": ["council", "implementation", "testing"],
        },
        {
            "id": "RU-QUERY-INTERFACE",
            "statement": (
                "WFA-0084 typed query interface is absent; downstream cannot "
                "consume the registry through a stable contract."
            ),
            "settling_experiment": (
                "Deliver WFA-0084 and replay the fusion-precondition checker "
                "through the interface versus direct file access."
            ),
            "owner_visible_impact": (
                "IMP-0209 scout and IMP-0212 forge have no registry query "
                "surface; they must not scrape four JSON files ad hoc."
            ),
            "inherited_by": ["implementation", "testing"],
        },
        {
            "id": "RU-CERT-GATE",
            "statement": (
                "WFA-0118 certification gate is absent; no workflow on this "
                "tree has been certified against the seven-condition gate."
            ),
            "settling_experiment": (
                "Deliver WFA-0118 and run the seven single-condition-removed "
                "refusals plus third-party re-derivation of any certification."
            ),
            "owner_visible_impact": (
                "Publishing or tournament units must treat every candidate as "
                "uncertified; a green IMP receipt is not a certification."
            ),
            "inherited_by": ["council", "implementation", "testing"],
        },
        {
            "id": "RU-FLOOR-160",
            "statement": (
                "WFA-0123 candidate-floor proof is absent; whether 160 "
                "classified-plus-provenance-plus-licence candidates exist is "
                "unmeasured."
            ),
            "settling_experiment": (
                "Deliver WFA-0123 with a three-way AND count and a second "
                "script written from the stopping-condition text alone."
            ),
            "owner_visible_impact": (
                "Program stopping condition 16 cannot be claimed; a raw 284 "
                "row count is not the floor."
            ),
            "inherited_by": ["council", "testing"],
        },
        {
            "id": "RU-EXECUTABLE-GAP",
            "statement": (
                "WFA-0124 executability gap is unmeasured; 108 blueprints must "
                "not be read as executable."
            ),
            "settling_experiment": (
                "Deliver WFA-0124: per-blueprint IR load plus smoke case, "
                "publish the measured executable count even if it is zero."
            ),
            "owner_visible_impact": (
                "Implementation may otherwise schedule 108 executable "
                "blueprints that have never been loaded."
            ),
            "inherited_by": ["implementation", "testing"],
        },
        {
            "id": "RU-LIBRARY-COVER",
            "statement": (
                "WFA-0125 library-category coverage matrix is absent; NEITHER "
                "cells are not yet routed as typed generation goals."
            ),
            "settling_experiment": (
                "Deliver WFA-0125 by parsing the spec's enumerated list and "
                "spot-checking every claimed cover."
            ),
            "owner_visible_impact": (
                "Council library work and IMP generation lanes lack a "
                "requirement-by-requirement cover table."
            ),
            "inherited_by": ["council", "implementation"],
        },
        {
            "id": "RU-SCOUT-FORGE-IR",
            "statement": (
                "WFA-0127 and WFA-0128 executable scout/forge IR specs are "
                "absent; this bucket did not ship those meta-workflows."
            ),
            "settling_experiment": (
                "Deliver WFA-0127 with the held-out known-answer test, then "
                "WFA-0128 with the mechanism-conflict no-improvement control."
            ),
            "owner_visible_impact": (
                "IMP-0209 and IMP-0212 cannot be driven from a WFA IR; they "
                "must not assume scout/forge already exist as archaeology output."
            ),
            "inherited_by": ["implementation", "testing"],
        },
        {
            "id": "RU-IMP-COUNT",
            "statement": (
                "The unit brief says implementation has 480 units; this "
                "catalog measures 470 IMP-* work_units."
            ),
            "settling_experiment": (
                "Recount catalog ids with prefix IMP- versus the brief string "
                "implementation 480 units and record which ten are missing "
                "or mis-prefixed."
            ),
            "owner_visible_impact": (
                "Capacity and dependency planning that uses 480 will be off "
                "by ten units on this tree."
            ),
            "inherited_by": ["implementation"],
        },
        {
            "id": "RU-OWNER-SIGNOFF",
            "statement": (
                "WFA-0126 requires owner sign-off on scope or terminal "
                "decision; no owner signature is present on this artifact."
            ),
            "settling_experiment": (
                "Owner reviews residual_unknowns and bucket_did_not, then "
                "sets owner_signoff.granted=true with a named signer, or "
                "rejects the scope in writing."
            ),
            "owner_visible_impact": (
                "This contract must not be read as owner-approved bucket "
                "completion or as a licence to treat residual unknowns as settled."
            ),
            "inherited_by": ["council", "implementation", "testing"],
        },
    ]


def bucket_did_not() -> list[dict]:
    return [
        {
            "id": "DN-SCHEMA-PACK",
            "statement": (
                "Did not author the 18-type WFA schema pack (WFA-0001); this "
                "unit only defines a local HandoffContract $def. The on-disk "
                "wfa-schema-pack.json is a generated $ref shim, not that pack."
            ),
        },
        {
            "id": "DN-REGISTRY-V2",
            "statement": (
                "Did not emit candidate registry v2 (WFA-0078) or the four "
                "graph artifacts (WFA-0079 through WFA-0081)."
            ),
        },
        {
            "id": "DN-QUERY",
            "statement": (
                "Did not ship the typed registry query interface (WFA-0084)."
            ),
        },
        {
            "id": "DN-EXECUTE-BLUEPRINTS",
            "statement": (
                "Did not execute any of the 108 discovery_only blueprints or "
                "measure an executable count (WFA-0124)."
            ),
        },
        {
            "id": "DN-CERTIFY",
            "statement": (
                "Did not certify any fused or source workflow (WFA-0118) and "
                "did not run fusion operators (WFA-0100 through WFA-0106)."
            ),
        },
        {
            "id": "DN-SCOUT-FORGE",
            "statement": (
                "Did not specify or execute workflow-scout or workflow-forge; "
                "those remain WFA-0127/WFA-0128 and IMP-0209/IMP-0212."
            ),
        },
        {
            "id": "DN-MANIFEST",
            "statement": (
                "Did not write command-center/ARTIFACT-MANIFEST.json or run "
                "tools/command-center/unit_manifest.py --write."
            ),
        },
        {
            "id": "DN-COMPLETENESS",
            "statement": (
                "Did not search the spec-enumerated source classes or prove "
                "the 160-candidate floor after trivial-fork discount "
                "(WFA-0160, WFA-0123)."
            ),
        },
        {
            "id": "DN-OWNER-COMPLETE",
            "statement": (
                "Did not obtain owner approval that the WFA bucket is complete "
                "or that residual unknowns may be ignored."
            ),
        },
    ]


def consumer_bindings() -> list[dict]:
    return [
        {
            "unit_id": "IMP-0209",
            "bucket": "implementation",
            "catalog_output_path": "command-center/receipts/IMP-0209.json",
            "consumes_unit_ids": [
                "WFA-0001",
                "WFA-0078",
                "WFA-0079",
                "WFA-0084",
                "WFA-0123",
                "WFA-0126",
            ],
            "first_output_kind": "scout-source-plan",
            "inherits_unknown_ids": [
                "RU-SCHEMA-PACK",
                "RU-QUERY-INTERFACE",
                "RU-BUCKET-ABSENT",
                "RU-SCOUT-FORGE-IR",
                "RU-FLOOR-160",
            ],
        },
        {
            "unit_id": "TST-0001",
            "bucket": "testing",
            "catalog_output_path": "command-center/receipts/TST-0001.json",
            "consumes_unit_ids": ["WFA-0118", "WFA-0126", "WFA-0134"],
            "first_output_kind": "predicate-bind-plan",
            "inherits_unknown_ids": [
                "RU-CERT-GATE",
                "RU-MANIFEST",
                "RU-SCHEMA-PACK",
            ],
        },
        {
            "unit_id": "CNL-0001",
            "bucket": "council",
            "catalog_output_path": (
                "command-center/design/council/CNL-0001-councilspec-v2-root-"
                "envelope-that-supersedes-council-chart.schema.json"
            ),
            "consumes_unit_ids": ["WFA-0077", "WFA-0125", "WFA-0126"],
            "first_output_kind": "library-cover-intake",
            "inherits_unknown_ids": [
                "RU-LIBRARY-COVER",
                "RU-OWNER-SIGNOFF",
                "RU-BUCKET-ABSENT",
            ],
        },
    ]


def downstream_buckets(catalog: dict, unknowns: list[dict]) -> dict:
    known = {u["id"] for u in unknowns}

    def inherit(*ids: str) -> list[str]:
        return [i for i in ids if i in known]

    return {
        "implementation": {
            "catalog_prefix": "IMP",
            "brief_unit_count": 480,
            "measured_unit_count": prefix_count(catalog, "IMP-"),
            "count_source": (
                "brief claimed 480; measured len(work_units id startswith IMP-)"
            ),
            "inherits_unknown_ids": inherit(
                "RU-BUCKET-ABSENT",
                "RU-SCHEMA-PACK",
                "RU-QUERY-INTERFACE",
                "RU-CERT-GATE",
                "RU-EXECUTABLE-GAP",
                "RU-SCOUT-FORGE-IR",
                "RU-IMP-COUNT",
                "RU-OWNER-SIGNOFF",
            ),
            "named_consumer_unit_id": "IMP-0209",
        },
        "testing": {
            "catalog_prefix": "TST",
            "brief_unit_count": 352,
            "measured_unit_count": prefix_count(catalog, "TST-"),
            "count_source": (
                "brief claimed 352; measured len(work_units id startswith TST-)"
            ),
            "inherits_unknown_ids": inherit(
                "RU-BUCKET-ABSENT",
                "RU-SCHEMA-PACK",
                "RU-MANIFEST",
                "RU-CERT-GATE",
                "RU-FLOOR-160",
                "RU-EXECUTABLE-GAP",
                "RU-OWNER-SIGNOFF",
            ),
            "named_consumer_unit_id": "TST-0001",
        },
        "council": {
            "catalog_prefix": "CNL",
            "brief_unit_count": 128,
            "measured_unit_count": prefix_count(catalog, "CNL-"),
            "count_source": (
                "brief claimed council 128; measured len(work_units id "
                "startswith CNL-); CNF is confirmation, not council"
            ),
            "inherits_unknown_ids": inherit(
                "RU-BUCKET-ABSENT",
                "RU-SCHEMA-PACK",
                "RU-LIBRARY-COVER",
                "RU-CERT-GATE",
                "RU-FLOOR-160",
                "RU-OWNER-SIGNOFF",
            ),
            "named_consumer_unit_id": "CNL-0001",
        },
    }


def manifest_check(rows: list[dict]) -> dict:
    declared = len(rows)
    present = sum(1 for r in rows if r["present"])
    hash_matched = 0
    for r in rows:
        if not r["present"]:
            continue
        live = measure_path(r["path"])
        if live["sha256"] and r["sha256"] and live["sha256"] == r["sha256"]:
            hash_matched += 1
        elif r["unit_id"] == "WFA-0126" and live["present"] and r["sha256"] is None:
            hash_matched += 1
    missing = sum(1 for r in rows if not r["present"])
    wfa_dir = REPO / "command-center" / "wfa"
    orphans = 0
    declared_paths = {r["path"] for r in rows}
    if wfa_dir.is_dir():
        for p in wfa_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if rel not in declared_paths:
                orphans += 1
    self_rows = [r for r in rows if r["unit_id"] == "WFA-0126"]
    this_hash = False
    if self_rows:
        live = measure_path(self_rows[0]["path"])
        this_hash = bool(live["present"])
    return {
        "checker": (
            "WFA-0083-equivalent: recompute sha256 after CRLF-to-LF; do not "
            "trust a recorded digest; do not run unit_manifest.py --write"
        ),
        "wfa0083_artifact_present": (REPO / WFA0083_REL).is_file(),
        "global_artifact_manifest_present": (REPO / GLOBAL_MANIFEST_REL).is_file(),
        "declared_count": declared,
        "present_count": present,
        "hash_matched_count": hash_matched,
        "missing_file_count": missing,
        "orphan_file_count": orphans,
        "this_unit_hash_recomputed": this_hash,
        "verdict": "BUCKET-INCOMPLETE" if missing else "BUCKET-REGISTERABLE",
    }


def both_states_schema(doc: dict) -> dict:
    """Mutant: strip settling_experiment from the first residual unknown."""
    mutant = json.loads(json.dumps(doc))
    del mutant["residual_unknowns"][0]["settling_experiment"]
    return mutant
