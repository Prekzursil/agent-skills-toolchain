"""Catalog-reconstructed 05-ECO call-sheet calibration set.

The cited source
C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md
is not on this Linux worktree. Rows are reconstructed from WORK-UNIT-CATALOG.json
citations of that file (lines 74-108 and the named Tier-1 / Tier-3 quotes).
Each row records reconstruction_confidence. Feature cards are filled from the
catalog's own evidence language, not from a desire to match the inherited grade.
"""
from __future__ import annotations

from typing import Any

SOURCE_ABSENT = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
)

TIER1: list[dict[str, Any]] = [
    {
        "id": "T1-01",
        "name": "native-progressive-disclosure-deferred-tool",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "EXPLICIT-ADOPT",
        "catalog_citation": (
            "RES-0100 inputs cite 05-ECOSYSTEM.md:83-84,100 "
            "'adopt native, reject bespoke retriever'"
        ),
        "features": {
            "leverage": 3,
            "integration_cost": 0,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "Native client mechanism already on the bus; catalog contrasts it "
            "with gateway daemons and with a bespoke retriever. Cost is zero "
            "beyond using the existing surface."
        ),
    },
    {
        "id": "T1-02",
        "name": "judge-abstention-as-a-first-class-verdict",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "EXPLICIT-TIER-1",
        "catalog_citation": (
            "RES-0103 inputs cite 05-ECOSYSTEM.md:84-85 "
            "'judge abstention, Tier 1'"
        ),
        "features": {
            "leverage": 3,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "RIDES-BUS+STATE",
        },
        "feature_basis": (
            "Call sheet grades it Tier 1. This estate has no measured "
            "wrong-injection versus missed-injection cost ratio (RES-0103 "
            "exists to obtain one). Headline without baseline is E3."
        ),
    },
    {
        "id": "T1-03",
        "name": "in-toto-shaped-attestation-on-every-agent-artifact",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "EXPLICIT-TIER-1",
        "catalog_citation": (
            "RES-0049 question names 'in-toto-shaped attestation on every "
            "agent artifact (Tier 1 in the call sheet)'; inputs cite "
            "05-ECO-frontier-orchestration.md:81-86"
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 3,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "SECOND RUNTIME",
        },
        "feature_basis": (
            "RES-0049 asks which SLSA level a single-owner PR-only process "
            "can reach without a hosted builder. Hosted-builder attestation "
            "is a second runtime relative to this bus."
        ),
    },
    {
        "id": "T1-04",
        "name": "two-rail-R1-R2-evidence",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "Repeated 05-ECO evidence_requirement: structured API probe AND "
            "prose source; a single rail is E3"
        ),
        "features": {
            "leverage": 3,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E1",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "The R1/R2 pattern is the catalog's load-bearing evidence rule. "
            "Baseline is the single-rail (E3) alternative; effect is "
            "mechanical: one rail cannot be cited as measured fact."
        ),
    },
    {
        "id": "T1-05",
        "name": "embedding-free-symbol-graph-repo-map",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0028 extracts Aider repo-map; RES-0107 asks whether the "
            "05-ECO no-vector-store constraint is satisfiable. The explicit "
            "reject at line 100 is the bespoke *vector* retriever, not repo-map."
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "RES-0028 requires an independent reproduction of the accuracy "
            "gain versus sending more files. Catalog treats a blog number "
            "without baseline as E3 that cannot promote to Tier 1."
        ),
    },
    {
        "id": "T1-06",
        "name": "e1-e4-mechanical-evidence-ledger",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0003 operationalizes the shard E1-E4 ledger cited from "
            "05-ECO-frontier-orchestration.md:11"
        ),
        "features": {
            "leverage": 3,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "Mechanical grader with named adversarial fixtures (hedged E1 "
            "must not drop to E4; confident E4 must still be caught). "
            "Target kappa >= 0.6 is a stated effect against a labelled sample."
        ),
    },
    {
        "id": "T1-07",
        "name": "content-addressed-source-snapshot-and-recheck",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0004; 05-ECOSYSTEM.md:146 observed HTTP 301 "
            "docs.claude.com -> code.claude.com"
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "Snapshot tuple (URL, final URL, status, timestamp, sha256) is "
            "the second rail for every later claim. Mutated-byte CHANGED "
            "versus unchanged UNCHANGED is a both-states control."
        ),
    },
    {
        "id": "T1-08",
        "name": "goose-lead-worker-failure-threshold-escalation",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0029 title: Extract Goose recipes and its lead/worker "
            "failure-threshold escalation mechanism"
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 2,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "RIDES-BUS+STATE",
        },
        "feature_basis": (
            "Escalation-on-failure is already expressible as a gate plus a "
            "retry policy on this bus. Catalog extraction does not record a "
            "measured effect size versus the existing retry_policy."
        ),
    },
    {
        "id": "T1-09",
        "name": "keyless-signing-sigstore-cosign",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0048 assesses Sigstore/cosign for a file-based plugin "
            "marketplace; adjacent to the Tier-1 attestation row"
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 2,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS+DAEMON",
        },
        "feature_basis": (
            "Fulcio/Rekor (or a freshness log) is a daemon-class dependency. "
            "RES-0048 requires naming attacks the signature does not stop; "
            "that measured-scope finding is E2, but bus-fit still fails GEM."
        ),
    },
    {
        "id": "T1-10",
        "name": "typed-io-and-provenance-from-scientific-workflows",
        "call_sheet_grade": "TIER-1",
        "reconstruction_confidence": "CATALOG-INFERRED",
        "catalog_citation": (
            "RES-0063 extract typed-IO and provenance; evidence_requirement "
            "forbids adopting a second orchestration runtime (_USER-PROMPTS.md:10727)"
        ),
        "features": {
            "leverage": 2,
            "integration_cost": 1,
            "irreplaceable": True,
            "rename_of_existing": False,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "RIDES-BUS+STATE",
        },
        "feature_basis": (
            "The typed-IO *mechanism* can ride the bus; the engine cannot. "
            "No effect size versus this estate's existing artifact schemas "
            "is recorded in the catalog, so evidence is E3."
        ),
    },
]

TIER3: list[dict[str, Any]] = [
    {
        "id": "T3-01",
        "name": "multi-round-free-form-debate-to-consensus",
        "call_sheet_grade": "TIER-3",
        "reconstruction_confidence": "EXPLICIT-TIER-3",
        "catalog_citation": (
            "RES-0076 inputs cite 05-ECOSYSTEM.md:97-103 (Tier 3 rejects) "
            "and asks whether negative evidence explains the 05-ECO reject of "
            "'multi-round free-form debate to consensus'"
        ),
        "features": {
            "leverage": 0,
            "integration_cost": 2,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS+STATE",
        },
        "feature_basis": (
            "Negative-result hunt is the point of RES-0076: debate at or "
            "below a single well-prompted model. Leverage 0 against that baseline."
        ),
    },
    {
        "id": "T3-02",
        "name": "same-vendor-majority-vote",
        "call_sheet_grade": "TIER-3",
        "reconstruction_confidence": "EXPLICIT-TIER-3",
        "catalog_citation": (
            "RES-0078 inputs cite 05-ECOSYSTEM.md:99 "
            "'same-vendor majority-vote reject' and 60%+ correlated errors"
        ),
        "features": {
            "leverage": 0,
            "integration_cost": 1,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E2",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "RIDES-BUS",
        },
        "feature_basis": (
            "Correlated-error figure is inherited as a reject reason. Even "
            "traced, majority-of-the-same-model is not irreplaceable."
        ),
    },
    {
        "id": "T3-03",
        "name": "bespoke-vector-tool-retriever",
        "call_sheet_grade": "TIER-3",
        "reconstruction_confidence": "EXPLICIT-TIER-3",
        "catalog_citation": (
            "RES-0107 inputs cite 05-ECOSYSTEM.md:100 "
            "'bespoke vector tool-retriever reject'; RES-0100 pairs it with "
            "adopt-native at 83-84"
        ),
        "features": {
            "leverage": 1,
            "integration_cost": 2,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "RIDES-BUS+DAEMON",
        },
        "feature_basis": (
            "Vector store is a daemon-class extra; native progressive "
            "disclosure is the catalog's named replacement."
        ),
    },
    {
        "id": "T3-04",
        "name": "second-orchestration-runtime",
        "call_sheet_grade": "TIER-3",
        "reconstruction_confidence": "OUTSIDE-RANGE-REJECT",
        "catalog_citation": (
            "RES-0063 evidence_requirement: a transferable MECHANISM is "
            "adopted, never a second orchestration runtime "
            "(_USER-PROMPTS.md:10727). Not inside lines 97-103."
        ),
        "features": {
            "leverage": 1,
            "integration_cost": 3,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E1",
            "has_baseline": True,
            "has_effect_size": True,
            "bus_fit": "SECOND RUNTIME",
        },
        "feature_basis": (
            "Bus-fit vocabulary names SECOND RUNTIME as the fail-closed class. "
            "High evidence that the rule exists does not make the runtime a GEM."
        ),
    },
    {
        "id": "T3-05",
        "name": "build-a-workflow-language",
        "call_sheet_grade": "TIER-3",
        "reconstruction_confidence": "OUTSIDE-RANGE-REJECT",
        "catalog_citation": (
            "RES-0067 inputs cite 05-ECOSYSTEM.md:118-119 (anti-adoption 1) "
            "'do not build a workflow language'"
        ),
        "features": {
            "leverage": 1,
            "integration_cost": 3,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E3",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "SECOND RUNTIME",
        },
        "feature_basis": (
            "Anti-adoption 1 sits just after the call sheet. Reconstruction "
            "uses it as a fifth negative control, labelled outside 97-103."
        ),
    },
]


def all_rows() -> list[dict[str, Any]]:
    return list(TIER1) + list(TIER3)


def known_good() -> dict[str, Any]:
    """Both-states silent-on-good fixture: T1-01 features, no grade."""
    row = TIER1[0]
    return {
        "id": "CTRL-GOOD",
        "name": row["name"],
        "features": dict(row["features"]),
    }


def known_broken() -> dict[str, Any]:
    """Known-broken: marketing copy of a GEM with failing features."""
    return {
        "id": "CTRL-BROKEN",
        "name": "high-leverage-gem-second-runtime-with-e4-headline",
        "call_sheet_grade": "TIER-1",
        "features": {
            "leverage": 3,
            "integration_cost": 3,
            "irreplaceable": False,
            "rename_of_existing": True,
            "evidence_tier": "E4",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "SECOND RUNTIME",
        },
    }


def grade_leak_mutant() -> dict[str, Any]:
    """If the scorer reads call_sheet_grade it would false-green this row."""
    broken = known_broken()
    broken["id"] = "CTRL-GRADE-LEAK"
    broken["call_sheet_grade"] = "TIER-1"
    broken["features"] = dict(broken["features"])
    return broken
