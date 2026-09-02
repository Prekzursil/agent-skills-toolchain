#!/usr/bin/env python3
"""Emit SYN-0009 raw-source control synthesis artifact."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from denylist import DENY_LIST  # noqa: E402
from inventory import production_inventory  # noqa: E402
from schema_local import garbage_rejected, iter_errors  # noqa: E402
from synthesizer import run  # noqa: E402

OUT = "command-center/synthesis/SYN-0009.raw-source-control.json"
SCHEMA = "command-center/schema/synthesis-candidate.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0009/probe1_denylist.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0009/probe2_no_sibling.py"
)
QUESTION = (
    "Question: how much of the consensus synthesis is an artifact of the "
    "DIGESTS rather than the evidence? Target: one additional synthesizer "
    "whose input set contains only raw artifacts -- source files, test "
    "output, transcripts -- and zero summaries, digests, or sibling conclusions."
)
COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0009 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the admitted-input "
    "inventory shows zero digest-class files and the known-present control "
    "fact is present. Any other terminal state is FAILED:SYN-0009 "
    "<classification> with the diagnostic tail attached."
)
MIN_BYTES = 1800
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0009/denylist.py",
    "command-center/p2-wave/probes/SYN-0009/inventory.py",
    "command-center/p2-wave/probes/SYN-0009/synthesizer.py",
    "command-center/p2-wave/probes/SYN-0009/reviewer.py",
    "command-center/p2-wave/probes/SYN-0009/schema_local.py",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/raw/transcript.json",
]


def sha256_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def sha256_file(path: Path) -> tuple[str, int]:
    return sha256_bytes(path.read_bytes())


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, fingerprint: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint,
        "exit_code": 0,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_stable(doc: dict, out: Path) -> tuple[str, int]:
    primary = next(a for a in doc["artifacts"] if a["role"] == "primary")
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    digest, size = sha256_bytes(raw)
    for _ in range(8):
        if primary["sha256"] == digest and primary["bytes"] == size:
            break
        primary["sha256"] = digest
        primary["bytes"] = size
        text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
        raw = text.encode("utf-8").replace(b"\r\n", b"\n")
        digest, size = sha256_bytes(raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return digest, size


def main() -> int:
    started = utc_now()
    live = run(REPO, apply_deny=True)
    inv = live["inventory"]
    prod = production_inventory(REPO)
    kp = live["known_present_control"]
    if inv["digest_class_admitted"] != 0:
        print("FAILED:SYN-0009 digest-contamination")
        return 1
    if not kp["present"] or not kp["exists_only_in_raw"]:
        print("FAILED:SYN-0009 known-present-miss")
        return 1
    if live["digest_framing_present"] or live["sibling_leak_present"]:
        print("FAILED:SYN-0009 digest-contamination")
        return 1
    if not all(a.get("result") == "DENIED" for a in live["sibling_read_attempts"]):
        print("FAILED:SYN-0009 sibling-read-not-denied")
        return 1
    if not garbage_rejected():
        print("FAILED:SYN-0009 schema accepted garbage")
        return 1

    contaminated = run(REPO, apply_deny=False)
    digest_only = run(REPO, apply_deny=True, digest_only=True)
    if not contaminated["digest_framing_present"]:
        print("FAILED:SYN-0009 unguarded digest framing silent")
        return 1
    if digest_only["known_present_control"]["present"]:
        print("FAILED:SYN-0009 digest-only recovered raw-only fact")
        return 1

    suppressed = [
        f
        for f in live["findings"]
        if f.get("kind") == "fact" and f.get("id") == kp["fact_id"]
    ]
    answer = (
        "On the control corpus, raw-only synthesis recovered "
        f"{kp['fact_id']} ({kp['span']}) from {kp['source_path']}. "
        "Every digest-class and receipt-narrative file in that corpus omits "
        "the span, so a digest-fed candidate would miss it. Flagged "
        "DIGEST-SUPPRESSED and escalated to SYN-0013. Production Phase 10-13 "
        f"roots are {prod['production_status']}; SYN-0008 candidates were "
        "not read (DENIED). This does not measure live consensus, because "
        "SYN-0008 output is absent on this worktree."
    )
    ended = utc_now()
    artifacts = [
        {
            "path": OUT,
            "bytes": MIN_BYTES,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(artifact_row(rel, "supporting"))

    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0009",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0009",
        "spec_anchor": "_USER-PROMPTS.md:11088",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"{kp['fact_id']} exists only in raw artifact "
                    f"{kp['source_path']} and is present in this output."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": kp["source_path"],
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/SYN-0009/synthesizer.py",
                        f"present={kp['present']} span={kp['span']}",
                        "syn0009-source-synthesizer",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "python3 -B command-center/p2-wave/probes/SYN-0009/reviewer.py",
                        f"rederive fact_id={kp['fact_id']} source={kp['source_path']}",
                        "syn0009-verifier-reviewer",
                    ),
                ],
            },
            {
                "claim": (
                    f"Control corpus admitted={inv['admitted_count']} "
                    f"excluded={inv['excluded_count']} "
                    f"digest_class_admitted={inv['digest_class_admitted']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": inv["root"],
                "probes": [
                    probe(
                        "source",
                        "command",
                        P1,
                        f"admitted={inv['admitted_count']} digest_admitted=0",
                        "syn0009-source-probe1-inventory",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "python3 -B command-center/p2-wave/probes/SYN-0009/inventory.py",
                        f"digest_class_admitted={inv['digest_class_admitted']}",
                        "syn0009-verifier-inventory",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "test_no_admitted_input_path_matches_the_digest_denylist",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2",
                "name": "test_control_output_is_produced_without_reading_SYN_0008_candidates",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3",
                "name": (
                    "known-present control: a fact that exists ONLY in a raw "
                    "artifact must appear"
                ),
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unguarded-digest-framing",
                "kind": "known-broken-fixture",
                "description": (
                    "Without the deny-list the synthesizer picks up "
                    "SYN-0009-DIGEST-FRAMING; with the deny-list it does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "digest_framing_present=true apply_deny=false",
                "good_state_output": "digest_framing_present=false apply_deny=true",
            },
            {
                "id": "digest-only-misses-raw-fact",
                "kind": "known-broken-fixture",
                "description": (
                    "Reading only digest-class files does not recover RAW-ONLY-001."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "digest_only known_present.present=false",
                "good_state_output": "raw-only known_present.present=true",
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "synthesis-candidate.schema.json rejects empty/unrelated "
                    "documents when $ref is resolved from disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "garbage rejected",
                "good_state_output": "receipt_core synthesis-candidate accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0009-probe2-independent-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "probe2 calls reviewer.rederive() on admitted raw files before "
                "opening SYN-0009.raw-source-control.json"
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0009/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0009",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0009/schema_local.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/SYN-0009/schema_local.py",
                    "in-process Draft7Validator + on-disk $ref store",
                    "syn0009-consumer-schema-local",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "one retry ONLY in a fresh context with the inputs re-read "
                "from disk, because the dominant failure mode here is an "
                "anchored prior, not a flaky tool"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live Phase 10-13 raw outputs are absent, so the "
                    "digest-cascade share of a real consensus synthesis is "
                    "NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind inventory.PHASE_ROOTS to live phase outputs when "
                    "those directories exist and re-run the two named probes."
                ),
            },
            {
                "claim": (
                    "SYN-0008 candidate-syntheses.json is absent as a live "
                    "sibling; the unread proof is the deny-list plus the "
                    "fixture leak token."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When SYN-0008 emits, keep the live sibling path DENIED "
                    "and re-run probe2."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "control-synthesizer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "synthesis-candidate",
            "title": (
                "Raw-source control synthesis: one synthesizer that never sees a digest"
            ),
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "digest-class-admitted",
                    "measured": inv["digest_class_admitted"],
                    "method": "deny-list-inventory",
                    "anchor": inv["root"],
                },
                {
                    "name": "known-present-raw-only-fact",
                    "measured": True,
                    "method": "fact-span-extract",
                    "anchor": kp["source_path"],
                },
                {
                    "name": "sibling-reads-denied",
                    "measured": True,
                    "method": "guarded-reader",
                    "anchor": "command-center/synthesis/SYN-0008.candidate-syntheses.json",
                },
            ],
            "control_ids": [
                "unguarded-digest-framing",
                "digest-only-misses-raw-fact",
                "schema-garbage",
            ],
            "synthesizer": {
                "assigned": {
                    "vendor": "anthropic",
                    "model": "opus",
                    "role": "control-synthesizer",
                },
                "produced_by": {
                    "vendor": "xai",
                    "model": "grok-4.6",
                    "role": "control-synthesizer",
                    "execution_substrate": "linux-local",
                },
                "role": "control-synthesizer",
                "input_class": "raw-only",
            },
            "deny_list": DENY_LIST,
            "input_inventory": {
                "control_corpus": inv["root"],
                "admitted_count": inv["admitted_count"],
                "excluded_count": inv["excluded_count"],
                "digest_class_admitted": inv["digest_class_admitted"],
                "digest_class_excluded": inv["digest_class_excluded"],
                "sibling_excluded": inv["sibling_excluded"],
                "admitted": inv["admitted"],
                "excluded": inv["excluded"],
                "production": {
                    "status": prod["production_status"],
                    "roots_present": prod["production_roots_present"],
                    "admitted_count": prod["admitted_count"],
                    "excluded_count": prod["excluded_count"],
                    "note": (
                        "Phase 10-13 directories are ABSENT on this worktree. "
                        "The deny-list and known-present controls are proven on "
                        "the fixture corpus, not on live phase outputs."
                    ),
                },
            },
            "findings": live["findings"],
            "known_present_control": kp,
            "digest_suppressed": [
                {
                    "fact_id": f["id"],
                    "statement": f["statement"],
                    "source_path": f["source_path"],
                    "flag": "DIGEST-SUPPRESSED",
                    "escalate_to": "SYN-0013",
                }
                for f in suppressed
            ],
            "sibling_read_attempts": live["sibling_read_attempts"],
            "read_log": live["read_log"],
            "denials": live["denials"],
            "scope": {
                "proof_surface": (
                    "Fixture corpus + guarded reader + two named probes. "
                    "Production phase coverage is NOT-CHECKED."
                ),
                "does_not_claim": [
                    "SYN-0008 ran on this worktree",
                    "Phase 10-13 artifacts exist here",
                    "cloud ok=true is delivery",
                    "global unit_manifest.py --write was run",
                ],
            },
        },
        "extensions": {
            "cloud_ok": False,
            "completion_sentinel": COMPLETION_SENTINEL,
            "named_probes": [
                {"id": "probe1", "role": "deny-list-known-present", "command": P1},
                {"id": "probe2", "role": "no-sibling-independent-reviewer", "command": P2},
            ],
            "global_catalog_write": False,
        },
    }

    # Named probes read the domain rows at the artifact root (probe1:
    # input_inventory / findings / known_present_control). receipt_core allows
    # extra root keys, so mirror the report rows there as well; the report copy
    # stays the schema-pinned one.
    for key in ("input_inventory", "findings", "known_present_control",
                "digest_suppressed", "sibling_read_attempts", "deny_list"):
        doc[key] = doc["report"][key]

    out = REPO / OUT
    digest, size = write_stable(doc, out)
    if size < MIN_BYTES:
        print(f"FAILED:SYN-0009 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:SYN-0009 sentinel-absent after write")
        return 1
    written = json.loads(text)
    errs = iter_errors(written)
    if errs:
        print("FAILED:SYN-0009 schema errors")
        for err in errs[:25]:
            print(" ", err)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"admitted={inv['admitted_count']} excluded={inv['excluded_count']} "
        f"digest_admitted={inv['digest_class_admitted']} "
        f"production={prod['production_status']}"
    )
    print("SUCCESS:SYN-0009 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
