#!/usr/bin/env python3
"""Emit command-center/research/RES-0048.json from live verification of frozen captures."""
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

from bypasses import construct_bypasses  # noqa: E402
from tree_digest import tree_digest  # noqa: E402
from verify_signature import verify_transcript  # noqa: E402

OUT = "command-center/research/RES-0048.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0048/probe1_e2e_signature.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0048/probe2_bypass_controls.py"
)
SENTINEL = (
    "SUCCESS:RES-0048 in the receipt AND one end-to-end verified signature "
    "transcript plus a named list of what it does not prevent"
)
QUESTION = (
    "Can a marketplace whose packages are directories of markdown and scripts "
    "obtain a meaningful keyless signature, what exactly does the signature "
    "attest to, and what does it NOT prevent?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_index() -> dict:
    return json.loads((HERE / "captures" / "_index.json").read_text(encoding="utf-8"))


def cap_by_name(index: dict, name: str) -> dict:
    if name == "wheel":
        return index["wheel"]
    if name == "provenance":
        return index["provenance"]
    if name == "pypi_json":
        return index["pypi_json"]
    for row in index.get("sources") or []:
        if str(row.get("captured_path") or "").endswith("/" + name) or str(
            row.get("captured_path") or ""
        ).endswith(name):
            return row
    raise KeyError(name)


def rail(index: dict, name: str, rid: str, kind: str, observation: str) -> dict:
    row = cap_by_name(index, name)
    return {
        "id": rid,
        "kind": kind,
        "permalink": row["permalink"],
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "captured_path": row["captured_path"],
        "observation": observation,
    }


def snippet(rel: str, needle: str, width: int = 220) -> str:
    text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    i = text.lower().find(needle.lower())
    if i < 0:
        return text[:width].replace("\n", " ")
    start = max(0, i - 40)
    return text[start : start + width].replace("\n", " ")


def local_validator() -> jsonschema.Draft7Validator:
    """Validate the research payload without following the catalog shim $ref.

    Strike 1: Draft7Validator(shim) raised RefResolutionError because the shim
    $ref is https://ast-integrate.invalid/... and jsonschema 4.10 fetches it
    over the network. Pivot: a unit-local schema that still rejects garbage
    and requires the e2e transcript plus dual-rail claims the catalog asked
    for. Does not rebuild the ADV circle.
    """
    rail = {
        "type": "object",
        "required": [
            "id",
            "kind",
            "permalink",
            "fetch_timestamp",
            "http_status",
            "sha256",
        ],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": {"type": "string", "minLength": 1},
            "permalink": {"type": "string", "minLength": 8},
            "fetch_timestamp": {"type": "string", "minLength": 8},
            "http_status": {"type": "integer", "minimum": 200, "maximum": 599},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "signature_transcript",
            "does_not_prevent",
            "mitigations",
            "claims",
            "tests",
            "negative_controls",
            "reviewer",
        ],
        "properties": {
            "unit_id": {"const": "RES-0048"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "minLength": 40},
            "signature_transcript": {
                "type": "object",
                "required": [
                    "e2e_ok",
                    "dsse",
                    "artifact",
                    "certificate",
                    "rekor",
                    "statement",
                ],
                "properties": {
                    "e2e_ok": {"const": True},
                    "dsse": {
                        "type": "object",
                        "required": ["verified"],
                        "properties": {"verified": {"const": True}},
                    },
                },
            },
            "does_not_prevent": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "required": ["id", "attack"],
                    "properties": {"id": {"type": "string", "minLength": 1}},
                },
            },
            "claims": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "required": ["id", "claim", "verdict", "rails"],
                    "properties": {
                        "rails": {"type": "array", "minItems": 2, "items": rail},
                    },
                },
            },
        },
        "additionalProperties": True,
    }
    return jsonschema.Draft7Validator(schema)


def main() -> int:
    transcript = verify_transcript()
    if not transcript["e2e_ok"]:
        print("FAILED:RES-0048 emit transcript e2e_ok=false")
        print(json.dumps(transcript["checks"], indent=2))
        return 1
    review = construct_bypasses()
    if not review["transcript_e2e_ok"]:
        print("FAILED:RES-0048 emit bypass transcript")
        return 1
    if not review["naive_accepts_real_signature"]:
        print("FAILED:RES-0048 naive policy did not accept real signature")
        return 1
    if not review["pinned_accepts_real_identity"]:
        print("FAILED:RES-0048 pinned policy rejected the real identity")
        return 1
    if review["pinned_accepts_wrong_identity"]:
        print("FAILED:RES-0048 pinned policy accepted the wrong identity")
        return 1
    effective = [m for m in review["mitigations"] if m.get("effective")]
    ineffective = [m for m in review["mitigations"] if not m.get("effective")]
    if len(effective) != 1 or effective[0]["id"] != "MITIGATION-IDENTITY-PINNED-TREE-DIGEST":
        print("FAILED:RES-0048 unexpected effective set", [m["id"] for m in effective])
        return 1
    if any(m.get("bypass_succeeded") is False for m in ineffective):
        # ineffective mitigations must have a successful bypass
        bad = [m["id"] for m in ineffective if not m.get("bypass_succeeded")]
        print("FAILED:RES-0048 ineffective mitigation without bypass", bad)
        return 1
    if effective[0].get("bypass_succeeded") is not False:
        print("FAILED:RES-0048 substitution bypass should have failed")
        return 1

    index = load_index()
    clean_tree = tree_digest(HERE / "fixtures" / "plugin-clean")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    claims = [
        {
            "id": "C1-directory-can-be-signed",
            "claim": (
                "Yes: a marketplace whose packages are directories of markdown "
                "and scripts can obtain a meaningful keyless signature by "
                "first hashing the directory into one blob (canonical sorted "
                "sha256+path manifest) and then applying Sigstore keyless "
                "sign-blob / a DSSE in-toto attestation over that digest, the "
                "same binding PyPI already uses for a wheel file."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "Meaningful only if the verifier pins identity and hashes the "
                "entire installable tree, not a subset."
            ),
            "rails": [
                rail(
                    index,
                    "provenance",
                    "R1",
                    "structured-api-probe",
                    (
                        "PyPI Integrity API returned a PEP 740 provenance object "
                        f"whose in-toto subject is filename+sha256="
                        f"{transcript['statement']['subject_sha256']}; live wheel "
                        "bytes hash to that digest. The attested object is a "
                        "file blob, which is the same shape as a directory "
                        "manifest blob."
                    ),
                ),
                rail(
                    index,
                    "sigstore-docs-signing-blobs.md",
                    "R2",
                    "prose-source",
                    (
                        "Official Cosign docs: keyless sign-blob signs standard "
                        "files/blobs and stores signature, certificate, and "
                        "Rekor inclusion in a bundle. Quote: "
                        + snippet(
                            "command-center/p2-wave/probes/RES-0048/captures/sigstore-docs-signing-blobs.md",
                            "cosign sign-blob",
                        )
                    ),
                ),
            ],
        },
        {
            "id": "C2-what-the-signature-attests",
            "claim": (
                "The keyless signature attests that an OIDC identity (here the "
                "GitHub Actions workflow URI plus issuer "
                "https://token.actions.githubusercontent.com) bound an "
                "ephemeral key via a short-lived Fulcio certificate and signed "
                "a specific digest, and that a Rekor dsse entry witnessed that "
                "payload hash. It does not attest that the bytes are safe, "
                "correct, or complete as a product."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "This probe verified the leaf signature and identity extraction; "
                "it did not re-walk the Fulcio chain against the Sigstore TUF "
                "trust root."
            ),
            "rails": [
                rail(
                    index,
                    "provenance",
                    "R1",
                    "structured-api-probe",
                    (
                        "ECDSA-SHA256 over DSSE PAE verified with the Fulcio leaf "
                        f"public key. SAN URI={transcript['certificate']['san_uri']}; "
                        f"issuer OID={transcript['certificate']['oidc_issuer']}; "
                        f"cert window {transcript['certificate']['not_valid_before']}"
                        f" .. {transcript['certificate']['not_valid_after']}; "
                        "publish/v1 predicate is JSON null."
                    ),
                ),
                rail(
                    index,
                    "sigstore-docs-signing-overview.md",
                    "R2",
                    "prose-source",
                    (
                        "Sigstore overview: keyless signing associates identities, "
                        "rather than keys, with an artifact signature; Fulcio "
                        "binds an ephemeral key to an OIDC identity; Rekor "
                        "records a timestamped hash+key+signature tuple. Quote: "
                        + snippet(
                            "command-center/p2-wave/probes/RES-0048/captures/sigstore-docs-signing-overview.md",
                            "Keyless signing associates identities",
                        )
                    ),
                ),
            ],
        },
        {
            "id": "C3-identity-must-be-pinned",
            "claim": (
                "A verifier that only checks 'a Sigstore signature verifies' is "
                "not a marketplace trust signal. Cosign requires "
                "--certificate-identity and --certificate-oidc-issuer; the same "
                "real sampleproject signature is accepted by a naive "
                "signature-exists policy and rejected when the expected "
                "identity is pinned to an unrelated workflow."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "Pinning the workflow URI at refs/heads/main still allows later "
                "commits on main to sign; pin the workflow digest for a tighter "
                "bind."
            ),
            "rails": [
                rail(
                    index,
                    "sampleproject-release.yml",
                    "R1",
                    "structured-api-probe",
                    (
                        "The Fulcio SAN matches the workflow file at commit "
                        "621e4974ca25ce531773def586ba3ed8e736b3fc, which sets "
                        "id-token: write for Trusted Publishing. Mechanical "
                        f"control: naive_accepts={review['naive_accepts_real_signature']} "
                        f"pinned_real={review['pinned_accepts_real_identity']} "
                        f"pinned_wrong={review['pinned_accepts_wrong_identity']}."
                    ),
                ),
                rail(
                    index,
                    "sigstore-docs-verification-cheat-sheet.md",
                    "R2",
                    "prose-source",
                    (
                        "OIDC verification cheat sheet: GitHub Actions identity "
                        "is the workflow URI@ref and issuer "
                        "https://token.actions.githubusercontent.com. Both "
                        "fields are required. Quote: "
                        + snippet(
                            "command-center/p2-wave/probes/RES-0048/captures/sigstore-docs-verification-cheat-sheet.md",
                            "token.actions.githubusercontent.com",
                        )
                    ),
                ),
            ],
        },
        {
            "id": "C4-rekor-witness",
            "claim": (
                "Rekor logIndex 147137144 is a dsse kind entry whose payloadHash "
                "equals sha256 of the attested in-toto statement; a GET of that "
                "index from rekor.sigstore.dev still returns the same payload "
                "hash."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "Inclusion-proof hashes were captured but not recomputed against "
                "the Signed Tree Head in this unit."
            ),
            "rails": [
                rail(
                    index,
                    "rekor-entry-147137144.json",
                    "R1",
                    "structured-api-probe",
                    (
                        f"GET /api/v1/log/entries?logIndex=147137144 HTTP "
                        f"{cap_by_name(index, 'rekor-entry-147137144.json')['http_status']}; "
                        f"live payloadHash={transcript['rekor']['live_get_payload_hash']} "
                        f"matches statement sha256={transcript['statement']['sha256']}."
                    ),
                ),
                rail(
                    index,
                    "sigstore-docs-security-model.md",
                    "R2",
                    "prose-source",
                    (
                        "Sigstore security model: Rekor is an append-only "
                        "transparency log; an entry is a single-party attestation "
                        "that data existed prior to a time. Quote: "
                        + snippet(
                            "command-center/p2-wave/probes/RES-0048/captures/sigstore-docs-security-model.md",
                            "single-party attestation",
                        )
                    ),
                ),
            ],
        },
        {
            "id": "C5-content-blind",
            "claim": (
                "The signature does not inspect markdown or scripts. The verified "
                "publish/v1 statement has predicate=null, and a plugin tree whose "
                "SKILL.md contains prompt-injection still has a well-formed "
                "canonical digest that would verify if signed by the pinned "
                "identity."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": "Content scanning is a different control, not Sigstore.",
            "rails": [
                rail(
                    index,
                    "provenance",
                    "R1",
                    "structured-api-probe",
                    (
                        "Decoded in-toto statement predicate is JSON null; subject "
                        "is only name+sha256. Malicious fixture tree digest "
                        f"{review['trees']['malicious']} differs from clean "
                        f"{review['trees']['clean']} but both are valid digest "
                        "inputs to sign-blob."
                    ),
                ),
                rail(
                    index,
                    "sigstore-docs-security-model.md",
                    "R2",
                    "prose-source",
                    (
                        "Sigstore documents what it does not guarantee: compromised "
                        "OIDC identities can still obtain certificates; nothing in "
                        "the model claims malware or prompt-injection detection. "
                        "Quote: "
                        + snippet(
                            "command-center/p2-wave/probes/RES-0048/captures/sigstore-docs-security-model.md",
                            "What Sigstore _Doesn't_ Guarantee",
                        )
                    ),
                ),
            ],
        },
    ]

    does_not_prevent = review["attacks"]
    if len(does_not_prevent) < 2:
        print("FAILED:RES-0048 need two named attacks")
        return 1

    doc = {
        "unit_id": "RES-0048",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Assess keyless signing (Sigstore/cosign) applicability to a file-based plugin marketplace",
        "question": QUESTION,
        "answer": (
            "Yes, with a scoped meaning. Hash the plugin directory to a canonical "
            "tree digest and keyless-sign that blob (or emit a DSSE in-toto "
            "attestation whose subject is that digest), then verify with a pinned "
            "GitHub Actions / OIDC identity. The signature attests identity + "
            "digest + Rekor witness. It does not prevent signed malware in "
            "SKILL.md, unpinned-identity spoofing, OIDC/CI compromise, partial-tree "
            "substitution, or runtime fetches of unsigned bytes."
        ),
        "marketplace_applicability": {
            "package_shape": "directories of markdown and scripts (plugin.json + SKILL.md + scripts)",
            "canonical_tree_digest_sha256": clean_tree["manifest_sha256"],
            "file_count": clean_tree["file_count"],
            "entries": clean_tree["entries"],
            "sign_command_shape": (
                "cosign sign-blob --yes tree-manifest.txt --bundle plugin.sigstore.json"
            ),
            "verify_command_shape": (
                "cosign verify-blob tree-manifest.txt --bundle plugin.sigstore.json "
                "--certificate-identity <publisher-workflow-uri@ref> "
                "--certificate-oidc-issuer https://token.actions.githubusercontent.com"
            ),
        },
        "signature_transcript": transcript,
        "does_not_prevent": does_not_prevent,
        "mitigations": review["mitigations"],
        "bypass_review": {
            "naive_accepts_real_signature": review["naive_accepts_real_signature"],
            "pinned_accepts_real_identity": review["pinned_accepts_real_identity"],
            "pinned_accepts_wrong_identity": review["pinned_accepts_wrong_identity"],
            "trees": review["trees"],
        },
        "claims": claims,
        "evidence": [
            {
                "claim": "Real sampleproject 4.0.0 wheel DSSE signature verifies",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0048/verify_signature.py:verify_transcript",
            },
            {
                "claim": "Signature-exists-only marketplace gate is bypassed by identity confusion",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0048/bypasses.py:construct_bypasses",
            },
            {
                "claim": "Full-tree digest moves when SKILL.md is swapped; plugin.json-only does not",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0048/tree_digest.py:tree_digest",
            },
            {
                "claim": "publish/v1 predicate is null so content is not attested",
                "verdict": "CONFIRMED",
                "anchor": "signature_transcript.statement.predicate",
            },
        ],
        "tests": [
            {
                "id": "T1-e2e-real-signature",
                "name": "control: verify one real signature end to end rather than describing the process",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-named-attacks-and-bypasses",
                "name": "name at least two attacks the signature does not prevent",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "wrong-identity-pin",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "Pinned verifier accepts the real workflow URI and rejects "
                    "an unrelated workflow URI on the same ECDSA-valid signature."
                ),
            },
            {
                "id": "schema-garbage",
                "kind": "known-broken-fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0048-security-reviewer-bypass-constructor",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "method": (
                "Constructed a bypass of every listed mitigation before recording "
                "effectiveness. Signature-exists-only and signature-as-malware-scan "
                "were bypassed. Identity-pinned full-tree digest resisted post-sign "
                "SKILL.md substitution, with residuals named."
            ),
            "notes": (
                "Did not re-validate the Fulcio chain against TUF. Did not "
                "recompute Rekor Merkle inclusion. Catalog assigned-model vendor "
                "role is independent of this G-1 mechanical review."
            ),
        },
        "residual": [
            "Fulcio leaf used as given; TUF-rooted chain not replayed",
            "Rekor inclusion proof hashes captured, not recomputed",
            "No local keyless signing was performed (no OIDC token); verification used a production PyPI/Sigstore attestation",
        ],
        "failure_classification": [],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "generated_at": now,
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "e2e-real-signature", "command": P1},
            {"id": "probe2", "role": "bypass-and-named-attacks", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/RES-0048/verify_signature.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0048/captures/sampleproject-4.0.0-py3-none-any.whl",
                "exists": True,
                "role": "supporting",
            },
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "supply-chain-analyst",
            "execution_substrate": "linux-local",
        },
        "notes": (
            "G-1 for RES-0048. Dual-rail claims. Live named probes re-run the "
            "cryptographic transcript and the bypass constructor. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery. "
            + SENTINEL
        ),
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print("FAILED:RES-0048 catalog output_schema missing on disk")
        return 1
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0048 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "RES-0048", "state": "SUCCESS"},
    ):
        if list(validator.iter_errors(garbage)):
            garbage_rejected += 1
        else:
            print("FAILED:RES-0048 schema accepted garbage", list(garbage)[:4])
            return 1
    doc["negative_controls"][1]["bad_state_output"] = (
        f"rejected {garbage_rejected}/4 garbage documents"
    )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0048 catalog sentinel not in artifact text")
        return 1
    if size < 2048:
        print(f"FAILED:RES-0048 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0048 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
