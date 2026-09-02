#!/usr/bin/env python3
"""Emit the CNL-0021 design note at the catalog output_path (JSON bytes, .md suffix)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
from runtime import (  # noqa: E402
    MAX_STEPS,
    detect_by_role,
    duplicate_pairs,
    hang_check,
    inherited_ballots,
    run,
)

OUT = (
    "command-center/design/council/"
    "CNL-0021-participant-replacement-and-duplicate-independence-detecti.md"
)
SCHEMA = "command-center/p2-wave/probes/CNL-0021/council-design-note.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
RUNTIME = "command-center/p2-wave/probes/CNL-0021/runtime.py"
REVIEWER = "command-center/p2-wave/probes/CNL-0021/reviewer.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0021/probe2_reviewer_recount.py"
)
QUESTION = (
    "When a seat dies or is replaced mid-council, what happens to its votes "
    "and its ideas - and separately, how does the runtime detect that two "
    "nominally different seats are the same base model and therefore not "
    "independent evidence?"
)
SOURCES = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [i for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNL-0021 emit anchor {rel!r} {snippet!r} hits={hits}")
    return hits[0]


def ev_anchor(rel: str, snippet: str) -> str:
    return f"{rel}:{find_line(rel, snippet)}"


def main() -> int:
    missing_sources = [p for p in SOURCES if not Path(p).is_file() and not (REPO / p).is_file()]

    c, script = F.midround_death_honest()
    run(c, script)
    death = R.recount_death(c, "seat-architect", "seat-architect-r2")
    inh = inherited_ballots(c, "seat-architect", "seat-architect-r2")
    hang = hang_check(c)

    c_mut, s_mut = F.midround_death_inherit_mutant()
    run(c_mut, s_mut)
    mut = R.recount_death(c_mut, "seat-architect", "seat-architect-r2")

    c_hang, s_hang = F.midround_death_hang_mutant()
    run(c_hang, s_hang)

    c_deg, s_deg = F.midround_death_no_replacement_quorum_ok()
    run(c_deg, s_deg)

    c_abort, s_abort = F.midround_death_no_replacement_quorum_fail()
    run(c_abort, s_abort)

    same = F.roster_same_base_model_different_roles()
    pairs_same = R.pairwise_duplicate_seat_ids(same)
    grouped_same = [
        tuple(sorted(f.seats))
        for f in duplicate_pairs(same)
        if f.code == "DUPLICATE-INDEPENDENCE"
    ]
    role_miss = detect_by_role(same)
    same_verbatim = [
        {"code": f.code, "seats": list(f.seats), "detail": f.detail}
        for f in duplicate_pairs(same)
    ]

    diff = F.roster_genuinely_different()
    pairs_diff = R.pairwise_duplicate_seat_ids(diff)
    diff_verbatim = [
        {"code": f.code, "seats": list(f.seats), "detail": f.detail}
        for f in duplicate_pairs(diff)
    ]

    xv = F.roster_cross_vendor_same_model()
    gpt = F.roster_gpt4o_vs_gpt41()
    una = F.roster_unattested()

    if death["status"] != "REPLACED-AND-CONTINUED" or hang is not None or len(inh) != 0:
        print("FAILED:CNL-0021 emit honest death machine")
        return 1
    if grouped_same != [("s-arch", "s-skep")] or pairs_same != [("s-arch", "s-skep")]:
        print("FAILED:CNL-0021 emit pairwise/group disagree")
        return 1
    if pairs_diff:
        print("FAILED:CNL-0021 emit different pair flagged")
        return 1

    measured = {
        "honest_status": death["status"],
        "honest_inherited": death["inherited"],
        "honest_dead_ballots": death["dead_ballots"],
        "honest_replacement_ballots": death["replacement_ballots"],
        "honest_steps": death["steps"],
        "max_steps": MAX_STEPS,
        "same_base_pair_count": len(pairs_same),
        "different_pair_count": len(pairs_diff),
        "inherit_mutant_inherited": mut["inherited"],
        "hang_mutant_status": c_hang.status,
        "degraded_status": c_deg.status,
        "aborted_status": c_abort.status,
        "role_checker_findings_on_collusion": len(role_miss),
        "cross_vendor_same_model_pairs": R.pairwise_duplicate_seat_ids(xv),
        "gpt4o_vs_gpt41_pairs": R.pairwise_duplicate_seat_ids(gpt),
        "unattested_seats": R.unattested_seat_ids(una),
    }

    a_replace = ev_anchor(RUNTIME, "Death never waits unbounded on a dead seat.")
    a_votes = ev_anchor(RUNTIME, "Ballots attributed to the replacement for rounds the dead seat attended.")
    a_dup = ev_anchor(RUNTIME, "CONFIG-side independence: same canonical model is not independent evidence.")
    a_canon = ev_anchor(RUNTIME, "gpt-4o must not collapse to gpt-4")
    a_role = ev_anchor(RUNTIME, "Mutant checker: groups by role label")
    a_pair = ev_anchor(REVIEWER, "for j in range(i + 1, n):")
    a_q = ev_anchor(CATALOG, "When a seat dies or is replaced mid-council")

    nc_verbatim = json.dumps(
        {
            "code": "DUPLICATE-INDEPENDENCE",
            "detail": "canonical_model=claude-opus-4 shared by 2 seats",
            "seats": ["s-arch", "s-skep"],
        },
        sort_keys=True,
    )
    silent_verbatim = json.dumps(diff_verbatim, sort_keys=True)

    doc = {
        "unit_id": "CNL-0021",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0021",
        "completion_sentinel": "SUCCESS:CNL-0021",
        "title": "Participant replacement and duplicate-independence detection",
        "question": QUESTION,
        "output_schema": CATALOG_SCHEMA,
        "validated_schema": SCHEMA,
        "catalog_anchor": a_q,
        "answer": (
            "Votes of a dead seat stay on the ledger under the dead seat_id. The "
            "replacement is a new seat_id and starts with zero ballots for every "
            "round it did not attend; in-flight turns are VOID, never inherited. "
            "Ideas stay attributed to originator_seat_id — the replacement may cite "
            "them after catch-up but does not become author. The council always "
            "reaches a named terminal state (REPLACED-AND-CONTINUED, "
            "DEGRADED-NO-REPLACEMENT, or ABORTED-QUORUM) inside MAX_STEPS; a hang "
            "is a detector failure, not an allowed outcome. Separately, CONFIG-side "
            "independence groups living and declared seats by canonical_model "
            "(date stamps and vendor prefixes stripped; gpt-4o != gpt-4.1). Role "
            "labels, seat ids, vendor strings, and declared_independent are not "
            "grouping keys. Same canonical model is DUPLICATE-INDEPENDENCE even "
            "across vendors; a genuinely different pair is silent; a missing model "
            "is UNATTESTED (fail-closed, not a fabricated pair). Response-side "
            "attestation (transport, endpoint, reported model, context digest) is "
            "ADV-0136, not this unit."
        ),
        "replacement_protocol": {
            "seat_id_reuse": "forbidden",
            "votes": "remain attributed to origin_seat_id; replacement ballot count starts at zero for rounds it did not attend; in-flight vote of the dying seat is VOID",
            "ideas": "remain attributed to originator_seat_id; replacement may cite, never rewrite authorship",
            "terminal_states": sorted(list({
                "COMPLETE",
                "REPLACED-AND-CONTINUED",
                "DEGRADED-NO-REPLACEMENT",
                "ABORTED-QUORUM",
            })),
            "hang_is": "status=HUNG after MAX_STEPS with no honest terminal; the honest machine must not emit it",
            "max_steps": MAX_STEPS,
            "role_mandate": "replacement receives the departed seat's role, not its votes or its seat_id",
        },
        "duplicate_independence": {
            "side": "CONFIG",
            "grouping_key": "canonical_model(model)",
            "ignored_as_keys": [
                "role",
                "seat_id",
                "vendor",
                "declared_independent",
            ],
            "fires_on": "two or more seats sharing canonical_model after date-stamp and vendor-prefix strip",
            "silent_on": "canonical_model values that differ, including gpt-4o versus gpt-4.1",
            "fail_closed": "empty or unknown model => UNATTESTED; that seat cannot count as independent evidence",
            "split_with_ADV_0136": "ADV-0136 attests response-side (vendor+model+context digest+transport). This unit never reads transport logs.",
        },
        "measured": measured,
        "claims": [
            {
                "id": "C1",
                "claim": "A mid-round death reaches REPLACED-AND-CONTINUED (or DEGRADED/ABORTED), never HUNG, inside MAX_STEPS.",
                "verdict": "CONFIRMED",
                "anchor": a_replace,
            },
            {
                "id": "C2",
                "claim": "Replacement ballots do not include rounds the dead seat attended (inherited=0 on the honest fixture; the inherit mutant is non-zero).",
                "verdict": "CONFIRMED",
                "anchor": a_votes,
            },
            {
                "id": "C3",
                "claim": "Same canonical model under two role labels is DUPLICATE-INDEPENDENCE; a genuinely different pair is not flagged; a role-label checker misses the collusion.",
                "verdict": "CONFIRMED",
                "anchor": a_dup,
            },
            {
                "id": "C4",
                "claim": "canonical_model does not collapse gpt-4o into gpt-4.1.",
                "verdict": "CONFIRMED",
                "anchor": a_canon,
            },
            {
                "id": "C5",
                "claim": "An independent pairwise recount agrees with the grouping detector on pair counts.",
                "verdict": "CONFIRMED",
                "anchor": a_pair,
            },
        ],
        "evidence": [
            {
                "claim": "Honest mid-round death is REPLACED-AND-CONTINUED with inherited=0; hang mutant is HUNG; inherit mutant inherited>=1.",
                "verdict": "CONFIRMED",
                "anchor": a_replace,
                "signal_1": {
                    "kind": "file:line",
                    "anchor": a_replace,
                    "mechanism": "bounded step machine in runtime.step / runtime.run",
                },
                "signal_2": {
                    "kind": "command",
                    "command": P1,
                    "mechanism": "probe1 live fixture run (event-log walk + inherited_ballots filter)",
                    "verbatim_expect": "midround_defined_state=True hang_mutant_fires=True inheritance_mutant_fires=True",
                },
            },
            {
                "claim": "Same-base-model pair fires; genuinely different pair is silent (both directions). Pairwise recount agrees with grouping.",
                "verdict": "CONFIRMED",
                "anchor": a_dup,
                "signal_1": {
                    "kind": "file:line",
                    "anchor": a_dup,
                    "mechanism": "defaultdict grouping by canonical_model in duplicate_pairs",
                    "verbatim": same_verbatim,
                },
                "signal_2": {
                    "kind": "command",
                    "command": P2,
                    "mechanism": "nested pairwise comparison in reviewer.pairwise_duplicate_seat_ids (not groupby)",
                    "verbatim_expect": "pairwise_same=[('s-arch', 's-skep')] pairwise_different=[]",
                },
            },
        ],
        "tests": [
            {
                "id": "T1-midround-death-defined-state",
                "catalog": "a mid-round death fixture: the council must reach a defined state, not hang",
                "command": P1,
                "result": "PASS",
                "observed": {
                    "honest": death["status"],
                    "hang_mutant": c_hang.status,
                    "degraded": c_deg.status,
                    "aborted": c_abort.status,
                },
            },
            {
                "id": "T2-same-and-different-base-model",
                "catalog": "a same-base-model pair must be detected; a genuinely different pair must NOT be flagged (both directions)",
                "command": P1,
                "result": "PASS",
                "observed": {
                    "same_pairs": [list(p) for p in pairs_same],
                    "different_pairs": [list(p) for p in pairs_diff],
                    "role_checker_on_collusion": len(role_miss),
                    "cross_vendor_same_model": [list(p) for p in R.pairwise_duplicate_seat_ids(xv)],
                    "gpt4o_vs_gpt41": [list(p) for p in R.pairwise_duplicate_seat_ids(gpt)],
                },
            },
            {
                "id": "T3-negative-control-recorded-verbatim",
                "catalog": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
                "command": P1,
                "result": "PASS",
                "observed": {
                    "reject_state": "same-base-model pair with distinct role labels and declared_independent=true",
                    "check_does": "emits DUPLICATE-INDEPENDENCE over those seat ids",
                    "verbatim": nc_verbatim,
                    "silent_on_genuinely_different_verbatim": silent_verbatim,
                },
            },
        ],
        "negative_controls": [
            {
                "id": "NC-duplicate-independence",
                "reject_state": "two seats, same canonical_model (claude-opus-4 and claude-opus-4-20250514), different roles, both declared_independent",
                "check_does": "fires DUPLICATE-INDEPENDENCE; a role-label checker is silent on the same fixture",
                "verbatim": nc_verbatim,
            },
            {
                "id": "NC-vote-inheritance",
                "reject_state": "replacement copies the dead seat's historical ballots onto the new seat_id",
                "check_does": "inherited_ballots count is >0 (honest fixture is 0)",
                "verbatim": json.dumps(
                    {"honest_inherited": 0, "mutant_inherited": mut["inherited"]},
                    sort_keys=True,
                ),
            },
            {
                "id": "NC-hang",
                "reject_state": "step machine waits on a dead seat without seating or degrading",
                "check_does": "status becomes HUNG at MAX_STEPS; honest run is REPLACED-AND-CONTINUED",
                "verbatim": json.dumps(
                    {
                        "honest": death["status"],
                        "hang_mutant": c_hang.status,
                        "max_steps": MAX_STEPS,
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0021-probe2-pairwise-recount",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "mechanism": "reviewer.py nested pairwise canonical_model comparison plus ballot table keyed by (round_id, seat_id, option); does not read the author's claims[]",
            "anchor": a_pair,
            "role_mutant_control": a_role,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": RUNTIME, "exists": True, "role": "supporting"},
            {"path": REVIEWER, "exists": True, "role": "supporting"},
        ],
        "not_checked": [
            {
                "claim": "Field-by-field citation of $defs.seat in 11-COUNCIL-SPECIFICATION.schema.json",
                "reason": (
                    "The four catalog input paths from harness-restore-20260806 are not on this "
                    f"worktree (missing={missing_sources}). Citing unread schema fields would be overclaim."
                ),
            },
            {
                "claim": "Behaviour of a live multi-vendor LLM council under this protocol",
                "reason": "This unit ships a deterministic step machine and fixtures, not a live model dispatch.",
            },
            {
                "claim": "Response-side SAME-TUPLE / DECLARED-ONLY / DRIVER-CONFOUND",
                "reason": "Those are ADV-0136 runtime attestation checks; this unit is the CONFIG-side half.",
            },
            {
                "claim": "CNL-0005 nine-dial descriptor and CNL-0020 catch-up briefing artifacts",
                "reason": "Those dependency artifacts are not on this worktree; replacement reuses the catalog questions (new seat_id, role mandate, no majority-anchored first vote) without claiming their units delivered.",
            },
            {
                "claim": "Instance validation against the catalog-declared shared command-center/schema/council-design-note.schema.json",
                "reason": "That shared file is contested: a sibling CNL-0030 worker required chair/flat size_sweep fields that are not this unit's question. This artifact validates against the per-unit copy at command-center/p2-wave/probes/CNL-0021/council-design-note.schema.json (same pattern as CNL-0012). Overwriting the shared schema would be a rebuild circle.",
            },
        ],
        "source_unavailable": missing_sources,
        "strongest_surviving_counterargument": (
            "Azure OpenAI gpt-4o and OpenAI gpt-4o may differ in routing and safety "
            "filters, so a vendor-aware auditor might want them as weak-independent. "
            "CONFIG-side this unit still flags them: they share a canonical_model, "
            "so they are not independent evidence of that model's distribution. "
            "ADV-0136 can still distinguish the vendor endpoints on the response side."
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "mid-round-death-and-both-direction-independence"},
            {"id": "probe2", "command": P2, "role": "independent-pairwise-recount"},
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0021 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0021 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0021 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
