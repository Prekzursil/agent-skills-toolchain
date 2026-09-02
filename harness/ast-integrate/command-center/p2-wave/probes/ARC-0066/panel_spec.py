#!/usr/bin/env python3
"""Seated panel, bench, and independence rules for ARC-0066.

A 2-vendor panel cannot keep both (a) vendor-authorship recusal including
catalog assignment and (b) quorum>=3: 54 of 63 lenses are assigned anthropic.
Minimum vendor diversity is therefore 3, computed from the seated roster.
"""
from __future__ import annotations

PANEL_SIZE = 5
VENDOR_DIVERSITY_MINIMUM = 3
MODEL_DIVERSITY_MINIMUM = 3
QUORUM_MINIMUM = 3
REVIEWER_ID = "auditor.arc0066.independence"

SEATED = [
    {
        "judge_id": "judge.anthropic.opus",
        "vendor": "anthropic",
        "model": "opus",
        "role": "scorer",
        "seat": 1,
    },
    {
        "judge_id": "judge.openai.codex",
        "vendor": "openai",
        "model": "codex-cli-default",
        "role": "scorer",
        "seat": 2,
    },
    {
        "judge_id": "judge.google.gemini",
        "vendor": "google",
        "model": "gemini",
        "role": "scorer",
        "seat": 3,
    },
    {
        "judge_id": "judge.xai.grok",
        "vendor": "xai",
        "model": "grok",
        "role": "scorer",
        "seat": 4,
    },
    {
        "judge_id": "judge.mistral.large",
        "vendor": "mistral",
        "model": "mistral-large",
        "role": "scorer",
        "seat": 5,
    },
]

BENCH = [
    {
        "judge_id": "judge.amazon.nova",
        "vendor": "amazon",
        "model": "nova",
        "role": "replacement",
        "seat": "bench-1",
    },
    {
        "judge_id": "judge.meta.llama",
        "vendor": "meta",
        "model": "llama",
        "role": "replacement",
        "seat": "bench-2",
    },
]

HARD_RULE = (
    "No judge may score an artifact they or their vendor authored. "
    "Authorship is the union of (1) the artifact's own provenance/produced_by "
    "vendor and author_id when present and (2) the catalog assignment vendor. "
    "A catalog-vs-disk mismatch recuses BOTH vendors. Self-declaration is not "
    "evidence and cannot waive recusal."
)

RECUSAL_PROCEDURE = {
    "when": [
        "once at seating, over the 63-lens census",
        "again immediately before each (judge, artifact) dispatch",
    ],
    "detector": "command-center/p2-wave/probes/ARC-0066/conflicts.py",
    "self_declaration": "ignored",
    "on_conflict": (
        "RECUSE. The ballot does not count. The judge is not given the "
        "artifact. Replacement is seated from the bench only if quorum "
        "would otherwise fail."
    ),
    "reason_visibility": (
        "Recusal reasons stay in the dispatch layer. Showing "
        "PROVENANCE_VENDOR=cursor to a judge would identify the author and "
        "break the information partition."
    ),
    "pre_recusal_contributions": "retained, never deleted",
    "replacement_does_not_inherit_votes": True,
}

INFORMATION_PARTITION = {
    "before_scoring_may_see": [
        "de-identified dossier bytes from ARC-0067 once that bundle exists",
        "the pre-registered rubric (ARC-0002) when present, as a hashed file",
        "this panel's independence rules without per-artifact recusal reasons",
        "opaque entry labels, never architecture names",
        "the judge's own notes",
    ],
    "before_scoring_must_not_see": [
        "architecture ids A1-A9 and class names (config-first, generated SSOT, ...)",
        "produced_by / provenance of the dossier under score",
        "catalog assigned_model_vendor_role for that dossier",
        "peer scorecards, peer identities, peer recusal reasons",
        "the ARC-0067 sealed label-to-architecture map",
        "which vendor the detector recused and why",
    ],
    "peer_scores_readable_only_after": "every seated eligible judge has submitted or abstained",
}

QUORUM = {
    "minimum_eligible_judges_per_artifact": QUORUM_MINIMUM,
    "below_quorum": "VOID",
    "void_means": (
        "No architecture verdict is recorded. Seat a bench replacement whose "
        "vendor is not in the recused set; if the bench cannot restore quorum, "
        "the entry remains unscored."
    ),
    "abstention": "an abstention that does not name missing evidence counts as zero, not as a quorum seat",
}

QUESTION = (
    "Who judges, and what makes a judge INDEPENDENT here? Define panel size, "
    "the model/vendor diversity requirement, the hard rule that no judge may "
    "score an artifact they or their vendor authored, the recusal procedure, "
    "the information partition (what each judge may and may not see before "
    "scoring), and the quorum below which a verdict is void."
)


def panel_payload(doc: dict) -> dict:
    """Seated-panel payload lives under report (schema-valid) or at top-level."""
    report = doc.get("report")
    if isinstance(report, dict) and report.get("seated_panel"):
        return report
    return doc
