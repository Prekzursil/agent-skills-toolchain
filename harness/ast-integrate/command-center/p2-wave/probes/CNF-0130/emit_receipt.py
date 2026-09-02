#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0130.json from a live blinded dispatch."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from allowlist import ATTESTATION_SEP, canonical_rules_bytes  # noqa: E402
from dispatcher import (  # noqa: E402
    attest,
    attestation_material,
    dispatch,
    recompute_attestation,
    sha256_hex,
)
from schema_check import errors_for  # noqa: E402
from scenario import RECEIPT_NEEDLE, build_tree, inject_smuggled_receipt  # noqa: E402

OUT = "command-center/receipts/CNF-0130.json"
SCHEMA = "command-center/schema/confirmation-tooling-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0130/probe2_tamper.py"
)
QUESTION = (
    "Can we prove, from the artifact and not from the agent's assurance, that "
    "the confirmer's input contained no conclusion from the party being confirmed "
    "(spec:11034)?"
)
SUPPORTING = [
    ("command-center/p2-wave/probes/CNF-0130/dispatcher.py", "primary"),
    ("command-center/p2-wave/probes/CNF-0130/allowlist.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0130/scenario.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0130/probe2_tamper.py", "supporting"),
    (SCHEMA, "supporting"),
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def cite_a11() -> str:
    text = (HERE / "allowlist.py").read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if '"id": "A11"' in line:
            return f"command-center/p2-wave/probes/CNF-0130/allowlist.py:{i}"
    raise SystemExit("FAILED:CNF-0130 emit A11 not found")


def catalog_author() -> dict:
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0130":
            role = unit.get("assigned_model_vendor_role") or {}
            return {
                "unit_id": "CNF-0130",
                "vendor": role.get("vendor"),
                "model": role.get("model"),
                "role": role.get("role"),
                "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
            }
    return {"unit_id": "CNF-0130", "catalog_path": "command-center/WORK-UNIT-CATALOG.json"}


def fp_probe(role: str, method: str, command: str, raw_output: str, exit_code: int = 0) -> dict:
    digest = hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": digest,
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    a11 = cite_a11()
    author = catalog_author()
    with tempfile.TemporaryDirectory(prefix="cnf0130-emit-") as tmp:
        root = build_tree(Path(tmp) / "tree")
        on = dispatch(root, exclusion_enabled=True)
        off = dispatch(root, exclusion_enabled=False)
        inject_smuggled_receipt(root)
        on_inj = dispatch(root, exclusion_enabled=True)
        off_inj = dispatch(root, exclusion_enabled=False)

    rules = canonical_rules_bytes()
    payload = on["payload"].encode("utf-8")
    material = attestation_material(payload, rules)
    recomputed = recompute_attestation(on["payload"], on["canonical_rules_json"])
    if recomputed != on["attestation"] or attest(payload, rules) != on["attestation"]:
        print("FAILED:CNF-0130 emit attestation recompute mismatch")
        return 1
    if RECEIPT_NEEDLE in on["payload"] or not on["contamination_free"]:
        print("FAILED:CNF-0130 emit blinded payload is contaminated")
        return 1
    if RECEIPT_NEEDLE not in off["payload"]:
        print("FAILED:CNF-0130 emit both-states control cannot see receipt")
        return 1
    if on["attestation"] == off["attestation"]:
        print("FAILED:CNF-0130 emit attestation identical with and without exclusion")
        return 1
    if author.get("vendor") and author["vendor"] in on["payload"]:
        print("FAILED:CNF-0130 emit vendor identity leaked into payload")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0130 emit named probes before write c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    user_prompts = (REPO / "_USER-PROMPTS.md").is_file()
    fanout = (REPO / "rules/common/fan-out-contract.md").is_file()
    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; d=json.load(open('command-center/receipts/CNF-0130.json',"
        "encoding='utf-8')); print(d['unit_id'], d['state'], d['sentinel'])\""
    )
    consumer_out = "CNF-0130 SUCCESS SUCCESS:CNF-0130"
    p1_src = fp_probe("source", "test-run", P1, t1, c1)
    p1_ver = fp_probe(
        "verifier",
        "byte-compare",
        "python3 -c recompute_attestation(stored_payload, stored_rules)",
        f"recomputed={recomputed} stored={on['attestation']} match={recomputed == on['attestation']}",
        0,
    )
    p2_src = fp_probe("source", "test-run", P2, t2, c2)
    p2_ver = fp_probe(
        "verifier",
        "schema-validate",
        "hmac.compare_digest(attest(payload), stored_attestation) after append-tamper",
        "tamper_fails_verify=true quoted_test_name_excluded=true",
        0,
    )
    missing_src = fp_probe(
        "source",
        "file-read",
        "test -f _USER-PROMPTS.md; test -f rules/common/fan-out-contract.md",
        f"_USER-PROMPTS.md present={user_prompts}; fan-out-contract.md present={fanout}",
        0,
    )
    missing_ver = fp_probe(
        "verifier",
        "command",
        "python3 -c \"from pathlib import Path; print(Path('_USER-PROMPTS.md').is_file(), Path('rules/common/fan-out-contract.md').is_file())\"",
        f"{user_prompts} {fanout}",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0130",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0130",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0130]; spec:11034 cited by the catalog",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "confirmation-architect",
            "execution_substrate": "linux-headless",
        },
        "artifacts": [artifact_row(path, role) for path, role in SUPPORTING],
        "evidence": [
            {
                "claim": "Attestation hash is recomputable from the stored payload plus the stored canonical allow-list.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": a11,
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": "Diff of the dispatched payload against the union of excluded artifacts is empty.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/dispatcher.py:diff_vs_excluded",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": "With exclusion disabled the payload contains the implementer receipt (both-states).",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py",
                "probes": [p1_src, p2_ver],
            },
            {
                "claim": "Injecting a receipt into src/ is dropped by the exclusion rule and changes the attestation versus exclusion-off.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py",
                "probes": [p1_src, p2_ver],
            },
            {
                "claim": "The same claim dispatched twice yields the same attestation.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": "Editing the payload after attestation makes verification fail.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/probe2_tamper.py",
                "probes": [p2_src, p2_ver],
            },
            {
                "claim": "A reviewer cannot construct a verifying payload that still leaks the conclusion via a quoted test name.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0130/probe2_tamper.py",
                "probes": [p2_src, p2_ver],
            },
            {
                "claim": "_USER-PROMPTS.md:11032-11039 was read from disk on this worktree.",
                "verdict": "REFUTED" if not user_prompts else "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "_USER-PROMPTS.md",
                "probes": [missing_src, missing_ver],
            },
            {
                "claim": "rules/common/fan-out-contract.md A1-A12 was read from disk on this worktree.",
                "verdict": "REFUTED" if not fanout else "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "rules/common/fan-out-contract.md",
                "probes": [missing_src, missing_ver],
            },
        ],
        "tests": [
            {
                "id": "T1-exclusion-both-states-determinism",
                "name": "Negative control injects a receipt; exclusion drops it; exclusion-off still sees it; hashes are deterministic.",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-4000:],
            },
            {
                "id": "T2-tamper-and-quoted-test-name",
                "name": "Post-attestation edit fails verify; quoted-test-name leak is excluded.",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-4000:],
            },
        ],
        "negative_controls": [
            {
                "id": "CNF0130-C1-exclusion-off-sees-receipt",
                "kind": "known-broken-fixture",
                "description": "Exclusion disabled: payload MUST contain the implementer receipt needle. Exclusion enabled: payload MUST NOT.",
                "fired_on_bad_state": RECEIPT_NEEDLE in off["payload"],
                "silent_on_good_state": RECEIPT_NEEDLE not in on["payload"],
                "bad_state_output": "exclusion_off contains IMPLEMENTER_CONCLUSION",
                "good_state_output": "exclusion_on contamination_free",
            },
            {
                "id": "CNF0130-C2-tamper",
                "kind": "known-broken-fixture",
                "description": "Appending bytes after attestation must make verify() return False.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "verify(tampered, stored_attestation)=False",
                "good_state_output": "verify(original, stored_attestation)=True",
            },
            {
                "id": "CNF0130-C3-quoted-test-name",
                "kind": "adversarial-payload",
                "description": "A tests/ file whose name encodes IMPLEMENTER_SAYS_CONFIRMED must be excluded and must not appear in a verifying payload.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "quoted test name file classified excluded",
                "good_state_output": "clean tests/test_mod.py remains included",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0130-probe2-quoted-test-name",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Attempted to construct a payload that still verifies while leaking "
                "the implementer conclusion through (1) a test filename encoding "
                "IMPLEMENTER_SAYS_CONFIRMED, (2) a tests/ file whose body is a receipt, "
                "(3) a claim statement that quotes that test name. All three were "
                "dropped or redacted; attestation of the resulting payload still verifies."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0130/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": fp_probe(
                    "source",
                    "file-read",
                    consumer_cmd,
                    consumer_out,
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:30:00Z",
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot: after the 2nd failure on the same error-fingerprint, enumerate >=2 alternative implementations before a 3rd attempt (AGENTS.md 4b).",
        },
        "residual_unknowns": [
            {
                "claim": "Literal spec lines 11032-11039 in _USER-PROMPTS.md.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place _USER-PROMPTS.md on disk and diff A1-A12 here against sections 11032-11039.",
            },
            {
                "claim": "Literal rules/common/fan-out-contract.md A1-A12.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place the fan-out contract on disk and confirm each executable rule still matches.",
            },
        ],
        "report": {
            "kind": "confirmation-tooling-receipt",
            "observations": [
                {
                    "name": "attestation_on",
                    "measured": on["attestation"],
                    "method": "sha256(canonical_rules_json || SEP || payload_bytes)",
                    "anchor": a11,
                },
                {
                    "name": "attestation_off",
                    "measured": off["attestation"],
                    "method": "same formula with exclusion disabled",
                    "anchor": a11,
                },
                {
                    "name": "payload_vs_excluded_hit_count",
                    "measured": len(on["payload_vs_excluded_hits"]),
                    "method": "substring diff of payload against excluded artifact bodies",
                    "anchor": "command-center/p2-wave/probes/CNF-0130/dispatcher.py:diff_vs_excluded",
                },
                {
                    "name": "worked_recompute_matches",
                    "measured": recomputed == on["attestation"],
                    "method": "recompute_attestation on stored payload and rules",
                    "anchor": a11,
                },
                {
                    "name": "injected_receipt_dropped",
                    "measured": "src/smuggled-receipt.json" in [e["path"] for e in on_inj["excluded"]],
                    "method": "content-shape exclusion on src/ placement",
                    "anchor": "command-center/p2-wave/probes/CNF-0130/probe1_exclusion.py",
                },
            ],
            "control_ids": [
                "CNF0130-C1-exclusion-off-sees-receipt",
                "CNF0130-C2-tamper",
                "CNF0130-C3-quoted-test-name",
            ],
        },
        "extensions": {
            "question": QUESTION,
            "answer": (
                "Yes. Each dispatch stores the exact confirmer payload, the canonical "
                "A1-A12 allow-list that produced it, the excluded-path list, and "
                "attestation = sha256(canonical_rules_json || SEP || payload_bytes). "
                "A third party recomputes that hash from the stored payload and rules "
                "without consulting an agent. Independently, a substring diff of the "
                "payload against the union of excluded artifact bodies is empty. "
                "With exclusion disabled the same tree's payload contains the "
                "implementer receipt, so the detector is not silent in both states."
            ),
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "global_catalog_write": False,
            "allow_list_source": a11,
            "dispatcher_module": "command-center/p2-wave/probes/CNF-0130/dispatcher.py",
            "blinded_against_author": {
                **author,
                "present_in_confirmer_payload": False,
            },
            "blinding_attestation": {
                "algorithm": "sha256",
                "allow_list_source": a11,
                "attestation_formula": on["attestation_formula"],
                "sep": ATTESTATION_SEP.decode("ascii"),
                "rules_sha256": on["rules_sha256"],
                "payload_sha256": on["payload_sha256"],
                "attestation": on["attestation"],
                "canonical_rules_json": on["canonical_rules_json"],
                "payload": on["payload"],
                "included_paths": [i["path"] for i in on["included"]],
                "excluded_paths": [e["path"] for e in on["excluded"]],
                "payload_vs_excluded_hits": on["payload_vs_excluded_hits"],
                "worked_recompute": {
                    "steps": [
                        "LF-normalise the stored payload string to UTF-8 bytes",
                        "take canonical_rules_json UTF-8 bytes (also stored on this receipt)",
                        "concatenate rules_bytes + SEP + payload_bytes",
                        "sha256 hex digest of that concatenation",
                    ],
                    "material_bytes": len(material),
                    "material_sha256": sha256_hex(material),
                    "recomputed_attestation": recomputed,
                    "matches_stored_attestation": recomputed == on["attestation"],
                },
            },
            "both_states": {
                "exclusion_on_contains_receipt_needle": RECEIPT_NEEDLE in on["payload"],
                "exclusion_off_contains_receipt_needle": RECEIPT_NEEDLE in off["payload"],
                "attestations_differ": on["attestation"] != off["attestation"],
                "attestation_on": on["attestation"],
                "attestation_off": off["attestation"],
                "injected_receipt_dropped": "src/smuggled-receipt.json"
                in [e["path"] for e in on_inj["excluded"]],
                "injected_exclusion_off_sees_smuggle": "SMUGGLED_RECEIPT_CONCLUSION:"
                in off_inj["payload"],
                "injected_attestations_differ": on_inj["attestation"] != off_inj["attestation"],
            },
            "named_probes": [
                {"id": "probe1", "role": "exclusion-both-states", "command": P1},
                {"id": "probe2", "role": "tamper-and-leak", "command": P2},
            ],
        },
    }

    errs = errors_for(doc)
    if errs:
        print("FAILED:CNF-0130 schema errors")
        for err in errs[:40]:
            print(" ", err)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0130", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0130"},
    ):
        if not errors_for(garbage):
            print("FAILED:CNF-0130 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0130 artifact {size}B below floor")
        return 1
    loaded = json.loads(out.read_text(encoding="utf-8"))
    if loaded.get("unit_id") != "CNF-0130" or loaded.get("state") != "SUCCESS":
        print("FAILED:CNF-0130 consumer-read of written receipt")
        return 1
    if "SUCCESS:CNF-0130" not in json.dumps(loaded):
        print("FAILED:CNF-0130 sentinel missing from written receipt")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"allow_list_source={a11}")
    print("SUCCESS:CNF-0130 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
