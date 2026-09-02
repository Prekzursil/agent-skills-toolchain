"""Planted mutants + hand-verified distinct set for CC-0020.

Four calibration classes (exact-rename, paraphrase, one-parameter-fork,
full-rewrite) are authored against two synthetic seeds so the gate is not a
single-string special case. The reviewer fifth class is authored AFTER the
thresholds in mechanism_dedup.py and is not used to retune them.

The 24 distinct catalog units were read (title + question_or_target) and
confirmed as different (population, instrument, purpose) triples. Pairwise
token-Jaccard among them peaks at 0.190 (WFA-0007 vs WFA-0008) — the same
band the catalog quotes for full-rewrite *or* genuine distinction, which is
why lexical-alone cannot separate those two cases.
"""

from __future__ import annotations

from typing import Any

SEED_A_ID = "SYNTH-PIPE-DUAL"
SEED_A_TITLE = "Pipeline step dual-signal completion gate"
SEED_A = (
    "A pipeline step is complete only when the process exit code is zero AND "
    "the declared output artifact bytes exist on disk. A dual detector "
    "AND-gates those two signals; either signal alone is insufficient."
)

SEED_B_ID = "SYNTH-BRANCH-PATCHID"
SEED_B_TITLE = "Branch merge-state classifier via patch-id sets"
SEED_B = (
    "Enumerate git branches and classify each as merged-via-squash, "
    "merged-via-ff, or unmerged by comparing the patch-id set to main, "
    "not the commit hash. Squash rewrites the hash so hash equality is "
    "the wrong instrument."
)

# Reviewer-authored fifth class (SOP / register-shift). Same mechanism as
# seed A, spoken as an operator checklist. Thresholds were not fitted on this
# wording. Distinct from paraphrase (not a near-token shuffle) and from
# full-rewrite (keeps a checklist register rather than a detector thesis).
FIFTH_A = (
    "Operator checklist for signing a stage finished: tick box one only after "
    "the child yields a successful status; tick box two only after the promised "
    "blob sits on the filesystem. Sign the stage finished solely when both "
    "boxes are ticked. A solitary tick never suffices."
)


def _rec(uid: str, title: str, text: str, cls: str, gold_same_as: str) -> dict[str, Any]:
    return {
        "id": uid,
        "title": title,
        "text": f"{title}. {text}",
        "mutant_class": cls,
        "gold_same_as": gold_same_as,
    }


def planted() -> list[dict[str, Any]]:
    """Calibration mutants. Two seeds, four classes each."""
    rows: list[dict[str, Any]] = [
        _rec(SEED_A_ID, SEED_A_TITLE, SEED_A, "seed", SEED_A_ID),
        _rec(SEED_B_ID, SEED_B_TITLE, SEED_B, "seed", SEED_B_ID),
        # exact-rename: same body and title, different identifier only
        _rec(
            "SYNTH-PIPE-DUAL-RENAME",
            SEED_A_TITLE,
            SEED_A,
            "exact-rename",
            SEED_A_ID,
        ),
        _rec(
            "SYNTH-BRANCH-PATCHID-RENAME",
            SEED_B_TITLE,
            SEED_B,
            "exact-rename",
            SEED_B_ID,
        ),
        # paraphrase: clause reorder + light function-word swap; content tokens stay
        _rec(
            "SYNTH-PIPE-DUAL-PARA",
            "Pipeline step dual-signal completion gate",
            (
                "A pipeline step is complete only when the declared output artifact "
                "bytes exist on disk AND the process exit code is zero. Those two "
                "signals are AND-gated by a dual detector; either signal alone is "
                "insufficient."
            ),
            "paraphrase",
            SEED_A_ID,
        ),
        _rec(
            "SYNTH-BRANCH-PATCHID-PARA",
            "Branch merge-state classifier via patch-id sets",
            (
                "Enumerate git branches and classify each as merged-via-ff, "
                "merged-via-squash, or unmerged by comparing the patch-id set to "
                "main, not the commit hash. Hash equality is the wrong instrument "
                "because squash rewrites the hash."
            ),
            "paraphrase",
            SEED_B_ID,
        ),
        # one-parameter fork: add a third conjunct / extra taxonomy label
        _rec(
            "SYNTH-PIPE-DUAL-FORK",
            "Pipeline step dual-signal completion gate",
            (
                "A pipeline step is complete only when the process exit code is zero "
                "AND the declared output artifact bytes exist on disk AND wall-clock "
                "duration is under the timeout. A triple detector AND-gates those "
                "three signals; any two signals alone are insufficient."
            ),
            "one-parameter-fork",
            SEED_A_ID,
        ),
        _rec(
            "SYNTH-BRANCH-PATCHID-FORK",
            "Branch merge-state classifier via patch-id sets",
            (
                "Enumerate git branches and classify each as merged-via-squash, "
                "merged-via-ff, merged-via-rebase, or unmerged by comparing the "
                "patch-id set to main, not the commit hash. Squash rewrites the "
                "hash so hash equality is the wrong instrument."
            ),
            "one-parameter-fork",
            SEED_B_ID,
        ),
        # full rewrite: disjoint surface vocabulary, same mechanism
        _rec(
            "SYNTH-PIPE-DUAL-REWRITE",
            "Stage-finished fused-sensor instrument",
            (
                "Declare a stage finished solely after the child process yields a "
                "successful status together with the promised blob being present in "
                "the filesystem. The instrument fuses both sensors conjunctively; "
                "a solitary sensor never suffices."
            ),
            "full-rewrite",
            SEED_A_ID,
        ),
        _rec(
            "SYNTH-BRANCH-PATCHID-REWRITE",
            "Patch-payload identity taxonomy for branch integration",
            (
                "Walk every ref and bucket it as squash-integrated, fast-forward "
                "integrated, or still-open by matching the payload identity set "
                "against trunk rather than the commit identifier. Squash mints a "
                "fresh identifier, so identifier equality is the incorrect meter."
            ),
            "full-rewrite",
            SEED_B_ID,
        ),
    ]
    return rows


def fifth_mutants() -> list[dict[str, Any]]:
    return [
        _rec(
            "SYNTH-PIPE-DUAL-SOP",
            "Stage-finished operator checklist",
            FIFTH_A,
            "register-shift-sop",
            SEED_A_ID,
        )
    ]


# Hand-verified distinct catalog units. Each line is the mechanism gloss used
# to confirm distinctness (population / instrument / purpose).
DISTINCT_24: list[dict[str, str]] = [
    {"id": "CC-0001", "because": "19-field completeness gate over work-unit rows, not a similarity detector"},
    {"id": "CC-0008", "because": "id allocation + slice merge + collision gate to reach 2048 rows"},
    {"id": "AUD-0001", "because": "git branch inventory with squash-aware merge-state classes"},
    {"id": "AUD-0069", "because": "body-level dedup over option cards (different population than work units)"},
    {"id": "ADV-0001", "because": "adversarial construction of a predicate-passing unusable unit"},
    {"id": "ADV-0096", "because": "idea-count gaming uniqueness gate over brainstorm wording variants"},
    {"id": "ARC-0001", "because": "tournament roster mapping of architecture candidates onto slots"},
    {"id": "ARC-0016", "because": "generated-SSOT escape-hatch reintroduces drift; architecture refute"},
    {"id": "BLD-0001", "because": "never-read file census from a transcript read-ledger"},
    {"id": "BLD-0060", "because": "identifier-space and detector accuracy at 10x catalog scale"},
    {"id": "CNF-0001", "because": "confirmation-receipt and discrepancy-record schemas"},
    {"id": "CNF-0078", "because": "blueprint material distinctness under a second similarity measure"},
    {"id": "CNL-0001", "because": "CouncilSpec v2 root envelope superseding Charter v1"},
    {"id": "IMP-0001", "because": "package payload deny-by-default allowlist manifest"},
    {"id": "IMP-0388", "because": "routing-description quality linter with negative-scope coverage"},
    {"id": "REL-0001", "because": "semver contract with a diff-derived bump linter"},
    {"id": "RES-0001", "because": "shared research claim-record and source-lineage schema family"},
    {"id": "SYN-0001", "because": "root-cause hierarchy as a typed causal DAG"},
    {"id": "SYN-0017", "because": "duplicate-mechanism collapse inside synthesis output, not the input catalog"},
    {"id": "TST-0001", "because": "executable conformance harness for the 12-condition completion predicate"},
    {"id": "TST-0222", "because": "declared tool permissions enforced at runtime"},
    {"id": "WFA-0001", "because": "WFA schema pack of 18 record types"},
    {"id": "WFA-0007", "because": "lexical Jaccard near-dup scan of workflow candidates"},
    {"id": "WFA-0008", "because": "embedding-cosine rescan of the same candidates; different instrument from WFA-0007"},
]


def seeds() -> list[dict[str, Any]]:
    return [r for r in planted() if r["mutant_class"] == "seed"]
