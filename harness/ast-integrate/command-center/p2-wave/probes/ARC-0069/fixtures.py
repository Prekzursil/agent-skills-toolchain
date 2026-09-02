"""Rubric, panel, gate config, and fixture dossiers for ARC-0069.

Upstream JUDGE-PANEL / RUBRIC / BLIND-BUNDLE / FULL-READ-GATE are absent on
this worktree. This unit does not write those other units' output paths.
Judge-visible entries use opaque labels E-01..E-09 only.
"""
from __future__ import annotations

from typing import Any

DIMENSIONS = [
    {
        "id": "correctness",
        "weight": 0.35,
        "objective": "correctness first: claims match cited dossier sections",
    },
    {
        "id": "singularity",
        "weight": 0.20,
        "objective": "one control plane; duplicate ownership is a defect",
    },
    {
        "id": "evidence_quality",
        "weight": 0.20,
        "objective": "citations, mixed verdicts, falsifiable tests",
    },
    {
        "id": "operational_safety",
        "weight": 0.15,
        "objective": "failure modes, rollback, tests that can fire",
    },
    {
        "id": "resource_efficiency",
        "weight": 0.10,
        "objective": "resource efficiency last: machinery cost vs value",
    },
]

RUBRIC = {
    "id": "ARC-0069-fixture-rubric",
    "source": "command-center/p2-wave/probes/ARC-0069/fixtures.py",
    "note": (
        "Live command-center/phase3/RUBRIC.json is absent (ARC-0002). "
        "This pre-registered fixture is hashed into SCORECARDS.json. "
        "It is not written to ARC-0002's output path."
    ),
    "scale": {"min": 0, "max": 5, "integer": True},
    "dimensions": DIMENSIONS,
    "weight_sum": 1.0,
    "disqualifying": [
        "scorecard citations fail the full-read gate",
        "abstention without named missing evidence (recorded as zero)",
    ],
    "minimum_evidence_to_score": "at least one dossier section other than digest",
}

PANEL = {
    "id": "ARC-0069-fixture-panel",
    "source": "command-center/p2-wave/probes/ARC-0069/fixtures.py",
    "note": (
        "Live command-center/phase3/JUDGE-PANEL.json is absent (ARC-0066). "
        "Three vendor-diverse mechanical judges with isolated read sets. "
        "Not a live LLM dispatch; independence is file-isolation, not vendor RPCs."
    ),
    "quorum": 3,
    "judges": [
        {
            "id": "J-A",
            "vendor": "anthropic",
            "role": "methodologist",
            "policy": "evidence-density; abstain when a required section is absent",
        },
        {
            "id": "J-B",
            "vendor": "openai",
            "role": "critic",
            "policy": "penalize all-confirmed evidence; reward named REFUTED claims",
        },
        {
            "id": "J-C",
            "vendor": "independent",
            "role": "operator",
            "policy": "file-set size, tests, rollback; cost grows with machinery",
        },
    ],
}

GATE = {
    "id": "ARC-0069-fixture-full-read-gate",
    "source": "command-center/p2-wave/probes/ARC-0069/gate.py",
    "note": (
        "Live command-center/phase3/FULL-READ-GATE.json is absent (ARC-0068). "
        "Coverage = distinct top-level sections cited / sections present. "
        "Anchors are derived from the dossier keys, not a hand list."
    ),
    "threshold": 0.5,
    "digest_only_fails": True,
}

LIVE_LENS = {
    "E-01": [
        "command-center/phase3/A1/DESIGN.json",
        "command-center/phase3/A1/FAILURE-MODES.json",
        "command-center/phase3/A1/MIGRATION.json",
        "command-center/phase3/A1/REFUTATION.json",
    ],
    "E-02": [
        "command-center/phase3/A2/DESIGN.json",
        "command-center/phase3/A2/FAILURE-MODES.json",
        "command-center/phase3/A2/MIGRATION.json",
        "command-center/phase3/A2/REFUTATION.json",
    ],
}

LENS_KEYS = {
    "DESIGN.json": "design",
    "FAILURE-MODES.json": "failure_modes",
    "MIGRATION.json": "migration",
    "REFUTATION.json": "refutation",
}


def _base(
    *,
    file_n: int,
    stopped: bool,
    first: str | None,
    dual_plane: bool,
    evidence: list[dict],
    tests: list[dict] | None,
    failure_modes: dict | None,
    migration: dict | None,
    extra_design: dict | None = None,
) -> dict[str, Any]:
    design: dict[str, Any] = {
        "file_set_count": file_n,
        "file_set": [f"cap/{i:02d}.json" for i in range(file_n)],
        "precedence": {
            "rule": "later load_order replaces earlier whole-object",
            "dual_plane_risk": dual_plane,
        },
        "expressibility": {
            "stopped_at_first_inexpressible": stopped,
            "first_non_expressible_construct": first,
        },
    }
    if extra_design:
        design.update(extra_design)
    doc: dict[str, Any] = {
        "design": design,
        "samples": [
            {"id": "skill.sample", "verdict": "EXPRESSIBLE"},
            {"id": "wf.sample", "verdict": "EXPRESSIBLE"},
            {"id": "preset.sample", "verdict": "EXPRESSIBLE" if not stopped else "INEXPRESSIBLE"},
        ],
        "evidence": evidence,
        "digest": {
            "one_paragraph": "opaque entry summary for digest-only negative control"
        },
    }
    if tests is not None:
        doc["tests"] = tests
    if failure_modes is not None:
        doc["failure_modes"] = failure_modes
    if migration is not None:
        doc["migration"] = migration
    return doc


FIXTURE_ENTRIES: dict[str, dict[str, Any]] = {
    "E-03": _base(
        file_n=12,
        stopped=False,
        first=None,
        dual_plane=False,
        evidence=[
            {"claim": "index is the control plane", "verdict": "CONFIRMED", "anchor": "design"},
            {"claim": "lockfile pins installs", "verdict": "CONFIRMED", "anchor": "design"},
        ],
        tests=[{"id": "install", "result": "PASS"}],
        failure_modes={"stale_index": "named", "offline_install": "named"},
        migration={"from": "loose files", "to": "lockfile", "rollback": True},
    ),
    "E-04": _base(
        file_n=4,
        stopped=True,
        first="runtime activation graph",
        dual_plane=False,
        evidence=[
            {"claim": "lazy mount is declared", "verdict": "CONFIRMED", "anchor": "design"}
        ],
        tests=None,
        failure_modes=None,
        migration=None,
    ),
    "E-05": _base(
        file_n=8,
        stopped=True,
        first="cross-node consensus predicate",
        dual_plane=False,
        evidence=[],
        tests=[{"id": "partition", "result": "PASS"}, {"id": "quorum", "result": "PASS"}],
        failure_modes={"split_brain": "named", "lost_write": "named"},
        migration={"from": "single node", "to": "runtime", "rollback": True},
    ),
    "E-06": _base(
        file_n=6,
        stopped=True,
        first="vendor-specific tool dialect",
        dual_plane=True,
        evidence=[
            {"claim": "one adapter surface", "verdict": "CONFIRMED", "anchor": "design"},
            {"claim": "no second permission plane", "verdict": "REFUTED", "anchor": "design.precedence"},
        ],
        tests=[{"id": "translate", "result": "PASS"}],
        failure_modes={"dialect_drift": "named"},
        migration={"from": "native tools", "to": "adapter", "rollback": True},
    ),
    "E-07": _base(
        file_n=5,
        stopped=True,
        first="owner-bypass of the permission evaluator",
        dual_plane=False,
        evidence=[
            {"claim": "single evaluator", "verdict": "CONFIRMED", "anchor": "design"},
            {"claim": "default-deny", "verdict": "CONFIRMED", "anchor": "design"},
            {"claim": "unreviewed allow-all path", "verdict": "REFUTED", "anchor": "failure_modes"},
        ],
        tests=[{"id": "deny", "result": "PASS"}, {"id": "allow", "result": "PASS"}],
        failure_modes={"confused_deputy": "named", "secret_leak": "named"},
        migration={"from": "scattered checks", "to": "evaluator", "rollback": True},
    ),
    "E-08": _base(
        file_n=7,
        stopped=False,
        first=None,
        dual_plane=False,
        evidence=[
            {"claim": "operator journey is specified", "verdict": "CONFIRMED", "anchor": "design"},
            {"claim": "error copy is specified", "verdict": "CONFIRMED", "anchor": "design"},
        ],
        tests=None,
        failure_modes={"silent_loss": "named"},
        migration=None,
        extra_design={"journeys": ["install", "recover", "audit"]},
    ),
    "E-09": _base(
        file_n=20,
        stopped=True,
        first="composition that yields two permission evaluators",
        dual_plane=True,
        evidence=[
            {"claim": "control planes remain singular", "verdict": "REFUTED", "anchor": "design.precedence"},
            {"claim": "strongest mechanism list is enumerated", "verdict": "CONFIRMED", "anchor": "design"},
        ],
        tests=[{"id": "duplicate-plane-detector", "result": "PASS"}],
        failure_modes={"overlapping_ownership": "named", "concept_count": "named"},
        migration={"from": "single class", "to": "composed", "rollback": True, "stages": 4},
    ),
}


def fixture_entry(eid: str) -> dict[str, Any]:
    if eid not in FIXTURE_ENTRIES:
        raise KeyError(eid)
    return FIXTURE_ENTRIES[eid]


# Fallback dossiers when live A1/A2 lens files are absent.
FIXTURE_ENTRIES["E-01"] = _base(
    file_n=9,
    stopped=True,
    first="runtime stopping predicate over prior rounds",
    dual_plane=False,
    evidence=[
        {"claim": "static file set is declared", "verdict": "CONFIRMED", "anchor": "design"},
        {"claim": "libraries were read from this tree", "verdict": "REFUTED", "anchor": "design"},
    ],
    tests=[{"id": "independent-replication", "result": "PASS"}],
    failure_modes={"drift_after_fact": "named"},
    migration={"from": "scattered files", "to": "static tree", "rollback": True},
)
FIXTURE_ENTRIES["E-02"] = _base(
    file_n=10,
    stopped=True,
    first="opaque untyped blob copied into generated output",
    dual_plane=False,
    evidence=[
        {"claim": "generator is byte-identical across two runs", "verdict": "CONFIRMED", "anchor": "design"},
        {"claim": "hand-edit is TAMPERED", "verdict": "CONFIRMED", "anchor": "tests"},
        {"claim": "libraries present on this tree", "verdict": "REFUTED", "anchor": "design"},
    ],
    tests=[{"id": "marking", "result": "PASS"}, {"id": "tamper", "result": "PASS"}],
    failure_modes={"silent_hand_edit": "named"},
    migration={"from": "hand files", "to": "generated", "rollback": True},
)

DIMENSIONS = DIMENSIONS
LIVE_LENS = LIVE_LENS
LENS_KEYS = LENS_KEYS
FIXTURE_ENTRIES = FIXTURE_ENTRIES
