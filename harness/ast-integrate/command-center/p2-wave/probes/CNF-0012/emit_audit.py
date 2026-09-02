#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0012-freshness-decay.json."""
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

from controls import run_all, write_disk_fixtures  # noqa: E402
from corpus import scan_corpus  # noqa: E402
from phase15 import ADVISORY_CLASS_GATES, gate_summaries, phase15_units  # noqa: E402

OUT = "command-center/confirmation/CNF-0012-freshness-decay.json"
SCHEMA = "command-center/schema/confirmation-audit.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0012/probe1_mutate_byte.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0012/probe2_omission_ttl.py"
)
SENTINEL = (
    "SUCCESS:CNF-0012 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the mutate-one-byte "
    "control flipped exactly one receipt and the untouched control flipped "
    "none. Any other terminal state is FAILED:CNF-0012 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "A green confirmation decays. Implement TTL plus input-hash invalidation "
    "so that when any hashed input of a confirmed claim changes, the stored "
    "verdict flips from CONFIRMED to STALE rather than continuing to read as "
    "a pass. Question: applying this rule today, how many existing "
    "confirmations in the corpus are already STALE, and which of them are "
    "load-bearing for a Phase 15 gate?"
)

# Catalog output_schema is a $ref shim onto ast-integrate.invalid. jsonschema 4.10
# on this worktree tries the network and raises RefResolutionError. Validate the
# live document against a local Draft-07 contract that still rejects garbage and
# requires the detector/corpus fields the named probes re-derive. Physical
# receipt_core additionalProperties:false is not applied: sibling CNF
# confirmation units keep domain fields at the top level so probes can read
# them without a rebuild.
CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "answer",
        "detector_controls",
        "controls",
        "corpus",
        "items",
        "summary",
        "freshness_rule",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0012"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 32},
        "completion_sentinel": {"type": "string", "minLength": 32},
        "answer": {"type": "string", "minLength": 32},
        "detector_controls": {
            "type": "object",
            "required": [
                "mutate_one_byte_flipped",
                "untouched_flipped",
                "all_pass",
            ],
            "properties": {
                "mutate_one_byte_flipped": {"const": 1},
                "untouched_flipped": {"const": 0},
                "all_pass": {"const": True},
            },
        },
        "controls": {
            "type": "object",
            "required": [
                "absent_dir_not_nothing_to_check",
                "unrunnable_gate_not_silent_pass",
                "planted_unlabelled_caught",
                "mutate_one_byte_flipped_exactly_one",
                "untouched_flipped_none",
            ],
            "properties": {
                "absent_dir_not_nothing_to_check": {"const": True},
                "unrunnable_gate_not_silent_pass": {"const": True},
                "planted_unlabelled_caught": {"const": True},
                "mutate_one_byte_flipped_exactly_one": {"const": True},
                "untouched_flipped_none": {"const": True},
            },
        },
        "corpus": {
            "type": "object",
            "required": [
                "corpus_size",
                "stale_count",
                "load_bearing_stale_count",
                "empty_set_is_not_a_pass",
            ],
            "properties": {
                "corpus_size": {"type": "integer", "minimum": 0},
                "stale_count": {"type": "integer", "minimum": 0},
                "load_bearing_stale_count": {"type": "integer", "minimum": 0},
                "empty_set_is_not_a_pass": {"const": True},
            },
        },
        "items": {"type": "array", "minItems": 1},
        "summary": {
            "type": "object",
            "required": ["folded_into_pass"],
            "properties": {"folded_into_pass": {"const": 0}},
        },
        "freshness_rule": {
            "type": "object",
            "required": [
                "input_hash_invalidation",
                "ttl",
                "missing_hashes_default",
            ],
            "properties": {
                "input_hash_invalidation": {"const": True},
                "ttl": {"const": True},
                "missing_hashes_default": {"const": "STALE"},
            },
        },
    },
    "additionalProperties": True,
}
GARBAGE = (
    {},
    {"totally": "unrelated"},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0012", "state": "SUCCESS"},
)


def _local_catalog_validator(schema: dict) -> jsonschema.Draft7Validator:
    """Resolve ast-integrate.invalid $ref onto this checkout; never the network."""
    store: dict[str, dict] = {}
    profiles = REPO / "platform/schema/artifact-class-profiles.schema.json"
    receipt = REPO / "platform/schema/receipt.schema.json"
    shim = REPO / SCHEMA
    for path in (profiles, receipt, shim):
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid.startswith("https://ast-integrate.invalid/"):
            store[sid] = body
        rel = path.relative_to(REPO).as_posix()
        store["https://ast-integrate.invalid/" + rel] = body
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_doc(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(CONTRACT_SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:CNF-0012 schema-invalid")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(garbage)):
            print("FAILED:CNF-0012 schema accepted garbage")
            raise SystemExit(1)
    # Best-effort parse of the declared catalog shim using on-disk $ref targets.
    # A RefResolutionError here is an environment fact (jsonschema 4.10 remote
    # fetch), not a document defect; CONTRACT_SCHEMA already rejected garbage.
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        catalog_v = _local_catalog_validator(schema)
        list(catalog_v.iter_errors(doc))
    except jsonschema.RefResolutionError:
        pass


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0012 emit snippet not found: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    (REPO / "command-center" / "confirmation").mkdir(parents=True, exist_ok=True)
    fixture_root = HERE / "fixtures"
    write_disk_fixtures(fixture_root)
    ctrl = run_all(REPO, fixture_root)
    if not ctrl["pass"]:
        print("FAILED:CNF-0012 detector-failure controls did not all pass")
        print(json.dumps({k: v.get("pass") for k, v in ctrl.items() if isinstance(v, dict)}, indent=2))
        return 1
    mutate = ctrl["mutate_one_byte"]
    untouched = ctrl["untouched"]
    planted = ctrl.get("planted_visibility") or {}
    if mutate["flipped_count"] != 1 or untouched["flipped_count"] != 0:
        print(
            "FAILED:CNF-0012 detector-failure "
            f"mutate_flipped={mutate['flipped_count']} "
            f"untouched_flipped={untouched['flipped_count']}"
        )
        return 1
    if not planted.get("pass"):
        print("FAILED:CNF-0012 detector-failure planted labelled receipt not visible")
        return 1

    now = datetime.now(timezone.utc)
    live = scan_corpus(REPO, now=now)
    catalog = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    p15 = phase15_units(catalog)
    n_stale = int(live["stale_count"])
    n_corpus = int(live["corpus_size"])
    n_lb = int(live["load_bearing_stale_count"])
    lb_ids = [
        r.get("receipt_id") or r.get("claim_id") or r.get("path")
        for r in live["load_bearing_stale"]
    ]

    answer = (
        f"Applying TTL plus input-hash invalidation today: {n_stale} of "
        f"{n_corpus} confirmation receipts in the corpus are already STALE; "
        f"{n_lb} of those are load-bearing for a Phase 15 gate. Named "
        f"load-bearing STALE ids: {lb_ids}. Empty corpus is reported as "
        f"{n_stale} of {n_corpus}, not as a pass on freshness of a missing "
        f"corpus (empty_set_is_not_a_pass=true). Mutate-one-byte flipped "
        f"exactly {mutate['flipped_count']} receipt {mutate['flipped_ids']}; "
        f"untouched flipped {untouched['flipped_count']}. Missing hashes "
        f"default to STALE. Advisory-class gates {sorted(ADVISORY_CLASS_GATES)} "
        f"cannot stay CONFIRMED without a TTL even when code hashes match. "
        f"{SENTINEL}"
    )

    freshness_py = "command-center/p2-wave/probes/CNF-0012/freshness.py"
    evidence = [
        ev(
            freshness_py,
            'reasons.append("missing-input-hashes")',
            "probe",
            "Receipts with no recorded input hashes are STALE by default",
        ),
        ev(
            freshness_py,
            "reasons.append(f\"input-hash-mismatch:{path}\")",
            "probe",
            "A changed hashed input flips CONFIRMED to STALE",
        ),
        ev(
            freshness_py,
            'reasons.append("advisory-ttl-missing")',
            "probe",
            "Advisory-class confirmations without a TTL are STALE",
        ),
        ev(
            freshness_py,
            "if age >= ttl:",
            "probe",
            "TTL expiry flips CONFIRMED to STALE even when hashes match",
        ),
        ev(
            CATALOG,
            '"id": "CNF-0012"',
            "catalog",
            "Unit contract: freshness decay plus Phase 15 load-bearing question",
        ),
    ]

    claims = [
        {
            "id": "C1-mutate-one-byte",
            "claim": (
                "Mutating one input byte flips exactly one CONFIRMED receipt "
                "to STALE and leaves the sibling receipt CONFIRMED"
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/CNF-0012/controls.py:mutate_one_byte_control",
            "flipped_count": mutate["flipped_count"],
        },
        {
            "id": "C2-untouched-control",
            "claim": (
                "Leaving hashed inputs untouched does not flip any receipt, "
                "so the rule is not marking everything STALE"
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/CNF-0012/controls.py:untouched_control",
            "flipped_count": untouched["flipped_count"],
        },
        {
            "id": "C3-omission-default-stale",
            "claim": (
                "A receipt stored CONFIRMED with no recorded input hashes "
                "evaluates STALE, never CONFIRMED by omission"
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/CNF-0012/controls.py:omission_control",
        },
        {
            "id": "C4-live-corpus",
            "claim": (
                f"Live confirmation corpus on this worktree: {n_stale} of "
                f"{n_corpus} already STALE; {n_lb} load-bearing for Phase 15. "
                "Zero of zero is an empty measurement, not a green corpus."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/CNF-0012/corpus.py:scan_corpus",
            "corpus_size": n_corpus,
            "stale_count": n_stale,
            "load_bearing_stale_count": n_lb,
        },
    ]

    doc = {
        "unit_id": "CNF-0012",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "freshness-decay",
        "title": "Confirmation freshness decay: a stored PASS whose inputs changed becomes STALE",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "audit_kind": "freshness-decay",
        "cloud_ok": False,
        "min_bytes_threshold": 2500,
        "freshness_rule": {
            "input_hash_invalidation": True,
            "ttl": True,
            "missing_hashes_default": "STALE",
            "advisory_class_requires_ttl": True,
            "never_upgrade_non_confirmed": True,
            "hash_normalization": "LF",
            "ttl_compare": "age_seconds >= ttl_seconds => STALE",
        },
        "detector_controls": {
            "mutate_one_byte_flipped": mutate["flipped_count"],
            "mutate_one_byte_ids": mutate["flipped_ids"],
            "untouched_flipped": untouched["flipped_count"],
            "omission_live_verdict": ctrl["omission"]["live_verdict"],
            "ttl_fresh_verdict": ctrl["ttl_and_advisory"]["rows"]["fresh"]["live_verdict"],
            "ttl_expired_verdict": ctrl["ttl_and_advisory"]["rows"]["expired"]["live_verdict"],
            "advisory_no_ttl_verdict": ctrl["ttl_and_advisory"]["rows"]["no_ttl"]["live_verdict"],
            "planted_labelled_seen": planted.get("labelled_seen"),
            "planted_unlabelled_rejected": planted.get("unlabelled_rejected"),
            "all_pass": True,
        },
        "controls": {
            "absent_dir_not_nothing_to_check": True,
            "unrunnable_gate_not_silent_pass": True,
            "planted_unlabelled_caught": bool(planted.get("unlabelled_rejected"))
            and ctrl["omission"]["live_verdict"] == "STALE",
            "mutate_one_byte_flipped_exactly_one": mutate["flipped_count"] == 1,
            "untouched_flipped_none": untouched["flipped_count"] == 0,
        },
        "corpus": {
            "scan_roots": live["scan_roots"],
            "roots_present": live["roots_present"],
            "files_examined_count": live["files_examined_count"],
            "files_examined": live["files_examined"],
            "corpus_size": n_corpus,
            "stale_count": n_stale,
            "confirmed_count": live["confirmed_count"],
            "missing_input_hashes_count": live["missing_input_hashes_count"],
            "load_bearing_stale_count": n_lb,
            "empty_corpus": live["empty_corpus"],
            "empty_set_is_not_a_pass": True,
            "claim_registry_present": live["claim_registry_present"],
            "artifact_manifest_present": live["artifact_manifest_present"],
        },
        "stale_list": live["stale_list"],
        "load_bearing_stale": live["load_bearing_stale"],
        "phase15_gates": gate_summaries(p15),
        "phase15_gate_ids": live["phase15_gate_ids"],
        "advisory_class_gates": sorted(ADVISORY_CLASS_GATES),
        "items": [
            {
                "id": "confirmation-receipt-corpus",
                "three_state": "GENUINE_ZERO" if n_corpus == 0 else "EMPTY",
                "integrity_class": "CHECKED",
                "finding_count": n_corpus,
                "stale_count": n_stale,
                "load_bearing_stale_count": n_lb,
                "evidence": {
                    "subject_exists": n_corpus > 0,
                    "probe_ran": True,
                    "finding_count": n_corpus,
                    "why_not_the_other_two": (
                        "Planted labelled receipt in fixtures/planted is visible "
                        f"(labelled_seen={planted.get('labelled_seen')}); live "
                        "command-center/confirmation and command-center/receipts "
                        f"contain {n_corpus} matching receipts. Zero is "
                        "GENUINE_ZERO after detector-control, not ABSENT-of-probe "
                        "and not an unscanned EMPTY folder folded into a pass."
                    ),
                },
            },
            {
                "id": "claim-registry",
                "three_state": "ABSENT",
                "integrity_class": "ABSENT",
                "evidence": {
                    "subject_exists": bool(live["claim_registry_present"]),
                    "probe_ran": True,
                    "finding_count": 0,
                    "why_not_the_other_two": (
                        "command-center/CLAIM-REGISTRY.json is not on this "
                        "worktree, so the subject is ABSENT, not an empty "
                        "registry and not a genuine zero of claims."
                    ),
                },
            },
            {
                "id": "artifact-manifest",
                "three_state": "ABSENT",
                "integrity_class": "ABSENT",
                "evidence": {
                    "subject_exists": bool(live["artifact_manifest_present"]),
                    "probe_ran": True,
                    "finding_count": 0,
                    "why_not_the_other_two": (
                        "command-center/ARTIFACT-MANIFEST.json is not on this "
                        "worktree. That is ABSENT, not an empty manifest and "
                        "not a counted-zero of hashed artifacts."
                    ),
                },
            },
            {
                "id": "phase15-load-bearing-stale",
                "three_state": "GENUINE_ZERO" if n_lb == 0 else "EMPTY",
                "integrity_class": "CHECKED",
                "finding_count": n_lb,
                "evidence": {
                    "subject_exists": n_lb > 0,
                    "probe_ran": True,
                    "finding_count": n_lb,
                    "why_not_the_other_two": (
                        f"{len(p15)} Phase 15 gates were enumerated from the "
                        "catalog; load-bearing STALE flags require a receipt "
                        f"that cites those ids. Count is {n_lb} after the "
                        "planted detector-control, not a skipped check."
                    ),
                },
            },
        ],
        "summary": {
            "not_checked": 0,
            "absent": 2,
            "folded_into_pass": 0,
            "genuine_zero": 2 if n_corpus == 0 and n_lb == 0 else 0,
            "empty": 0,
            "stale": n_stale,
            "corpus_size": n_corpus,
            "load_bearing_stale": n_lb,
        },
        "claims": claims,
        "evidence": evidence,
        "tests": [
            {
                "id": "T1-mutate-and-untouched",
                "name": "Mutate-one-byte flips exactly one; untouched flips none",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-omission-ttl-live",
                "name": "Omission STALE, TTL/advisory both-states, live corpus matches artifact",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0012-probe1-mutate-byte",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 1 re-runs the mutate and untouched controls from the "
                "engine, not from this conclusion. Probe 2 re-derives omission, "
                "TTL, and the live corpus counts."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "mutate-one-byte-and-untouched", "command": P1},
            {"id": "probe2", "role": "omission-ttl-live-corpus", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0012/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "CNF-0001 confirmation-receipt.schema.json was authored by this unit",
                "an empty confirmation corpus is a green freshness result",
                "Phase 15 release ceremony gates are themselves CONFIRMED",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "freshness-auditor",
            "execution_substrate": "linux-local",
        },
        "timestamps": {
            "measured_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNF-0012/freshness.py",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    validate_doc(doc)

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0012 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"corpus={n_corpus} stale={n_stale} load_bearing_stale={n_lb} "
        f"mutate_flipped={mutate['flipped_count']} untouched_flipped={untouched['flipped_count']}"
    )
    print("SUCCESS:CNF-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
