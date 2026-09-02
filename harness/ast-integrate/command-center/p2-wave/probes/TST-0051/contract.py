"""TDD release-policy contract for TST-0051.

Written BEFORE broad implementation of the release tooling (:10822).
Canonical gate ids are the policy-declared set the suite measures against.
Live documents (RELEASE-CHECKLIST.md, ARC-0097) may add ids; they do not
remove these.
"""
from __future__ import annotations

from typing import Any

# Spec / catalog sources for the PR-ONLY release ceremony.
CANONICAL_POLICY_GATES: tuple[dict[str, str], ...] = (
    {
        "id": "pr-only-no-marketplace-publish",
        "source": "OQ-3",
        "evidence_kind": "owner-decision",
        "note": "Release mode is PR-ONLY: no public marketplace publish.",
    },
    {
        "id": "ci-green-pr-head",
        "source": "OQ-9",
        "evidence_kind": "ci-log",
        "note": "Green CI on the PR head stands in for a canary channel.",
    },
    {
        "id": "lifecycle-install-runtime",
        "source": "REL-0004",
        "evidence_kind": "lifecycle-receipt",
        "note": "Throwaway-prefix install; pass is a runtime hook observation.",
    },
    {
        "id": "lifecycle-upgrade",
        "source": "REL-0005",
        "evidence_kind": "lifecycle-receipt",
        "note": "N-1 to N upgrade rehearsal; second run mutates nothing.",
    },
    {
        "id": "lifecycle-rollback",
        "source": "REL-0006",
        "evidence_kind": "lifecycle-receipt",
        "note": "Downgrade drill with behaviour-restored proof.",
    },
    {
        "id": "semver-bump-linter",
        "source": "REL-0001",
        "evidence_kind": "linter-exit",
        "note": "Declared version must be >= diff-derived bump.",
    },
    {
        "id": "rollback-typed-inverses",
        "source": "REL-0002",
        "evidence_kind": "schema-validate",
        "note": "Every mutating install action declares a typed inverse.",
    },
    {
        "id": "sc13-substitute-or-waiver",
        "source": "REL-0003/OQ-9",
        "evidence_kind": "owner-decision",
        "note": "Stop condition 13 has a PR-ONLY substitute or an owner waiver.",
    },
    {
        "id": "uninstall-orphan-sweep",
        "source": "REL-0007",
        "evidence_kind": "release-gate-receipt",
        "note": "Uninstall leaves no dangling registration surfaces.",
    },
    {
        "id": "no-data-loss-oracle",
        "source": "REL-0008",
        "evidence_kind": "lifecycle-receipt",
        "note": "Owner-owned paths hashed before/after lifecycle ops.",
    },
    {
        "id": "package-allowlist-ceiling",
        "source": "REL-0009",
        "evidence_kind": "bundle-scan",
        "note": "Shipped archive evaluated against allowlist and byte/file ceilings.",
    },
    {
        "id": "format-hash-against-blob",
        "source": "RELEASE-CHECKLIST.md / TST-0028",
        "evidence_kind": "blob-digest",
        "note": "Formatting/hash gates read git cat-file -p, never git archive.",
    },
    {
        "id": "secret-scan-bundle",
        "source": "tools/marketplace/secret_gate.py",
        "evidence_kind": "secret-gate",
        "note": "Shipped bundle must not carry private-key PEM markers.",
    },
    {
        "id": "waiver-not-reinterpretation",
        "source": "ARC-0097 tests_required",
        "evidence_kind": "owner-waiver",
        "note": "Unsatisfiable conditions close only by owner-recorded waiver.",
    },
)

CANONICAL_IDS: frozenset[str] = frozenset(g["id"] for g in CANONICAL_POLICY_GATES)

FORBIDDEN_UNDER_PR_ONLY: frozenset[str] = frozenset(
    {
        "marketplace-publish",
        "private-canary-deploy",
        "public-marketplace-release",
        "direct-index-write",
    }
)

# Contract rules. Each has a negative case exercised by suite.mutant_for().
RULES: tuple[dict[str, str], ...] = (
    {
        "id": "R-identity",
        "title": "policy-declared gates equal tooling-enforced gates",
        "negative": "insert a policy gate the tooling set does not contain",
    },
    {
        "id": "R-no-skip",
        "title": "a release must not proceed while a declared gate was never run",
        "negative": "allow_release while a policy gate is absent from ran",
    },
    {
        "id": "R-pr-only",
        "title": "PR-ONLY forbids marketplace-publish / canary-deploy as required gates",
        "negative": "require and mark-run a forbidden publish/canary gate",
    },
    {
        "id": "R-evidence",
        "title": "PASS with no evidence is illegal; missing evidence is NOT-CHECKED",
        "negative": "mark a gate PASS with an empty evidence pointer",
    },
    {
        "id": "R-waiver",
        "title": "unsatisfiable gates close only with an owner-recorded waiver",
        "negative": "close an unsatisfiable gate with no waiver id",
    },
)

RULE_IDS: tuple[str, ...] = tuple(r["id"] for r in RULES)

CATALOG_REL_UNITS: tuple[str, ...] = (
    "REL-0001",
    "REL-0002",
    "REL-0003",
    "REL-0004",
    "REL-0005",
    "REL-0006",
    "REL-0007",
    "REL-0008",
    "REL-0009",
)


def canonical_ids() -> list[str]:
    return [g["id"] for g in CANONICAL_POLICY_GATES]


def empty_record(gid: str) -> dict[str, Any]:
    return {
        "id": gid,
        "status": "NOT-CHECKED",
        "evidence": "",
        "unsatisfiable": False,
        "waiver_id": "",
        "required": True,
    }
