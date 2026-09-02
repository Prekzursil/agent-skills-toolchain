"""Shared constants for REL-0012 provenance + consumer verify."""
from __future__ import annotations

UNIT_ID = "REL-0012"
OUTPUT_REL = "command-center/receipts/REL-0012.json"
SCHEMA_REL = "command-center/schema/supply-chain-receipt.schema.json"
SENTINEL = "SUCCESS:REL-0012"
VERIFY_REL = "command-center/p2-wave/probes/REL-0012/verify.py"
NOTES_FIXTURE_REL = (
    "command-center/p2-wave/probes/REL-0012/fixtures/RELEASE-NOTES.md"
)
BUILDER_ID = "https://ast-integrate.local/builders/rel-0012-pr-only-unsigned"
BUILD_TYPE = "https://ast-integrate.local/buildTypes/rel-0012-pr-only/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
QUESTION = (
    "Implementation target: settle how a consumer establishes that this "
    "artifact came from this source. Under PR-ONLY the publication-bound "
    "half is out of scope, so deliver the half that is not: an in-toto or "
    "SLSA-shaped provenance document generated from the real build inputs, "
    "plus a verification command a consumer can actually run. Where signing "
    "needs a key only the owner controls, the release notes must carry an "
    "explicit UNSIGNED declaration rather than staying silent about it. "
    "This unit creates, uses and rotates no key on its own authority."
)
TITLE = (
    "Tamper-evidence: provenance attestation and either a signature or a "
    "declared UNSIGNED gap"
)
