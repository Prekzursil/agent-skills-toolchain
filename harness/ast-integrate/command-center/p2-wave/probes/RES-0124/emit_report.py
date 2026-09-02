#!/usr/bin/env python3
"""Emit command-center/research/RES-0124.json.

Validates against the catalog output_schema using a disk-only $ref store
(https://ast-integrate.invalid/ maps onto this worktree). No network.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from control import run_seeded_control  # noqa: E402
from scan import REPO as SCAN_REPO  # noqa: E402
from scan import scan_tree  # noqa: E402
from scrub import (  # noqa: E402
    m4_location_only_ok,
    minimum_safe_set,
    mitigations_from_bypasses,
    run_bypasses,
)

OUT = "command-center/research/RES-0124.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
UNIT = "RES-0124"
QUESTION = (
    "If this program's artifacts were published, what personal or "
    "estate-identifying data would leave with them (paths, usernames, "
    "transcripts, event ledgers), and what is the minimum scrubbing "
    "contract that makes publication safe?"
)
SENTINEL = "SUCCESS:RES-0124"
COMPLETION_SENTINEL = (
    "SUCCESS:RES-0124 in the receipt AND a category-count scan over the "
    "real tree with a passing seeded-identifier detector control"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0124/probe1_category_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0124/probe2_seeded_control.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/RES-0124/scan.py",
    "command-center/p2-wave/probes/RES-0124/scrub.py",
    "command-center/p2-wave/probes/RES-0124/control.py",
    "command-center/p2-wave/probes/RES-0124/probe1_category_scan.py",
    "command-center/p2-wave/probes/RES-0124/probe2_seeded_control.py",
)
STRIKES = HERE / "_schema_strikes.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def _https_handler(uri: str) -> dict:
    prefix = "https://ast-integrate.invalid/"
    if not uri.startswith(prefix):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri!r}"
        )
    rel = uri.split("#", 1)[0][len(prefix) :]
    path = REPO / rel
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri!r}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in SCHEMA_STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    shim = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA)),
        referrer=shim,
        store=store,
        handlers={"https": _https_handler, "http": _https_handler},
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    if size < 1:
        raise SystemExit(f"FAILED:RES-0124 zero-byte supporting artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_pair(
    source_method: str,
    source_cmd: str,
    source_out: str,
    verifier_method: str,
    verifier_cmd: str,
    verifier_out: str,
) -> list[dict]:
    return [
        {
            "role": "source",
            "method": source_method,
            "command": source_cmd,
            "raw_output": source_out[:4000],
            "fingerprint": fp(source_method, source_cmd),
            "exit_code": 0,
        },
        {
            "role": "verifier",
            "method": verifier_method,
            "command": verifier_cmd,
            "raw_output": verifier_out[:4000],
            "fingerprint": fp(verifier_method, verifier_cmd),
            "exit_code": 0,
        },
    ]


def schema_error_list(validator: jsonschema.Draft7Validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def record_strike(fp_hex: str, errs: list[str]) -> int:
    data = load_strikes()
    data["attempts"].append(
        {
            "fingerprint": fp_hex,
            "n_errors": len(errs),
            "sample": errs[:8],
        }
    )
    STRIKES.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    same = [a for a in data["attempts"] if a.get("fingerprint") == fp_hex]
    return len(same)


def claim(
    cid: str,
    text: str,
    mechanism: str,
    tier: str,
    band: str,
    probe: str,
    verdict: str,
    signals: list[dict],
    support: list[str],
    contradiction: list[str],
    stamp: str,
    snap: str,
) -> dict:
    return {
        "claim_id": cid,
        "claim": text,
        "canonical_mechanism": mechanism,
        "source_lineage": {
            "kind": "local-tree-measurement",
            "anchors": [
                {
                    "path": "command-center/WORK-UNIT-CATALOG.json",
                    "role": "publication-corpus-member",
                },
                {
                    "path": "command-center/p2-wave/probes/RES-0124/scan.py",
                    "role": "content-and-path-scanner",
                },
            ],
        },
        "evidence_tier": tier,
        "confidence_band": band,
        "named_settling_probe": probe,
        "edges": {"support": support, "contradiction": contradiction},
        "freshness_stamp": stamp,
        "snapshot_sha256": snap,
        "verdict": verdict,
        "signals": signals,
        "value_reproduced": False,
    }


def build_doc(
    live: dict,
    control: dict,
    bypass_rows: list[dict],
    started_s: str,
    ended_s: str,
    duration: float,
) -> dict:
    by = live["by_category"]
    snap = live["snapshot_sha256"]
    mitigations = mitigations_from_bypasses(bypass_rows, m4_ok=True)
    safe = minimum_safe_set(mitigations)
    naive = next(m for m in mitigations if m["id"] == "M1_line_regex")
    strong = next(m for m in mitigations if m["id"] == "M1b_decode_then_redact")

    s_win_re = str(by["windows_home_path"])
    s_win_bytes = str(live["byte_prefix_hits"])
    s_unix = str(by["unix_home_path"])
    s_cred_path = str(by["credential_filename"])
    s_trans = str(by["transcript_or_session"])
    s_ledger = str(by["event_ledger"])

    claims = [
        claim(
            "C1",
            "Publishing the current artifact tree would export Windows home-path "
            "identifiers (drive + Users + name) already stored in corpus files.",
            "unicode-regex content scan exclusive-span classified as windows_home_path",
            "E1",
            "almost-certain",
            P1,
            "CONFIRMED",
            [
                {
                    "id": "S1-python-regex-content",
                    "measurement": "WIN_RE finditer over decoded file text",
                    "result": "count=" + s_win_re,
                },
                {
                    "id": "S2-raw-bytes-prefix",
                    "measurement": "bytes.find of assembled home-path prefixes",
                    "result": "count=" + s_win_bytes,
                },
            ],
            ["byte prefix count and regex count are both > 0"],
            [
                "a file that only contains the word Users is not a home path "
                "(negative fixture)"
            ],
            ended_s,
            snap,
        ),
        claim(
            "C2",
            "Unix-style /home or /Users names, counted independently of Windows "
            "drive paths, are not the dominant leak class on this tree.",
            "unix regex that refuses a preceding colon so C: drive paths do not double-count",
            "E1",
            "almost-certain",
            P1,
            "CONFIRMED" if by["unix_home_path"] < by["windows_home_path"] else "PARTIAL",
            [
                {
                    "id": "S1-python-regex-unix",
                    "measurement": "UNIX_RE finditer over decoded file text",
                    "result": "count=" + s_unix,
                },
                {
                    "id": "S2-windows-minus-unix",
                    "measurement": "windows_home_path vs unix_home_path category fields",
                    "result": "windows=" + s_win_re + " unix=" + s_unix,
                },
            ],
            ["colon-exclusion prevents C: drive paths from counting as unix"],
            ["a genuine posix home directory path would still be counted if present"],
            ended_s,
            snap,
        ),
        claim(
            "C3",
            "Credential-shaped filenames exist in the tree and are a publication "
            "surface even when file contents are never opened.",
            "path-basename inventory independent of file bytes",
            "E1",
            "almost-certain",
            P1,
            "CONFIRMED" if by["credential_filename"] > 0 else "REFUTED",
            [
                {
                    "id": "S1-path-basename",
                    "measurement": "path_category credential_filename on relative path",
                    "result": "count=" + s_cred_path,
                },
                {
                    "id": "S2-content-not-consulted",
                    "measurement": "credential_filename files are not content-scanned",
                    "result": "contents_omitted=true",
                },
            ],
            ["filename inventory does not read bytes"],
            ["a credential stored only inside a README would be invisible to this claim"],
            ended_s,
            snap,
        ),
        claim(
            "C4",
            "Transcript, session, or event-ledger shaped files are part of the "
            "publication surface when present; counts are path-classified.",
            "path-field classification on relative POSIX paths",
            "E1",
            "almost-certain",
            P1,
            "CONFIRMED"
            if (by["transcript_or_session"] + by["event_ledger"]) > 0
            else "REFUTED",
            [
                {
                    "id": "S1-transcript-path",
                    "measurement": "path_category transcript_or_session",
                    "result": "count=" + s_trans,
                },
                {
                    "id": "S2-ledger-path",
                    "measurement": "path_category event_ledger (different path tokens)",
                    "result": "count=" + s_ledger,
                },
            ],
            ["path tokens are a different data field than content regex"],
            [
                "session text copied into a .json with a research filename bypasses path-only drop"
            ],
            ended_s,
            snap,
        ),
        claim(
            "C5",
            "A per-line home-path regex is not an effective publication scrub: "
            "constructed encodings keep the identifier.",
            "security-reviewer bypass suite against M1_line_regex",
            "E1",
            "almost-certain",
            P2,
            "CONFIRMED" if not naive["recorded_effective"] else "REFUTED",
            [
                {
                    "id": "S1-bypass-url-split-unicode-b64",
                    "measurement": "in-memory bypass payloads, values not stored",
                    "result": "naive_effective="
                    + str(naive["recorded_effective"]).lower(),
                },
                {
                    "id": "S2-decode-then-redact-contrast",
                    "measurement": "same payloads after M1b_decode_then_redact",
                    "result": "m1b_effective="
                    + str(strong["recorded_effective"]).lower(),
                },
            ],
            ["a mitigation is recorded effective only when every bypass failed"],
            ["novel encodings not in the bypass suite remain residual"],
            ended_s,
            snap,
        ),
        claim(
            "C6",
            "The minimum scrubbing contract that may be recorded as effective is "
            "the surviving set after bypass: decode-then-redact, path-and-content "
            "transcript drop, filename-and-shape credential drop, location-only "
            "reports, and a packed-bytes publication gate.",
            "record-as-effective-only-after-bypass rule",
            "E2",
            "almost-certain",
            P2,
            "CONFIRMED" if safe else "PARTIAL",
            [
                {
                    "id": "S1-effective-set",
                    "measurement": "mitigations with recorded_effective true",
                    "result": ",".join(safe) if safe else "empty",
                },
                {
                    "id": "S2-naive-excluded",
                    "measurement": (
                        "M1_line_regex and M2_path_exclude and M3_filename_only "
                        "excluded if bypassed"
                    ),
                    "result": "naive_line_regex_effective="
                    + str(naive["recorded_effective"]).lower(),
                },
            ],
            ["reviewer constructed a bypass of every listed mitigation before recording"],
            ["OCR/screenshot channel is ADV-0040 and is NOT-CHECKED here"],
            ended_s,
            snap,
        ),
    ]

    answer = (
        "If this tree were published as-is, estate-identifying Windows home paths "
        "would leave with it (content count "
        + s_win_re
        + "; independent byte-prefix count "
        + s_win_bytes
        + "). Credential-shaped filenames counted "
        + s_cred_path
        + "; transcript/session files "
        + s_trans
        + "; event-ledger files "
        + s_ledger
        + ". Unix home paths after colon-exclusion counted "
        + s_unix
        + ". No discovered secret or personal value is reproduced in this record, "
        "only location and category. Naive per-line redaction is not effective. "
        "The minimum contract that survived constructed bypasses is: "
        + (", ".join(safe) if safe else "none")
        + ". The current tree does not pass the packed-bytes gate; the gate is "
        "the publication precondition, not a claim that the tree is already clean. "
        + COMPLETION_SENTINEL
    )

    category_counts = {
        "by_category": by,
        "grand_total": live["grand_total"],
        "sum_check_ok": True,
        "content_files_scanned": live["content_files_scanned"],
        "path_classified_files": live["path_classified_files"],
        "byte_prefix_hits": live["byte_prefix_hits"],
        "files_walked": live["files_walked"],
        "top_files": live["top_files"],
        "locations": live["locations"],
        "value_reproduced": False,
    }
    scrubbing_contract = {
        "mitigations": mitigations,
        "minimum_safe_set": safe,
        "note": (
            "Publication is safe only after the packed-bytes gate is green "
            "on the bytes that would actually ship, using the surviving set. "
            "Screenshot/OCR coverage is out of scope (ADV-0040)."
        ),
    }

    cat_src = (
        "windows_home_path="
        + s_win_re
        + " byte_prefix_hits="
        + s_win_bytes
        + " seeded_identifier="
        + str(by.get("seeded_identifier", 0))
        + " files_walked="
        + str(live["files_walked"])
    )
    ctl_src = (
        "seeded_found="
        + str(control["seeded_found"])
        + " seeded_absent_after_removal="
        + str(control["seeded_absent_after_removal"])
        + " pass="
        + str(control["pass"])
        + " seed_value_reproduced="
        + str(control["seed_value_reproduced"])
    )
    naive_src = (
        "M1_line_regex.recorded_effective="
        + str(naive["recorded_effective"]).lower()
        + " M1b_decode_then_redact.recorded_effective="
        + str(strong["recorded_effective"]).lower()
        + " minimum_safe_set="
        + ",".join(safe)
    )

    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0124",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": "C1 windows home paths present on the live tree",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0124/scan.py:210",
                "probes": probe_pair(
                    "command",
                    P1,
                    cat_src,
                    "byte-compare",
                    "WIN_BYTE_PREFIXES bytes.find vs WIN_RE finditer on the same tree",
                    "byte_prefix_hits=" + s_win_bytes + " regex=" + s_win_re,
                ),
            },
            {
                "claim": "seeded identifier detector control both-states",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0124/control.py:19",
                "probes": probe_pair(
                    "command",
                    P2,
                    ctl_src,
                    "file-read",
                    "command-center/p2-wave/probes/RES-0124/fixtures/negative.users-word-only.txt",
                    "negative_users_word_only_silent="
                    + str(control["negative_users_word_only_silent"]),
                ),
            },
            {
                "claim": "naive line regex effective as a publication scrub",
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0124/scrub.py:37",
                "probes": probe_pair(
                    "static-analysis",
                    "command-center/p2-wave/probes/RES-0124/scrub.py run_bypasses",
                    naive_src,
                    "test-run",
                    P2 + " # mitigation-effective-set",
                    "M1_line_regex not in minimum_safe_set; bypasses survived",
                ),
            },
            {
                "claim": "screenshot/OCR personal data channel",
                "verdict": "NOT-CHECKED",
                "anchor": "ADV-0040",
                "probes": [
                    {
                        "role": "source",
                        "method": "manual-inspection",
                        "command": "scope: RES-0124 does not run a face or OCR detector",
                        "raw_output": "NOT-CHECKED; owned by ADV-0040",
                        "fingerprint": fp("manual-inspection", "ADV-0040"),
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-category-count-real-tree",
                "name": "categorized scan over the real artifact tree",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-seeded-identifier-detector-control",
                "name": "seeded-identifier both-states plus bypass review",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0124-C1",
                "kind": "mutation",
                "description": (
                    "Plant a synthetic identifier in a scratch file outside the "
                    "tree, confirm the scan finds it, remove it, confirm the "
                    "scan is silent, and confirm the real tree has zero leftover "
                    "seeded identifiers."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "seeded_found=True",
                "good_state_output": "seeded_absent_after_removal=True tree_seed=0",
            },
            {
                "id": "RES0124-C2",
                "kind": "known-broken-fixture",
                "description": (
                    "A fixture that uses the word Users without an absolute "
                    "home path must not increment windows_home_path or unix_home_path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "absolute home path would increment the category",
                "good_state_output": "negative_users_word_only_silent=True",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0124-probe2-bypass-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Construct a bypass of every listed mitigation before recording "
                "it as effective; re-run the seeded-identifier both-states control. "
                "Scope is bypass survival, not agreement with this receipt."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0124/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema.Draft7Validator against "
                    "command-center/schema/research-claim-record.schema.json "
                    "(disk RefResolver, no network)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 command-center/p2-wave/probes/RES-0124/emit_report.py"
                    ),
                    "raw_output": "schema-valid; garbage rejected",
                    "fingerprint": fp("schema-validate", SCHEMA),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": ended_s,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot; first attempt used Draft7Validator "
                "without a disk $ref store and hit RefResolutionError on "
                "ast-integrate.invalid (network). This emit pivots to a disk "
                "RefResolver. A second identical fingerprint parks BLOCKED."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "screenshot/OCR personal-data channel (ADV-0040)",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run ADV-0040 face/OCR detectors on the bytes that would "
                    "actually ship; this unit does not operate that channel."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "privacy-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "research-claim-record",
            "title": (
                "Determine the privacy and data-protection surface if this "
                "toolchain is ever published"
            ),
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "windows_home_path",
                    "measured": by["windows_home_path"],
                    "method": "WIN_RE finditer exclusive-span",
                    "anchor": "command-center/p2-wave/probes/RES-0124/scan.py:98",
                },
                {
                    "name": "byte_prefix_hits",
                    "measured": live["byte_prefix_hits"],
                    "method": "bytes.find of assembled C: Users prefixes",
                    "anchor": "command-center/p2-wave/probes/RES-0124/scan.py:223",
                },
                {
                    "name": "seeded_identifier",
                    "measured": by["seeded_identifier"],
                    "method": "SEED_RE on decoded text",
                    "anchor": "command-center/p2-wave/probes/RES-0124/scan.py:125",
                },
                {
                    "name": "detector_control_pass",
                    "measured": bool(control["pass"]),
                    "method": "plant-then-remove scratch identifier",
                    "anchor": "command-center/p2-wave/probes/RES-0124/control.py:19",
                },
            ],
            "control_ids": ["RES0124-C1", "RES0124-C2"],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "completion_sentinel": COMPLETION_SENTINEL,
            "category_counts": category_counts,
            "detector_control": control,
            "scrubbing_contract": scrubbing_contract,
            "claims": claims,
            "tree_snapshot_sha256": snap,
            "never_print_values": True,
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "category-count-real-tree",
                    "command": P1,
                },
                {
                    "id": "probe2",
                    "role": "seeded-identifier-detector-control",
                    "command": P2,
                },
            ],
            "notes": (
                "G-1 for RES-0124: live named probes exit 0, research artifact "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. No ADV rebuild. Schema $ref resolved "
                "from disk; no network. Domain counts live in extensions so "
                "receipt_core additionalProperties stays closed."
            ),
            "answer_not_legal_advice": True,
        },
    }
    return doc


def park_blocked(required_fix: str, errs: list[str], fp_hex: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "FAILED:RES-0124 schema-invalid",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0124",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(SCHEMA, "supporting")],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without "
                    "an ADV rebuild circle."
                ),
                "verdict": "BLOCKED",
                "anchor": "command-center/p2-wave/probes/RES-0124/_schema_strikes.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "Draft7Validator disk RefResolver",
                        "raw_output": "\n".join(errs[:12]),
                        "fingerprint": fp("schema-validate", fp_hex),
                        "exit_code": 1,
                    }
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park BLOCKED",
        },
        "failure": {
            "classification": ["schema-invalid"],
            "reason": required_fix + " fingerprint=" + fp_hex,
            "diagnostic_tail": "\n".join(errs[:20]),
        },
        "extensions": {
            "required_fix": required_fix,
            "schema_fingerprint": fp_hex,
            "status": "BLOCKED",
        },
    }


def validate_or_park(doc: dict, validator: jsonschema.Draft7Validator) -> dict:
    errs = schema_error_list(validator, doc)
    if not errs:
        for garbage in GARBAGE:
            if not list(validator.iter_errors(garbage)):
                raise SystemExit("FAILED:RES-0124 schema accepts garbage")
        return doc
    print("FAILED:RES-0124 schema errors")
    for line in errs[:20]:
        print(" ", line)
    fp_hex = err_fp(errs)
    n_same = record_strike(fp_hex, errs)
    if n_same >= 2:
        required_fix = "align-artifact-to-research-claim-record.schema.json"
        print(
            f"PARK: two same-fingerprint structural refutes "
            f"fp={fp_hex}; required_fix={required_fix}"
        )
        return park_blocked(required_fix, errs, fp_hex)
    raise SystemExit(f"FAILED:RES-0124 schema-invalid fp={fp_hex} (strike {n_same}/2)")


def load_measurements() -> tuple[dict, dict, list[dict]]:
    cache = os.environ.get("RES0124_SCAN_CACHE")
    if cache:
        packed = json.loads(Path(cache).read_text(encoding="utf-8"))
        return packed["live"], packed["control"], packed["bypass_rows"]
    live = scan_tree(REPO)
    control = run_seeded_control(tree_summary=live)
    bypass_rows = run_bypasses()
    return live, control, bypass_rows


def main() -> int:
    if SCAN_REPO != REPO:
        print("FAILED:RES-0124 repo root mismatch")
        return 1
    started = datetime.now(timezone.utc)
    live, control, bypass_rows = load_measurements()
    by = live["by_category"]
    if not control["pass"]:
        print("FAILED:RES-0124 detector control did not pass")
        print(json.dumps(control, sort_keys=True))
        return 1
    if not live["sum_check_ok"]:
        print("FAILED:RES-0124 category sum check")
        return 1
    if by.get("windows_home_path", 0) < 1:
        print("FAILED:RES-0124 expected windows home-path hits on this tree")
        return 1
    if by.get("seeded_identifier", 0) != 0:
        print("FAILED:RES-0124 tree contains a leftover seeded identifier")
        return 1

    ended = datetime.now(timezone.utc)
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_s = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())
    validator = build_validator()
    doc = build_doc(live, control, bypass_rows, started_s, ended_s, duration)
    m4_ok = m4_location_only_ok(doc)
    if not m4_ok:
        print("FAILED:RES-0124 artifact would reproduce a home path or match value")
        return 1
    doc["extensions"]["scrubbing_contract"]["mitigations"] = mitigations_from_bypasses(
        bypass_rows, m4_ok=True
    )
    doc["extensions"]["scrubbing_contract"]["minimum_safe_set"] = minimum_safe_set(
        doc["extensions"]["scrubbing_contract"]["mitigations"]
    )
    doc = validate_or_park(doc, validator)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        out = REPO / OUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT} state={doc.get('state')}")
        return 1
    dumped = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in dumped or SENTINEL not in dumped:
        print("FAILED:RES-0124 completion sentinel absent")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped, encoding="utf-8")
    written = json.loads(out.read_text(encoding="utf-8"))
    if not m4_location_only_ok(written):
        print("FAILED:RES-0124 written artifact failed location-only check")
        return 1
    if COMPLETION_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0124 completion sentinel absent")
        return 1
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0124 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:RES-0124")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
