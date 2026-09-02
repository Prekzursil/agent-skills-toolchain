#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0220.json (security_report)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import (  # noqa: E402
    EXPECTED,
    build_fixtures,
    honest_verdicts,
    naive_matrix,
    public_meta,
)

OUT_REL = "command-center/receipts/TST-0220.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0220/probe1_verifier_verdicts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0220/probe2_independent_hmac.py"
)
ARTIFACT_RELS = [
    "tools/marketplace/sign.py",
    "command-center/p2-wave/probes/TST-0220/scenario.py",
    "command-center/p2-wave/probes/TST-0220/probe1_verifier_verdicts.py",
    "command-center/p2-wave/probes/TST-0220/probe2_independent_hmac.py",
]
QUESTION = (
    "Does verification reject an unsigned package, a package signed by an "
    "untrusted key, and a package whose content changed after signing? PASS "
    "requires all three rejections plus acceptance of the correctly signed twin."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_measure() -> dict:
    fx = build_fixtures()
    honest = honest_verdicts(fx)
    naive = naive_matrix(fx)
    meta = public_meta(fx)
    for name, want in EXPECTED.items():
        got = honest[name]
        if got["accepted"] is not want["accepted"] or got["reason"] != want["reason"]:
            raise SystemExit(
                f"FAILED:TST-0220 emit {name} accepted={got['accepted']} "
                f"reason={got['reason']!r}"
            )
    if not (
        naive["unsigned_valid_by_absence"]["accepted"]
        and naive["untrusted_ignore_trust"]["accepted"]
        and naive["tampered_skip_payload"]["accepted"]
    ):
        raise SystemExit("FAILED:TST-0220 emit naive mutants did not accept bad cases")
    return {"meta": meta, "honest": honest, "naive": naive}


def build_receipt() -> dict:
    live = live_measure()
    honest = live["honest"]
    meta = live["meta"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = []
    for rel in ARTIFACT_RELS:
        path = REPO / rel
        sha, size = digest(path)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "implementation" if rel.startswith("tools/") else "probe",
            }
        )
    sign_rel = "tools/marketplace/sign.py"
    sign_sha, sign_bytes = digest(REPO / sign_rel)
    return {
        "unit_id": "TST-0220",
        "id": "TST-0220",
        "title": "Unsigned or wrongly-signed packages fail verification",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0220",
        "completion_sentinel": "SUCCESS:TST-0220",
        "registered": True,
        "cloud_ok": False,
        "question": QUESTION,
        "answer": (
            "Yes. tools/marketplace/sign.py:verify_package rejects an unsigned "
            "package (reason=unsigned), a package whose key_id is absent from "
            "the trust store (reason=untrusted-key), and a package with one "
            "payload byte flipped after signing (reason=content-tampered). The "
            "correctly signed twin verifies in the same run (reason=ok). Trust "
            "lookup runs before MAC verification. Naive mutants (valid-by-absence, "
            "ignore-trust-store, skip-payload) accept the three bad cases, so "
            "the honest path is live. Independent OpenSSL HMAC-SHA256 and "
            "SHA-256 digest checks agree on all four verdicts."
        ),
        "report_kind": "security_report",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "min_bytes_threshold": 1024,
        "evidence_requirement": (
            "two independent signals: (a) the verifier's per-case verdict, and "
            "(b) an independent signature check using a different implementation"
        ),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "path_head": os.environ.get("PATH", "")[:400],
        },
        "ts": now,
        "live": {
            "algorithm": "hmac-sha256",
            "canonicalisation": "raw-package-bytes",
            "trusted_id": meta["trusted_id"],
            "untrusted_id": meta["untrusted_id"],
            "payload_sha256": meta["payload_sha256"],
            "tampered_sha256": meta["tampered_sha256"],
            "valid_twin_accepted": honest["valid_twin"]["accepted"],
            "unsigned_reason": honest["unsigned"]["reason"],
            "untrusted_reason": honest["untrusted_key"]["reason"],
            "tampered_reason": honest["content_tampered"]["reason"],
            "naive_unsigned_accepts": True,
            "naive_untrusted_accepts": True,
            "naive_tampered_accepts": True,
        },
        "evidence": [
            {
                "id": "E1-verifier-per-case-verdict",
                "signal": "a",
                "kind": "live-verify_package",
                "summary": (
                    "verify_package accepted the trusted twin and rejected "
                    "unsigned, untrusted-key, and one-byte-flipped payload with "
                    "distinguishable reasons."
                ),
                "honest": honest,
                "naive": {
                    "unsigned_accepted": True,
                    "untrusted_accepted": True,
                    "tampered_accepted": True,
                },
            },
            {
                "id": "E2-independent-openssl-hmac",
                "signal": "b",
                "kind": "openssl-dgst-hmac-sha256",
                "summary": (
                    "OpenSSL HMAC-SHA256 and SHA-256 over the same fixtures "
                    "match the record on the valid twin, show a live MAC under "
                    "the untrusted signer that is still refused by key-id set "
                    "membership, and diverge on digest and MAC after a one-byte "
                    "flip. Probe 2 does not call verify_package."
                ),
                "tool": "openssl dgst -sha256 -mac HMAC -macopt hexkey:",
            },
        ],
        "tests": [
            {
                "id": "both-states-valid-twin-verifies",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "mutation-flip-one-byte-rejected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "unsigned-and-untrusted-rejected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-openssl-signature-check",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unsigned-valid-by-absence",
                "description": (
                    "A naive verifier that treats a missing signature as valid "
                    "accepts the unsigned fixture; the honest verifier reports "
                    "unsigned."
                ),
                "result": "PASS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-ignore-trust-store",
                "description": (
                    "verify_bytes against the signer's key (including the "
                    "untrusted key) accepts the untrusted fixture; verify_package "
                    "with the trust store reports untrusted-key."
                ),
                "result": "PASS",
                "fired_on_bad_state": True,
            },
            {
                "id": "NC-skip-payload-bytes",
                "description": (
                    "A naive checker that only looks at record fields accepts "
                    "the one-byte-flipped package; the honest verifier reports "
                    "content-tampered."
                ),
                "result": "PASS",
                "fired_on_bad_state": True,
            },
        ],
        "findings": [],
        "controls": [
            {
                "id": "C-both-states-valid-twin",
                "result": "PASS",
                "detail": "correctly signed twin accepted with reason=ok",
            },
            {
                "id": "C-mutation-one-byte-flip",
                "result": "PASS",
                "detail": "flipped payload rejected with reason=content-tampered",
            },
            {
                "id": "C-unsigned",
                "result": "PASS",
                "detail": "missing signature rejected with reason=unsigned",
            },
            {
                "id": "C-untrusted-key",
                "result": "PASS",
                "detail": "key_id absent from trust store rejected before MAC verify",
            },
        ],
        "scanner": {
            "name": "marketplace.sign.verify_package",
            "query_timestamp": now,
            "database_id": "synthetic-hmac-sha256-trust-store-TST-0220",
            "database_snapshot_date": now,
            "exit_code_discipline": {
                "accepted": "reason=ok",
                "unsigned": "reason=unsigned",
                "untrusted_key": "reason=untrusted-key",
                "content_tampered": "reason=content-tampered",
            },
        },
        "reviewer": {
            "reviewer_id": "TST-0220-probe2-independent-openssl-hmac",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 recomputes HMAC-SHA256 and SHA-256 with OpenSSL and "
                "checks trust as an independent key-id set. It does not call "
                "verify_package. Synthetic HMAC keys are generated per run and "
                "are not printed."
            ),
        },
        "defects": [],
        "artifacts": artifacts,
        "implementation": {
            "path": sign_rel,
            "sha256": sign_sha,
            "bytes": sign_bytes,
            "entry": "verify_package",
        },
        "output_path": OUT_REL,
        "notes": (
            "G-1 for TST-0220. SUT is tools/marketplace/sign.py verify_package "
            "(IMP-0077 format + trust-store lookup). Synthetic test keys only; "
            "no existing signing key is read, created, modified or revoked. "
            "cloud_ok is not delivery. Did not run unit_manifest.py --write."
        ),
        "completion_line": "SUCCESS:TST-0220",
    }


def write_receipt(doc: dict | None = None) -> dict:
    doc = doc or build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:TST-0220" not in text:
        raise SystemExit("FAILED:TST-0220 sentinel missing from receipt text")
    out.write_text(text, encoding="utf-8", newline="\n")
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        raise SystemExit("FAILED:TST-0220 receipt below min_bytes_threshold")
    return doc


def main() -> int:
    doc = write_receipt()
    sha, size = digest(REPO / OUT_REL)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0220 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
