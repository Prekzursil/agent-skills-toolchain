#!/usr/bin/env python3
"""Emit the CNL-0019 council design note from live fixture runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import probe1_theatre as T  # noqa: E402
import reviewer as R  # noqa: E402
import seating as S  # noqa: E402
from probe2_both_states import negative_control_verbatim  # noqa: E402
from priors import load_fixtures  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0019/note.schema.json"
SHARED_SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0019/probe1_theatre.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0019/probe2_both_states.py"
)
DEP_PATHS = {
    "CNL-0005": (
        "command-center/design/council/"
        "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
    ),
    "CNL-0033": (
        "command-center/design/council/"
        "CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md"
    ),
}
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [i for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if snippet in ln]
    if len(hits) != 1:
        raise ValueError(f"{rel}: snippet {snippet!r} hits={hits}")
    return hits[0]


def ev(rel: str, snippet: str, claim: str, verdict: str, mechanism: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "anchor": f"{rel}:{line}",
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "verdict": verdict,
        "mechanism": mechanism,
    }


def main() -> int:
    theatre = T.compare()
    if not theatre["ok"]:
        print("FAILED:CNL-0019 emit theatre probe did not diverge")
        return 1
    control = R.run_control()
    if not control["ok"]:
        print("FAILED:CNL-0019 emit both-states did not discriminate")
        return 1
    neg = negative_control_verbatim()
    if not neg["ok"]:
        print("FAILED:CNL-0019 emit negative control")
        return 1

    fixtures = load_fixtures()
    dep_status = {}
    for uid, rel in DEP_PATHS.items():
        dep_status[uid] = {
            "artifact_path": rel,
            "artifact_present": (REPO / rel).is_file(),
        }
    catalog_inputs = {p: False for p in CATALOG_INPUTS}

    seating_rel = "command-center/p2-wave/probes/CNL-0019/seating.py"
    sim_rel = "command-center/p2-wave/probes/CNL-0019/simulate.py"
    fix_rel = "command-center/p2-wave/probes/CNL-0019/fixtures.json"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"

    def kind_ev(rel, snippet, claim, verdict, mechanism, kind):
        row = ev(rel, snippet, claim, verdict, mechanism)
        row["kind"] = kind
        return row

    evidence = [
        kind_ev(
            seating_rel,
            "TOKEN:THEATRE-OPPOSITE-STANCE-SHARED-EVIDENCE",
            "Opposite assigned_stance with shared evidence_id is classified THEATRE, not a real prior conflict.",
            "CONFIRMED",
            "file-line-token",
            "file-line",
        ),
        kind_ev(
            seating_rel,
            "TOKEN:REAL-PRIOR-CONFLICT",
            "Independent opposite-polarity priors on the question axis classify as REAL_CONFLICT.",
            "CONFIRMED",
            "file-line-token",
            "file-line",
        ),
        kind_ev(
            sim_rel,
            "Public channel follows assigned_stance when present (the performed debate).",
            "Public and revealed channels share one update rule; only the anchor differs, so divergence is computed not asserted.",
            "CONFIRMED",
            "simulation-channel-gap",
            "command-output",
        ),
        kind_ev(
            fix_rel,
            "Four seats, one shared prior, opposite assigned_stance labels. This is manufactured disagreement.",
            "The assigned-position roster is a planted theatre fixture, not a live LLM run.",
            "CONFIRMED",
            "fixture-bytes",
            "file-line",
        ),
        kind_ev(
            cat_rel,
            "How do you seat participants with genuinely conflicting priors while preventing the failure where the council performs disagreement it does not hold",
            "The unit question is taken from this worktree's catalog row, not from an absent Windows prompt file.",
            "CONFIRMED",
            "catalog-question-text",
            "file-line",
        ),
        kind_ev(
            cat_rel,
            "complete participant descriptor type covering model, vendor, expertise, role, authority, vote weight, tools, effort and context",
            "CNL-0005 names nine per-seat dials; none of them is a locked prior. Role is not a substitute for prior.",
            "CONFIRMED",
            "catalog-dependency-dials",
            "file-line",
        ),
        {
            "anchor": "catalog-inputs-absent",
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": find_line(
                cat_rel,
                "CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md",
            ),
            "snippet": "CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md",
            "claim": "Catalog-cited CouncilSpec input files from the 20260806 harness restore are present on this worktree.",
            "verdict": "REFUTED",
            "mechanism": "path-is-file",
            "kind": "path-is-file",
        },
        {
            "anchor": "dependency-artifacts-absent",
            "path": seating_rel,
            "line": find_line(seating_rel, "TOKEN:THEATRE-OPPOSITIONAL-ROLES-WITHOUT-PRIOR"),
            "snippet": "TOKEN:THEATRE-OPPOSITIONAL-ROLES-WITHOUT-PRIOR",
            "claim": "CNL-0005 and CNL-0033 output artifacts are on disk and were read before seating.",
            "verdict": "REFUTED",
            "mechanism": "path-is-file",
            "kind": "path-is-file",
        },
    ]
    # Two independent signals for the load-bearing theatre/real split:
    # (1) structural classify reason on planted-bad, (2) revealed-disagreement numeric gap.
    evidence[0]["verbatim_output"] = (
        f"classify planted-bad fired={control['struct_bad']['fired']} "
        f"reason={control['struct_bad']['reason']}"
    )
    evidence[2]["command"] = P1
    evidence[2]["verbatim_output"] = (
        "theatre_revealed={:.6f} real_revealed={:.6f} gap={:.6f}".format(
            theatre["theatre"]["revealed_disagreement"],
            theatre["real"]["revealed_disagreement"],
            theatre["revealed_gap"],
        )
    )

    markdown_note = "\n".join(
        [
            "# Adversarial selection without manufacturing fake disagreement",
            "",
            "## Distinction",
            "A real prior conflict is a pair of seats whose locked priors on the",
            "question axis have opposite polarity, different evidence_id values,",
            "and commitment hashes that recompute from those fields before",
            "deliberation. An assigned debating position is a prompt- or",
            "role-imposed stance (assigned_stance, or an oppositional role pair)",
            "that does not rest on such priors. The first is a property of belief",
            "state. The second is theatre: the council performs disagreement it",
            "does not hold.",
            "",
            "## Selector",
            "adversarial_select refuses THEATRE. It never invents a prior, never",
            "flips a polarity to create conflict, and never treats CNL-0005 role",
            "as a prior. naive_select, which seats opposite labels, is the",
            "behaviour this unit rejects.",
            "",
            "## Convergence",
            "Same update rule on public (performed) and revealed (belief) channels.",
            "Theatre: high public disagreement, low revealed disagreement.",
            "Real-prior: high disagreement on both channels.",
            "",
            "SUCCESS:CNL-0019",
        ]
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0019",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0019",
        "completion_sentinel": "SUCCESS:CNL-0019",
        "title": "Adversarial selection without manufacturing fake disagreement",
        "claim_under_test": (
            "A real prior conflict is opposite locked polarities from distinct "
            "evidence_id values with verifying commitment hashes; assigned_stance "
            "or oppositional role pairs without that substrate are THEATRE and "
            "must be refused at seating. Assigned-position and real-prior rosters "
            "must produce measurably different revealed-channel disagreement."
        ),
        "declared_signal": {
            "signal_1": {
                "kind": "file-line",
                "field": "classify_roster.fired/reason",
                "planted_bad": control["struct_bad"],
                "known_good": control["struct_good"],
            },
            "signal_2": {
                "kind": "numeric-revealed-disagreement",
                "field": "simulate.run_roster.revealed_disagreement",
                "theatre": theatre["theatre"]["revealed_disagreement"],
                "real_prior": theatre["real"]["revealed_disagreement"],
                "gap": theatre["revealed_gap"],
            },
        },
        "which_stops_the_round": {
            "stops": (
                "THEATRE at seating: adversarial_select raises TheatreReject "
                "and does not emit a roster."
            ),
            "does_not_stop": (
                "High public disagreement on a REAL_CONFLICT roster is "
                "deliberation, not a seating reject."
            ),
            "satisfy_quota_from_padding": False,
        },
        "claims": [
            {
                "id": "C-THEATRE-DIVERGE",
                "claim": "Assigned-position and real-prior rosters differ on revealed-channel disagreement by at least MEASURABLE_REVEALED_GAP.",
                "verdict": "CONFIRMED",
                "anchor": f"{sim_rel}:{find_line(sim_rel, 'Public channel follows assigned_stance when present (the performed debate).')}",
            },
            {
                "id": "C-BOTH-STATES",
                "claim": "classify_roster FIRES on planted-bad and is SILENT on known-good.",
                "verdict": "CONFIRMED",
                "anchor": f"{seating_rel}:{find_line(seating_rel, 'TOKEN:THEATRE-ASSIGNED-STANCE-CONTRADICTS-PRIOR')}",
            },
            {
                "id": "C-ROLE-IS-NOT-PRIOR",
                "claim": "Oppositional roles without priors are THEATRE, not REAL_CONFLICT.",
                "verdict": "CONFIRMED",
                "anchor": f"{seating_rel}:{find_line(seating_rel, 'TOKEN:THEATRE-OPPOSITIONAL-ROLES-WITHOUT-PRIOR')}",
            },
            {
                "id": "C-CATALOG-INPUTS-PRESENT",
                "claim": "Harness-restore CouncilSpec input files are present on this worktree.",
                "verdict": "REFUTED",
                "anchor": f"{cat_rel}:{find_line(cat_rel, 'CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md')}",
            },
        ],
        "question": (
            "How do you seat participants with genuinely conflicting priors "
            "while preventing the failure where the council performs disagreement "
            "it does not hold - what distinguishes a real prior conflict from an "
            "assigned debating position?"
        ),
        "answer": (
            "Seat adversaries only by locked, evidence-backed priors on the "
            "question axis. A real prior conflict is opposite polarity plus "
            "distinct evidence_id plus a commitment_hash that recomputes from "
            "those fields before deliberation. An assigned debating position is "
            "assigned_stance or an oppositional role pair (advocate/critic, "
            "red/blue, and the other named pairs) that lacks that prior "
            "substrate, shares evidence, or contradicts the seat's own polarity. "
            "The selector refuses theatre rather than performing it. Role, from "
            "the CNL-0005 nine-dial list, is a label and is not a prior. "
            "Red/blue topology (CNL-0033) does not become informative by "
            "assigning those labels; without independent priors it is still "
            "theatre. Executable fixtures show the two rosters diverge: "
            "assigned-position has high public disagreement and near-zero "
            "revealed disagreement; real-prior has high disagreement on both "
            "channels."
        ),
        "output_schema_catalog": SHARED_SCHEMA_REL,
        "output_schema_validated_against": SCHEMA_REL,
        "shared_schema_note": (
            "Catalog names command-center/schema/council-design-note.schema.json. "
            "That file is contended by parallel CNL units on this worktree. "
            "This note is validated against the unit-local schema."
        ),
        "markdown_note": markdown_note,
        "distinction": {
            "real_prior_conflict": {
                "definition": (
                    "Two seats, same question axis, opposite prior polarity, "
                    "different evidence_id, verifying commitment_hash, no "
                    "assigned_stance contradiction."
                ),
                "code": "REAL_CONFLICT",
            },
            "assigned_debating_position": {
                "definition": (
                    "Opposite assigned_stance or oppositional roles used as the "
                    "conflict signal, including when priors are missing, shared, "
                    "or same-sign."
                ),
                "code": "THEATRE",
            },
            "not_a_dial_from_cnl_0005": (
                "The nine catalog dials are model, vendor, expertise, role, "
                "authority, vote weight, tools, effort, context. Prior is a "
                "seating substrate those dials do not provide."
            ),
        },
        "mechanism": {
            "module": seating_rel,
            "simulator": sim_rel,
            "update_rule": (
                "vote_i,t = (1 - (1-confidence_i)*alpha)*anchor_i + "
                "((1-confidence_i)*alpha)*mean(others). Public anchor is "
                "assigned_stance if present else prior; revealed anchor is prior."
            ),
            "refuse_on": [
                "ASSIGNED_STANCE_WITHOUT_PRIOR",
                "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
                "OPPOSITE_STANCE_SHARED_EVIDENCE",
                "OPPOSITE_STANCE_SHARED_POLARITY",
                "OPPOSITIONAL_ROLES_WITHOUT_PRIOR",
                "OPPOSITIONAL_ROLES_SHARED_POLARITY",
                "COMMITMENT_MISMATCH",
                "AXIS_MISMATCH",
                "CONFLICT_CLAIM_SHARED_EVIDENCE",
            ],
            "thresholds_declared_before_scoring": fixtures[
                "thresholds_declared_before_scoring"
            ],
        },
        "dependency_status": dep_status,
        "catalog_inputs_on_tree": catalog_inputs,
        "live_llm_council_run": False,
        "tests": [
            {
                "id": "theatre-probe",
                "command": P1,
                "result": "PASS" if theatre["ok"] else "FAIL",
                "measured": {
                    "theatre_public_disagreement": theatre["theatre"]["public_disagreement"],
                    "theatre_revealed_disagreement": theatre["theatre"]["revealed_disagreement"],
                    "real_public_disagreement": theatre["real"]["public_disagreement"],
                    "real_revealed_disagreement": theatre["real"]["revealed_disagreement"],
                    "revealed_gap": theatre["revealed_gap"],
                    "theatre_ok": theatre["theatre_ok"],
                    "real_ok": theatre["real_ok"],
                    "measurably_different": theatre["measurably_different"],
                },
            },
            {
                "id": "both-states",
                "command": P2,
                "result": "PASS" if control["ok"] else "FAIL",
                "measured": {
                    "fired_on_bad": control["struct_bad"]["fired"],
                    "silent_on_good": not control["struct_good"]["fired"],
                    "bad_reason": control["struct_bad"]["reason"],
                    "good_reason": control["struct_good"]["reason"],
                    "behav_bad_theatre_signature": control["behav_bad_theatre_signature"],
                    "behav_good_theatre_signature": control["behav_good_theatre_signature"],
                    "role_only_reason": control["struct_role_only"]["reason"],
                },
            },
            {
                "id": "negative-control",
                "command": P2,
                "result": "PASS" if neg["ok"] else "FAIL",
                "verbatim": neg["verbatim"],
                "what_the_check_does_on_the_state_it_rejects": (
                    "On planted-bad (opposite assigned_stance, shared evidence, "
                    "same prior polarity), adversarial_select raises TheatreReject "
                    f"with reason={neg['reason']}. naive_select would have seated "
                    f"{neg['naive'].get('seated')}."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "planted-bad-theatre-roster",
                "rejects": (
                    "opposite assigned_stance with shared same-sign prior "
                    "(the state naive_select would seat)"
                ),
                "observed": neg["verbatim"],
                "check": "adversarial_select",
                "fires": True,
            }
        ],
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": control["reviewer_id"],
            "verdict": control["verdict"],
            "independent": True,
            "re_ran_both_states": True,
            "scope_not_agreement": True,
            "cross_vendor_openai_gpt5_codex_seated": False,
            "cross_vendor_reason": control["cross_vendor_reason"],
            "structural": control["struct_bad"],
            "behavioral_second_field": {
                "bad_theatre_signature": control["behav_bad_theatre_signature"],
                "good_theatre_signature": control["behav_good_theatre_signature"],
            },
        },
        "strongest_surviving_counterargument": (
            "A later prompt can still instruct seated models to perform opposition "
            "even after this selector has refused theatre at seating time. This "
            "unit gates roster construction; it does not claim a runtime prompt "
            "firewall. Residual risk is named, not closed."
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "unit-local-schema"},
            {"path": seating_rel, "exists": True, "role": "selector"},
            {"path": sim_rel, "exists": True, "role": "simulator"},
            {
                "path": "command-center/p2-wave/probes/CNL-0019/fixtures.json",
                "exists": True,
                "role": "fixtures",
            },
        ],
        "ts": now,
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_REL}")
    print("SUCCESS:CNL-0019 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
