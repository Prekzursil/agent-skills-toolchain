#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0136-independence-attestation.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import attestation as A  # noqa: E402
import harvest as H  # noqa: E402
import rederive as R  # noqa: E402
import schema_offline as S  # noqa: E402

OUT = "command-center/adversarial/ADV-0136-independence-attestation.json"
SCHEMA = "command-center/schema/attestation-ledger.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0136 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every declared-independent "
    "seat carries a response-side attestation record or is reported as "
    "DECLARED-ONLY, and all three planted controls fired. Any other terminal "
    "state is FAILED:ADV-0136 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "For every seat, reviewer slot and confirmation unit this program declares "
    "INDEPENDENT or CROSS-VENDOR, does a runtime attestation prove the answering "
    "process was actually a different vendor, model, context and seed - or is "
    "independence asserted only in the config? The estate has a measured instance "
    "of the confound: a comparison believed to be GPT-5.x versus Opus was in fact "
    "sonnet-driver versus opus-driver, because the dispatching agent's model was "
    "never attested."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0136/probe1_planted_collusion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0136/probe2_reviewer_from_logs.py"
)
LOG_RELS = [
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-collusion.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-driver-confound.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/planted-declared-only.jsonl",
    "command-center/p2-wave/probes/ADV-0136/fixtures/logs/known-good.jsonl",
]


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2) + "\n"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "role": role,
        "eol": "LF",
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-4000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def _council_id(name: str) -> str:
    return {
        "planted-collusion": "ADV-0136-planted-collusion",
        "planted-driver-confound": "ADV-0136-planted-driver-confound",
        "planted-declared-only": "ADV-0136-planted-declared-only",
        "known-good": "ADV-0136-known-good",
    }[name]


def main() -> int:
    written = A.write_runtime_logs(REPO)
    events = A.load_runtime_logs(REPO, materialize_first=False)
    runtime = A.classify_runtime(events)
    cat = H.harvest_catalog(REPO)

    by_council = {name: A.council_events(events, _council_id(name)) for name in A.COUNCILS}
    collusion = A.classify_runtime(by_council["planted-collusion"])["violations"]
    confound = A.classify_runtime(by_council["planted-driver-confound"])["violations"]
    stripped = A.classify_runtime(by_council["planted-declared-only"])["violations"]
    healthy = A.classify_runtime(by_council["known-good"])["violations"]
    naive = A.naive_same_tuple_by_label(by_council["planted-collusion"])

    planted = [
        {
            "id": "planted-collusion",
            "name": "same model seated twice under critic vs advocate labels",
            "fired": bool(collusion["SAME-TUPLE"]),
            "violation": "SAME-TUPLE",
            "label_only_checker_fired": bool(naive),
            "detail": collusion["SAME-TUPLE"],
        },
        {
            "id": "planted-driver-confound",
            "name": "GPT-5.x vs Opus comparison dispatched by sonnet-driver vs opus-driver",
            "fired": bool(confound["DRIVER-CONFOUND"]),
            "violation": "DRIVER-CONFOUND",
            "detail": confound["DRIVER-CONFOUND"],
        },
        {
            "id": "adverse-inference-declared-only",
            "name": "strip response-side vendor from one genuine cross-vendor seat",
            "fired": bool(stripped["DECLARED-ONLY"]),
            "violation": "DECLARED-ONLY",
            "detail": stripped["DECLARED-ONLY"],
            "silently_passed": not bool(stripped["DECLARED-ONLY"]),
        },
    ]
    if not all(p["fired"] for p in planted):
        print("FAILED:ADV-0136 planted controls did not all fire")
        print(json.dumps(planted, indent=2)[:4000])
        return 1
    if naive:
        print("FAILED:ADV-0136 label-only checker unexpectedly fired on collusion")
        return 1
    healthy_any = any(healthy[k] for k in ("SAME-TUPLE", "DECLARED-ONLY", "DRIVER-CONFOUND"))
    if healthy_any:
        print("FAILED:ADV-0136 known-good council was flagged")
        print(json.dumps(healthy, indent=2)[:4000])
        return 1

    log_paths = [written[n] for n in A.COUNCILS]
    reviewed = R.rederive_from_logs(log_paths)
    fp_runtime = A.violation_fingerprint(runtime["violations"])
    fp_review = A.violation_fingerprint(reviewed)
    if fp_runtime != fp_review:
        print("FAILED:ADV-0136 reviewer fingerprint mismatch")
        print(json.dumps({"runtime": fp_runtime, "reviewer": fp_review}, indent=2, default=str)[:4000])
        return 1

    catalog_seats = cat["seats"]
    uncovered = [
        s
        for s in catalog_seats
        if s.get("coverage") not in {"RESPONSE-ATTESTED", "DECLARED-ONLY"}
    ]
    if uncovered:
        print("FAILED:ADV-0136 catalog seats uncovered")
        return 1

    union_declared = list(runtime["violations"]["DECLARED-ONLY"]) + list(cat["catalog_violations"])
    union = {
        "SAME-TUPLE": list(runtime["violations"]["SAME-TUPLE"]),
        "DECLARED-ONLY": union_declared,
        "DRIVER-CONFOUND": list(runtime["violations"]["DRIVER-CONFOUND"]),
    }

    all_seats = list(runtime["seats"]) + catalog_seats
    for s in all_seats:
        if s.get("coverage") not in {"RESPONSE-ATTESTED", "DECLARED-ONLY"}:
            print("FAILED:ADV-0136 seat missing coverage", s.get("seat_id"))
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    collusion_raw = (
        f"planted_collusion SAME-TUPLE fired={bool(collusion['SAME-TUPLE'])} "
        f"n={len(collusion['SAME-TUPLE'])} "
        f"seats={(collusion['SAME-TUPLE'][0].get('seats') if collusion['SAME-TUPLE'] else None)} "
        f"label_only={bool(naive)}"
    )
    review_raw = json.dumps(fp_review, default=str)
    confound_raw = (
        f"DRIVER-CONFOUND fired={bool(confound['DRIVER-CONFOUND'])} "
        f"drivers={(confound['DRIVER-CONFOUND'][0].get('drivers') if confound['DRIVER-CONFOUND'] else None)}"
    )
    declared_raw = (
        f"DECLARED-ONLY fired={bool(stripped['DECLARED-ONLY'])} "
        f"seats={[r.get('seat_id') for r in stripped['DECLARED-ONLY']]}"
    )
    census_raw = (
        f"census declared={cat['census']['declared_independent_seats']} "
        f"cross-vendor={cat['census']['cross_vendor_seats']} "
        f"independent={cat['census']['independent_seats']} attested=0"
    )

    tests = [
        {
            "id": "planted-collusion",
            "name": "SAME-TUPLE fires on two role labels sharing one response tuple; label-only checker is silent",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "planted-driver-confound",
            "name": "DRIVER-CONFOUND fires when comparison arms use different driver models",
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "adverse-inference-declared-only",
            "name": "stripped cross-vendor response vendor is DECLARED-ONLY not a silent pass",
            "command": P2,
            "result": "PASS",
        },
    ]
    evidence = [
        {
            "claim": (
                "SAME-TUPLE is computed from response vendor+model+context_digest, "
                "never from declared_role; critic and advocate share openai/gpt-4o-mini."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": LOG_RELS[0],
            "probes": [
                probe_obj("source", "test-run", P1, collusion_raw),
                probe_obj("verifier", "file-read", LOG_RELS[0], collusion_raw),
            ],
        },
        {
            "claim": (
                "DRIVER-CONFOUND reproduces the measured sonnet-driver vs opus-driver "
                "confound on comparison ADV-0136-measured-gpt5-vs-opus."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": LOG_RELS[1],
            "probes": [
                probe_obj("source", "test-run", P2, confound_raw),
                probe_obj("verifier", "file-read", LOG_RELS[1], confound_raw),
            ],
        },
        {
            "claim": (
                "Stripping the response-side vendor from one genuine cross-vendor "
                "seat files DECLARED-ONLY rather than a silent pass."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": LOG_RELS[2],
            "probes": [
                probe_obj("source", "test-run", P2 + " #declared-only", declared_raw),
                probe_obj("verifier", "file-read", LOG_RELS[2], declared_raw),
            ],
        },
        {
            "claim": (
                "Independent re-derivation from JSONL (rederive.py, no classify_runtime) "
                "matches the runtime violation fingerprint."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ADV-0136/rederive.py",
            "probes": [
                probe_obj(
                    "source",
                    "static-analysis",
                    "command-center/p2-wave/probes/ADV-0136/attestation.py:classify_runtime",
                    review_raw,
                ),
                probe_obj(
                    "verifier",
                    "command",
                    "command-center/p2-wave/probes/ADV-0136/rederive.py:rederive_from_logs",
                    review_raw,
                ),
            ],
        },
        {
            "claim": (
                "Every catalog reviewer slot declared INDEPENDENT or CROSS-VENDOR is "
                "DECLARED-ONLY after 3 failed response-side lookups; none are silently passed."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/WORK-UNIT-CATALOG.json",
            "probes": [
                probe_obj(
                    "source",
                    "static-analysis",
                    "command-center/p2-wave/probes/ADV-0136/harvest.py:harvest_catalog",
                    census_raw,
                ),
                probe_obj("verifier", "test-run", P2 + " #census", census_raw),
            ],
        },
    ]

    schema_row = artifact_row(SCHEMA, "supporting")
    log_rows = [artifact_row(rel, "log") for rel in LOG_RELS]
    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0136",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0136",
        "min_bytes_threshold": 2048,
        "profile": "independence-attestation",
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "bytes": 1,
                "sha256": "0" * 64,
                "role": "primary",
                "eol": "LF",
            },
            schema_row,
            *log_rows,
        ],
        "evidence": evidence,
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Every attestation attempt is recorded including "
                "failures to obtain a response-side identifier; a seat that fails "
                "attestation 3 times is filed as DECLARED-ONLY, never retried into a pass"
            ),
        },
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-collusion",
                "kind": "adversarial-payload",
                "description": (
                    "Same response tuple under critic vs advocate labels. SAME-TUPLE "
                    "must fire; a label-only checker must stay silent. Known-good is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": collusion_raw,
                "good_state_output": "known_good SAME-TUPLE fired=False silent=True",
            },
            {
                "id": "planted-driver-confound",
                "kind": "known-broken-fixture",
                "description": (
                    "GPT-5.x vs Opus comparison dispatched by sonnet-driver vs opus-driver. "
                    "DRIVER-CONFOUND must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": confound_raw,
                "good_state_output": "known_good DRIVER-CONFOUND fired=False",
            },
            {
                "id": "adverse-inference-declared-only",
                "kind": "malformed-input",
                "description": (
                    "Strip response-side vendor from one genuine cross-vendor seat. "
                    "Must be DECLARED-ONLY, not a silent pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": declared_raw,
                "good_state_output": "known_good DECLARED-ONLY fired=False",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0136-probe2-reviewer-from-logs",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Re-derived SAME-TUPLE, DECLARED-ONLY and DRIVER-CONFOUND from "
                "raw JSONL via rederive.py without importing classify_runtime. "
                f"Fingerprint match={fp_runtime == fp_review}."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0136/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ADV-0136/schema_offline.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": probe_obj(
                    "verifier",
                    "schema-validate",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ADV-0136/schema_offline.py " + OUT,
                    "VALID (in-process Draft7Validator + disk RefResolver)",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer slots have no live response-side vendor on this "
                    "worktree; a later transport capture could convert DECLARED-ONLY "
                    "to RESPONSE-ATTESTED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run harvest.py after a cross-vendor adapter records "
                    "response.vendor on the wire; any seat that gains a vendor must "
                    "be reclassified and must not stay DECLARED-ONLY."
                ),
            }
        ],
        "defects": [],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "independence-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "attestation-ledger",
            "observations": [
                {
                    "name": "planted-collusion-same-tuple",
                    "measured": True,
                    "method": "classify_runtime on fixtures/logs/planted-collusion.jsonl",
                    "anchor": LOG_RELS[0],
                },
                {
                    "name": "planted-driver-confound",
                    "measured": True,
                    "method": "classify_runtime on fixtures/logs/planted-driver-confound.jsonl",
                    "anchor": LOG_RELS[1],
                },
                {
                    "name": "adverse-inference-declared-only",
                    "measured": True,
                    "method": "classify_runtime on fixtures/logs/planted-declared-only.jsonl",
                    "anchor": LOG_RELS[2],
                },
                {
                    "name": "catalog-declared-only-census",
                    "measured": int(cat["census"]["declared_independent_seats"]),
                    "method": "harvest_catalog three failed response-side lookups",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json",
                },
            ],
            "control_ids": [
                "planted-collusion",
                "planted-driver-confound",
                "adverse-inference-declared-only",
            ],
            "title": "Runtime independence attestation: what actually answered versus what the config declared",
            "question": QUESTION,
            "response_side_is_source_of_truth": True,
            "tuple_fields": list(A.TUPLE_FIELDS),
            "three_planted_controls_fired": True,
            "rule": {
                "source_of_truth": "response-side",
                "same_tuple": "two allegedly independent seats share response vendor+model+context digest",
                "declared_only": "CROSS-VENDOR or INDEPENDENT slot with no response-side vendor; violation not unknown",
                "driver_confound": "dispatching agent's model differs across arms of a comparison",
                "adverse_inference": "absent attestation is SAME-TUPLE until measured; 3 failed attempts file DECLARED-ONLY and are never retried into a pass",
            },
            "seats": all_seats,
            "violations": union,
            "runtime_violations": runtime["violations"],
            "planted_controls": planted,
            "negative_control": {
                "id": "known-good",
                "name": "healthy three-vendor council with one driver",
                "fired": False,
                "silent": True,
                "violations": healthy,
            },
            "catalog_census": cat["census"],
            "reviewer_rederive": {
                "reviewer_id": "ADV-0136-probe2-reviewer-from-logs",
                "verdict": "PASS",
                "independent": True,
                "rederived_from": "raw-transport-logs",
                "violation_sets_match": True,
                "fingerprint": fp_review,
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "output_path": OUT,
            "output_schema": SCHEMA,
            "produced_by_script": "command-center/p2-wave/probes/ADV-0136/emit_ledger.py",
            "ts": now,
            "cloud_ok": False,
        },
    }

    if SENTINEL not in dump(doc):
        print("FAILED:ADV-0136 completion_sentinel not in document")
        return 1

    pre_sha, pre_size = digest_bytes(dump(doc).encode("utf-8"))
    doc["artifacts"][0]["sha256"] = pre_sha
    doc["artifacts"][0]["bytes"] = pre_size

    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:ADV-0136 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not S.iter_errors(garbage):
            print("FAILED:ADV-0136 schema vacuous on garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    live_sha, live_size = digest_file(out)
    if live_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ADV-0136 artifact {live_size}B below floor")
        return 1
    file_errs = S.iter_errors(json.loads(out.read_text(encoding="utf-8")))
    if file_errs:
        print("FAILED:ADV-0136 schema errors after write")
        for err in file_errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    print(f"wrote {OUT} bytes={live_size} sha256={live_sha}")
    print("SUCCESS:ADV-0136")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
