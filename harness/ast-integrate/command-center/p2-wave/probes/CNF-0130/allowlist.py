#!/usr/bin/env python3
"""Spawn-prompt allow-list for CNF-0130 (fan-out contract A1-A12).

rules/common/fan-out-contract.md is absent on this worktree. These twelve
rules are the executable stand-in: include claim STATEMENT + raw source +
tests; mechanically drop implementer receipts, review verdicts, prior
confirmations, receipt-shaped content, and conclusion-bearing names.
"""
from __future__ import annotations

import json
from typing import Any

# A11 attestation separator. Exact bytes dispatched are hashed with the
# canonical rule set on either side of this delimiter.
ATTESTATION_SEP = b"\n--CNF-0130-PAYLOAD--\n"

# Distinctive contamination needles used by fixtures and probes. A payload
# that contains any of these has leaked a conclusion.
CONCLUSION_NEEDLES = (
    "IMPLEMENTER_CONCLUSION:",
    "IMPLEMENTER_VERDICT:",
    "IMPLEMENTER_SAYS_CONFIRMED",
    "REVIEW_VERDICT:",
    "PRIOR_CONFIRMATION:",
    "SMUGGLED_RECEIPT_CONCLUSION:",
    "confidence_band",
    "summary_table",
)

CLAIM_KEEP_KEYS = ("claim_id", "id", "statement", "question")
CLAIM_DROP_KEYS = (
    "conclusion",
    "implementer_conclusion",
    "verdict",
    "confidence",
    "confidence_band",
    "summary",
    "summary_table",
    "receipt_prose",
    "author",
    "vendor",
    "assigned_model_vendor_role",
)

RECEIPT_SHAPE_ALL = ("unit_id", "state", "sentinel")
RECEIPT_SHAPE_ANY = CLAIM_DROP_KEYS + ("implementer_notes", "reviewer_verdict")

SOURCE_PREFIXES = ("src/", "lib/", "source/", "pkg/")
TEST_PREFIXES = ("tests/", "test/", "spec/")
TEST_NAME_PREFIXES = ("test_",)
SOURCE_SUFFIXES = (
    ".py",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".rs",
    ".go",
    ".js",
    ".ts",
    ".java",
    ".md",
)

DENY_PATH_PARTS = {
    "A4": ("receipts", "receipt"),
    "A5": ("reviews", "verdicts", "verdict"),
    "A6": ("confirmation", "confirmations"),
}
DENY_NAME_FRAGMENTS = {
    "A4": ("receipt",),
    "A5": ("verdict", "review"),
    "A6": ("confirmation",),
    "A8": (
        "implementer_conclusion",
        "implementer_says",
        "implementer_verdict",
        "quoted_test_leak",
    ),
}

SKIP_DIR_NAMES = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".venv"}

# Canonical rule set hashed into every attestation. Order is part of the
# contract: changing a rule changes the attestation even if payload bytes
# happen to stay the same.
RULES: list[dict[str, Any]] = [
    {
        "id": "A1",
        "kind": "include",
        "axis": "claim_statement",
        "description": "Include the claim STATEMENT as a quoted literal; never conclusion, confidence band, summary table, author identity, or receipt prose.",
    },
    {
        "id": "A2",
        "kind": "include",
        "axis": "raw_source",
        "path_prefixes": list(SOURCE_PREFIXES),
        "suffixes": list(SOURCE_SUFFIXES),
    },
    {
        "id": "A3",
        "kind": "include",
        "axis": "tests",
        "path_prefixes": list(TEST_PREFIXES),
        "name_prefixes": list(TEST_NAME_PREFIXES),
    },
    {
        "id": "A4",
        "kind": "exclude",
        "axis": "implementer_receipt",
        "path_parts": list(DENY_PATH_PARTS["A4"]),
        "name_contains": list(DENY_NAME_FRAGMENTS["A4"]),
    },
    {
        "id": "A5",
        "kind": "exclude",
        "axis": "review_verdict",
        "path_parts": list(DENY_PATH_PARTS["A5"]),
        "name_contains": list(DENY_NAME_FRAGMENTS["A5"]),
    },
    {
        "id": "A6",
        "kind": "exclude",
        "axis": "prior_confirmation",
        "path_parts": list(DENY_PATH_PARTS["A6"]),
        "name_contains": list(DENY_NAME_FRAGMENTS["A6"]),
    },
    {
        "id": "A7",
        "kind": "exclude",
        "axis": "content_receipt_shape",
        "json_keys_all": list(RECEIPT_SHAPE_ALL),
        "json_keys_any": list(RECEIPT_SHAPE_ANY),
        "needles": list(CONCLUSION_NEEDLES),
    },
    {
        "id": "A8",
        "kind": "exclude",
        "axis": "conclusion_filename",
        "name_contains": list(DENY_NAME_FRAGMENTS["A8"]),
        "description": "A quoted test name that encodes the implementer conclusion is not an allowed test.",
    },
    {
        "id": "A9",
        "kind": "canonical",
        "axis": "order",
        "description": "Sort included files by POSIX relative path; no mtime, no inode.",
    },
    {
        "id": "A10",
        "kind": "canonical",
        "axis": "eol",
        "description": "LF-normalise payload bytes before hashing.",
    },
    {
        "id": "A11",
        "kind": "attest",
        "axis": "hash",
        "description": "attestation = sha256(canonical_rules_json || SEP || payload_bytes)",
        "sep": ATTESTATION_SEP.decode("ascii"),
    },
    {
        "id": "A12",
        "kind": "exclude",
        "axis": "agent_prose",
        "description": "Do not append dispatcher commentary, confidence, or a summary table to the payload.",
    },
]


def canonical_rules_bytes() -> bytes:
    """Stable UTF-8 JSON of RULES. This blob is half of every attestation."""
    return json.dumps(RULES, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def attestation_formula() -> str:
    """A11: attestation = sha256(canonical_rules_json || SEP || payload_bytes)."""
    return "sha256(canonical_rules_json || SEP || payload_bytes)"


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def posix_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")
