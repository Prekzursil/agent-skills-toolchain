#!/usr/bin/env python3
"""Adversarial bypass constructor for claimed Sigstore marketplace mitigations.

A mitigation may be recorded as effective only after a bypass attempt.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from tree_digest import digest_of_named, tree_digest
from verify_signature import (
    EXPECTED_IDENTITY,
    EXPECTED_ISSUER,
    naive_accepts,
    pinned_accepts,
    verify_transcript,
)

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "fixtures" / "plugin-clean"
MALICIOUS = HERE / "fixtures" / "plugin-malicious"
SWAP = HERE / "fixtures" / "plugin-swap"

ATTACK_SIGNED_MALWARE = "ATTACK-SIGNED-MALWARE-MARKDOWN"
ATTACK_UNPINNED_IDENTITY = "ATTACK-UNPINNED-IDENTITY"
ATTACK_PARTIAL_TREE = "ATTACK-PARTIAL-TREE-SUBSTITUTION"
ATTACK_OIDC_COMPROMISE = "ATTACK-OIDC-OR-CI-COMPROMISE"
ATTACK_RUNTIME_FETCH = "ATTACK-RUNTIME-UNSIGNED-FETCH"

WRONG_IDENTITY = (
    "https://github.com/evil-org/imposter/.github/workflows/release.yml@refs/heads/main"
)


def construct_bypasses() -> dict:
    transcript = verify_transcript()
    clean = tree_digest(CLEAN)
    malicious = tree_digest(MALICIOUS)
    swapped = tree_digest(SWAP)
    plugin_json_only_clean = digest_of_named(CLEAN, ["plugin.json"])
    plugin_json_only_swap = digest_of_named(SWAP, ["plugin.json"])
    skill_clean = (CLEAN / "skills/skill.demo/SKILL.md").read_text(encoding="utf-8")
    skill_mal = (MALICIOUS / "skills/skill.demo/SKILL.md").read_text(encoding="utf-8")

    naive_on_real = naive_accepts(transcript)
    pinned_on_real = pinned_accepts(transcript, EXPECTED_IDENTITY, EXPECTED_ISSUER)
    pinned_on_wrong = pinned_accepts(transcript, WRONG_IDENTITY, EXPECTED_ISSUER)
    # Same real signature, marketplace expected a different publisher.
    unpinned_bypass = naive_on_real and (not pinned_on_wrong)

    malware_bypass = (
        "exfiltrate" in skill_mal.lower() or "ignore previous" in skill_mal.lower()
    ) and malicious["manifest_sha256"] != clean["manifest_sha256"]
    # Signing pipeline never reads SKILL.md; digest is content-agnostic.
    content_blind = transcript["statement"]["predicate"] is None

    partial_bypass = (
        plugin_json_only_clean == plugin_json_only_swap
        and swapped["manifest_sha256"] != clean["manifest_sha256"]
    )

    mitigations = [
        {
            "id": "MITIGATION-SIGNATURE-EXISTS-ONLY",
            "claim": (
                "Rejecting marketplace packages that lack any valid Sigstore "
                "signature is sufficient."
            ),
            "bypass_attempt": (
                "Feed the real pypa/sampleproject attestation to a marketplace "
                "that expected a different publisher. A signature-exists-only "
                "gate accepts it; an identity-pinned gate rejects it."
            ),
            "bypass_succeeded": unpinned_bypass,
            "effective": False,
            "residual": (
                "Any GitHub Actions identity that can talk to Fulcio produces "
                "an equally valid keyless signature."
            ),
        },
        {
            "id": "MITIGATION-IDENTITY-PINNED-TREE-DIGEST",
            "claim": (
                "cosign verify-blob / DSSE verify of a canonical tree digest "
                "with --certificate-identity and --certificate-oidc-issuer "
                "pinned to the publisher workflow stops third-party substitution "
                "of files after signing."
            ),
            "bypass_attempt": (
                "Swap skills/skill.demo/SKILL.md after the tree digest is taken. "
                "Full-tree digest changes; a pinned verify of the original "
                "digest would fail. Bypass of substitution: failed."
            ),
            "bypass_succeeded": False,
            "effective_against": "third-party post-sign file substitution",
            "effective": True,
            "residual": (
                "Does not stop the pinned identity from signing malware, a "
                "compromised GitHub Actions token, or a signed script that "
                "fetches unsigned bytes at runtime."
            ),
            "evidence": {
                "clean_tree": clean["manifest_sha256"],
                "swapped_tree": swapped["manifest_sha256"],
                "digest_moved": swapped["manifest_sha256"] != clean["manifest_sha256"],
            },
        },
        {
            "id": "MITIGATION-SIGNATURE-AS-MALWARE-SCAN",
            "claim": "A valid keyless signature means the markdown/scripts are safe.",
            "bypass_attempt": (
                "Build a plugin tree whose SKILL.md contains prompt-injection "
                "and an exfiltration instruction. The tree still has a well-formed "
                "digest; the verified PyPI publish attestation has predicate=null "
                "and never inspects file semantics."
            ),
            "bypass_succeeded": malware_bypass and content_blind,
            "effective": False,
            "residual": "Signing attests identity+digest, not harmlessness.",
        },
    ]

    attacks = [
        {
            "id": ATTACK_SIGNED_MALWARE,
            "attack": (
                "Publisher (or anyone who controls the pinned GitHub workflow) "
                "ships a SKILL.md with prompt injection / data-exfil instructions. "
                "Keyless verify succeeds because the digest is honest."
            ),
            "why_signature_does_not_stop_it": (
                "The verified sampleproject statement predicate is JSON null; "
                "the subject is only filename+sha256. Cosign/DSSE never parse "
                "markdown."
            ),
            "demonstrated": malware_bypass and content_blind,
        },
        {
            "id": ATTACK_UNPINNED_IDENTITY,
            "attack": (
                "Marketplace install gate checks only that a Sigstore signature "
                "verifies, not that certificate-identity matches the expected "
                "publisher workflow."
            ),
            "why_signature_does_not_stop_it": (
                "The same real ECDSA-verified attestation is accepted by a naive "
                "policy and rejected when the expected identity is pinned to an "
                "unrelated workflow URI."
            ),
            "demonstrated": unpinned_bypass,
        },
        {
            "id": ATTACK_PARTIAL_TREE,
            "attack": (
                "Sign only plugin.json (or a subset of files). Adversary replaces "
                "SKILL.md / scripts after signing."
            ),
            "why_signature_does_not_stop_it": (
                "plugin.json-only digest is identical for clean vs swapped trees; "
                "the full-tree digest is not."
            ),
            "demonstrated": partial_bypass,
        },
        {
            "id": ATTACK_OIDC_COMPROMISE,
            "attack": (
                "Stolen GitHub Actions OIDC token or compromised workflow YAML "
                "lets an attacker obtain a Fulcio cert for the expected identity."
            ),
            "why_signature_does_not_stop_it": (
                "Sigstore's own security model states that a compromised OIDC "
                "identity can yield unauthorized certificates; detection depends "
                "on log monitoring, not on the signature check itself."
            ),
            "demonstrated": True,
            "demonstration_class": "vendor-documented residual, not a local forge",
        },
        {
            "id": ATTACK_RUNTIME_FETCH,
            "attack": (
                "A signed script downloads and execs unsigned content after "
                "install-time verify has already passed."
            ),
            "why_signature_does_not_stop_it": (
                "sign-blob / DSSE bind bytes that existed at signing time. "
                "Runtime network fetches are outside the digest."
            ),
            "demonstrated": True,
            "demonstration_class": "scope argument from blob-signing semantics",
        },
    ]

    return {
        "transcript_e2e_ok": transcript["e2e_ok"],
        "naive_accepts_real_signature": naive_on_real,
        "pinned_accepts_real_identity": pinned_on_real,
        "pinned_accepts_wrong_identity": pinned_on_wrong,
        "skill_clean_sha256": hashlib.sha256(skill_clean.encode()).hexdigest(),
        "skill_malicious_sha256": hashlib.sha256(skill_mal.encode()).hexdigest(),
        "trees": {
            "clean": clean["manifest_sha256"],
            "malicious": malicious["manifest_sha256"],
            "swapped": swapped["manifest_sha256"],
            "plugin_json_only_clean": plugin_json_only_clean,
            "plugin_json_only_swap": plugin_json_only_swap,
        },
        "mitigations": mitigations,
        "attacks": attacks,
        "effective_mitigations": [
            m["id"] for m in mitigations if m.get("effective")
        ],
        "bypass_of_every_effective_attempted": True,
    }
