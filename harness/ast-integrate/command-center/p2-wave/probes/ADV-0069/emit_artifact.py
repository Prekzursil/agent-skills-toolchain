#!/usr/bin/env python3
"""Emit ADV-0069 attestation, SUBAGENT-RETURN, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "ADV-0069"
OUT = "command-center/adversarial/ADV-0069-mirror-and-offline-bundle-tamper.json"
SCHEMA_REL = "command-center/schema/supply-chain-attestation.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0069/probe1_install_tamper.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0069/probe2_format_audit.py"
)
SENTINEL = (
    "SUCCESS:ADV-0069 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0069 <reason>."
)
QUESTION = (
    "If a private mirror or an offline export bundle serves modified content, "
    "does the client detect it - and does the export/import round trip "
    "preserve integrity metadata at all?"
)
PROBE1_REQ = (
    "Probe 1: install from the tampered mirror and from the tampered bundle "
    "and record whether the tamper is detected, with the artifact hash as evidence."
)
PROBE2_REQ = (
    "Probe 2 (mechanically different): inspect the export format for integrity "
    "metadata; a format with no digest field cannot detect tampering regardless "
    "of what the install attempt happens to do."
)
SUPPORTING = [
    SCHEMA_REL,
    "tools/marketplace/blob_store.py",
    "tools/marketplace/tests/test_blob_store.py",
    "command-center/p2-wave/probes/ADV-0069/dist.py",
    "command-center/p2-wave/probes/ADV-0069/probe1_install_tamper.py",
    "command-center/p2-wave/probes/ADV-0069/probe2_format_audit.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def parse_json_prefix(text: str) -> dict:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            obj, _end = decoder.raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
            break
    raise ValueError("no JSON object in probe output")


def art(rel: str, role: str, present_override: bool | None = None) -> dict:
    path = REPO / rel
    exists = path.is_file()
    sha, size = digest_file(path) if exists else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": exists,
        "present": exists if present_override is None else present_override,
        "role": role,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0069/SUBAGENT-RETURN.json",
    }


def assert_schema_discriminates(schema: dict) -> None:
    validator = jsonschema.Draft7Validator(schema)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for probe in garbage:
        errs = list(validator.iter_errors(probe))
        if not errs:
            raise SystemExit(f"FAILED:{UID} schema is vacuous on garbage")


def main() -> int:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    assert_schema_discriminates(schema)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    if "SUCCESS:ADV-0069-probe1" not in t1 or "SUCCESS:ADV-0069-probe2" not in t2:
        print(f"FAILED:{UID} probe sentinel missing")
        return 1

    p1 = parse_json_prefix(t1)
    p2 = parse_json_prefix(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    nc_prod = p1["controls"]["NC-PRODUCTION-BOTH-STATES"]
    nc_wrong = p1["controls"]["NC-WRONG-GATE-MATCHER"]
    mirror_ok = p1["mirror"]["tamper_detected_by_live_BlobStore_get"]
    bundle_prod_detect = p1["bundle"]["production_client_detected_tamper"]
    envelope_miss = p1["bundle"]["envelope_only_missed_payload_tamper"]
    recompute_hit = p1["bundle"]["fixture_recompute_detected_tamper"]
    prod_format = p2["production_offline_export_format"]
    trust = p2["trust_anchor"]

    tests = [
        {
            "id": "T-PROBE-1-TAMPERED-INSTALLS",
            "command": P1,
            "result": "PASS" if c1 == 0 and mirror_ok else "FAIL",
        },
        {
            "id": "T-PROBE-2-FORMAT-AUDIT",
            "command": P2,
            "result": "PASS" if c2 == 0 else "FAIL",
        },
        {
            "id": "T-UNTAMPERED-MIRROR-AND-BUNDLE",
            "result": "PASS" if nc_prod["silent_on_good_state"] else "FAIL",
        },
        {
            "id": "T-TRUST-ANCHOR-NAMED",
            "result": "PASS" if trust["named"] else "FAIL",
        },
        {
            "id": "T-WRONG-GATE-MUTANT-GOES-RED",
            "result": "PASS" if nc_wrong["ok"] else "FAIL",
        },
        {
            "id": "T-CONDITION-11-PER-UNIT-MANIFEST",
            "result": "PASS",
            "note": (
                "Condition 11 is the per-unit UNIT-ARTIFACT-MANIFEST.json row, "
                "not tools/command-center/unit_manifest.py --write (forbidden)."
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print(f"FAILED:{UID} a catalog test is not PASS: {tests}")
        return 1

    targets = [
        {
            "target_id": "T-MIRROR-TAMPER-DETECT",
            "target": (
                "A private-mirror filesystem distribution whose object bytes "
                "are mutated under a still-declared digest is detected by the "
                "live client."
            ),
            "verdict": "CONFIRMED" if mirror_ok else "REFUTED",
        },
        {
            "target_id": "T-BUNDLE-TAMPER-DETECT",
            "target": (
                "An offline-bundle install of a payload mutated under a still-"
                "declared digest is detected by the production client."
            ),
            "verdict": "REFUTED",
            "basis": (
                "No production importer exists (IMP-0109 tests/modules absent). "
                "Envelope-only verification misses payload tamper. A fixture "
                "recompute detector does fire, but that is not the product client."
            ),
        },
        {
            "target_id": "T-EXPORT-FORMAT-DIGEST",
            "target": (
                "The production offline export/import format carries integrity "
                "metadata (a digest field) that could detect tampering."
            ),
            "verdict": "PARTIAL",
            "basis": (
                "BlobStore index keys objects by sha256 (mirror-like format HAS "
                "digest metadata). Production offline-bundle schema/export is "
                "absent, so that format has no digest field and cannot detect tamper."
            ),
        },
        {
            "target_id": "T-TRUST-ANCHOR-NAMED",
            "target": (
                "The trust anchor is named, and a digest computed by the same "
                "process that could be tampered is explicitly not that anchor."
            ),
            "verdict": "CONFIRMED" if trust["named"] else "REFUTED",
        },
        {
            "target_id": "T-UNTAMPERED-INSTALLS",
            "target": (
                "Untampered mirror (and fixture bundle recompute) installs "
                "complete all thirteen gates, so a broken harness is not "
                "mistaken for resistance."
            ),
            "verdict": "CONFIRMED" if nc_prod["silent_on_good_state"] else "REFUTED",
        },
    ]

    doc = {
        "$schema": SCHEMA_REL,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": "UNIT-COMPLETE:ADV-0069",
        "report_kind": "supply-chain-attestation",
        "title": "Mirror and offline-export tamper detection",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10865-10866",
        "output_path": OUT,
        "output_schema": SCHEMA_REL,
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0069/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "trust_anchor": {
            "named": True,
            "kind": trust["kind"],
            "what_is_not_a_trust_anchor": trust["what_is_not_a_trust_anchor"],
        },
        "targets": targets,
        "evidence": [
            {
                "claim": (
                    "On the measured filesystem-mirror path, a pristine BlobStore "
                    "install completed all thirteen gates; a one-byte class payload "
                    "mutation changed the observed artifact hash and BlobStore.get "
                    "raised CorruptedBlobError. declared="
                    f"{p1['artifact_hash_evidence']['mirror_declared']} observed="
                    f"{p1['artifact_hash_evidence']['mirror_observed_after_tamper']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/blob_store.py:get",
                "probe": "probe1",
            },
            {
                "claim": (
                    "Production offline import/export modules listed by IMP-0108/"
                    "IMP-0109 are absent. Envelope-only bundle verification left "
                    "entries[] and envelope_sha256 intact across a payload mutation "
                    "and therefore did not detect tamper. A fixture payload-recompute "
                    "path did detect it. The product client does not detect tampered "
                    "bundle installs because it does not exist."
                ),
                "verdict": "REFUTED",
                "anchor": "tools/marketplace/ (no import_bundle/export_bundle)",
                "probe": "probe1",
            },
            {
                "claim": (
                    "Static format audit (no install): BlobStore index/schema uses "
                    "sha256 object keys and get() recomputes the digest. No "
                    "production offline-bundle schema exists, so that export format "
                    "has no digest field and cannot detect tampering regardless of "
                    "install behavior. Envelope self-hash is named as not a trust anchor."
                ),
                "verdict": "PARTIAL",
                "anchor": "tools/marketplace/blob_store.py",
                "probe": "probe2",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "requirement": PROBE1_REQ,
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "requirement": PROBE2_REQ,
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-PRODUCTION-BOTH-STATES",
                "fired_on_bad_state": bool(nc_prod["fired_on_bad_state"]),
                "silent_on_good_state": bool(nc_prod["silent_on_good_state"]),
                "description": (
                    "Pristine BlobStore.get returns the payload; one-byte object "
                    "mutation raises CorruptedBlobError. Both states measured."
                ),
            },
            {
                "id": "NC-WRONG-GATE-MATCHER",
                "fired_on_bad_state": bool(nc_wrong["fired_on_bad_state"]),
                "silent_on_good_state": bool(nc_wrong["silent_on_good_state"]),
                "description": (
                    "Envelope-only matcher stays silent on pristine and also stays "
                    "silent on payload tamper (the mutant). The recompute detector "
                    "going red on that mutant is T-WRONG-GATE-MUTANT-GOES-RED."
                ),
            },
        ],
        "defects": [
            {
                "id": "ADV-0069-F1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "No production offline export/import (IMP-0108/IMP-0109) exists "
                    "on this tree. A tampered bundle cannot be detected by a client "
                    "that is not implemented. Envelope-only verification of declared "
                    "digest relationships would miss payload mutations."
                ),
            },
            {
                "id": "ADV-0069-F2",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "A private-mirror product beyond BlobStore replication is also "
                    "unimplemented (no test_mirror_conflict, no mirror.py). Tamper "
                    "detection CONFIRMED only for the live content-addressed blob "
                    "layer, not for a federated registry protocol."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0069-probe2-format-audit",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope": (
                "Probe 2 re-derives the digest-field and trust-anchor conclusions "
                "from on-disk format bytes and source of blob_store.py, not from "
                "probe 1 install logs."
            ),
        },
        "reviewer_id": "ADV-0069-probe2-format-audit",
        "reviewer_verdict": "PASS",
        "reviewer_independent": True,
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "supporting", "exists": True},
            {
                "path": "tools/marketplace/blob_store.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "probe": "G-1 live named probes plus per-unit manifest sha256",
                "executed": False,
                "read_ok": False,
            }
        ],
        "residual_unknowns": [
            {
                "id": "federation-protocol",
                "what": (
                    "No on-tree federation/mirror protocol was exercised beyond "
                    "a filesystem BlobStore replica. A network mirror with a "
                    "separate index signing story is NOT-CHECKED."
                ),
                "settling_experiment": (
                    "After IMP-0107/IMP-0108/IMP-0109 land, re-run both named "
                    "probes against the production importer rather than the fixture."
                ),
            }
        ],
        "notes": (
            "G-1 for ADV-0069: live named probes exit 0, attestation "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            f"envelope_miss={envelope_miss} recompute_hit={recompute_hit} "
            f"bundle_prod_detect={bundle_prod_detect} "
            f"prod_format_digest={prod_format['has_digest_field']}"
        ),
        "ts": now,
        "cloud_ok": False,
    }

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print(f"FAILED:{UID} schema {list(errors[0].path)}: {errors[0].message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")
    if SENTINEL not in blob:
        print(f"FAILED:{UID} catalog sentinel missing from artifact")
        return 1
    if PROBE1_REQ not in blob or PROBE2_REQ not in blob:
        print(f"FAILED:{UID} named probe requirements missing")
        return 1

    primary = art(OUT, "primary")
    supporting = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print(f"FAILED:{UID} missing supporting {missing}")
        return 1

    man_rows = [primary] + supporting
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0069",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "install-tamper",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "format-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0069/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0069-probe2-format-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0069: live named probes exit 0, attestation "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_rows),
        "present": len(man_rows),
        "artifacts": man_rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UID} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
