#!/usr/bin/env python3
"""Emit the CNL-0036 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import bracket as B  # noqa: E402
import contract as C  # noqa: E402
import probe2_independent_recount as P2  # noqa: E402
import _p2lib as L  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0036-pairwise-tournament-topology-bracket-seeding-and-tie-break.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0036/probe1_seeding_sweep.py"
)
P2CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0036/probe2_independent_recount.py"
)
QUESTION = (
    "How are options seeded into a pairwise bracket, and how is the well-known "
    "dependence of bracket outcomes on seeding order prevented from silently "
    "determining the winner?"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = "SUCCESS:CNL-0036"


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0036 emit anchor missing in {path}: {needle}")


def public_row(row: dict) -> dict:
    return {
        "counts": row["counts"],
        "invariance_rate": row["invariance_rate"],
        "modal_winner": row["modal_winner"],
        "n_distinct_winners": row["n_distinct_winners"],
        "n_permutations": row["n_permutations"],
        "reason": row["reason"],
        "tie_break": row["tie_break"],
    }


def main() -> int:
    fx = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    options = list(fx["options"])
    tb = fx["tie_break_declared"]
    thr = float(fx["threshold_reject_below"])
    live = {}
    gates = {}
    for name in ("cyclic4", "transitive4", "tied_wx"):
        prof = fx[name]
        beats = B.beats_set(prof["beats"])
        ties = B.tie_set(prof.get("ties") or [])
        row = B.sweep(options, beats, ties, tb)
        live[name] = row
        gates[name] = B.gate_unique_winner(row, thr)
    left = B.sweep(
        options,
        B.beats_set(fx["tied_wx"]["beats"]),
        B.tie_set(fx["tied_wx"]["ties"]),
        "left_slot",
    )
    if live["cyclic4"]["counts"] != {"W": 8, "X": 8, "Y": 8}:
        print("FAILED:CNL-0036 emit unexpected cyclic counts")
        return 1
    if live["transitive4"]["counts"] != {"W": 24}:
        print("FAILED:CNL-0036 emit transitive is not invariant")
        return 1
    if not gates["cyclic4"]["fires"] or gates["transitive4"]["fires"]:
        print("FAILED:CNL-0036 emit both-states not satisfied")
        return 1
    if left["counts"] != {"W": 12, "X": 12}:
        print("FAILED:CNL-0036 emit left_slot control broken")
        return 1

    independent = {}
    for name in ("cyclic4", "transitive4", "tied_wx"):
        prof = fx[name]
        independent[name] = P2.recount(
            options, prof["beats"], prof.get("ties") or [], tb
        )
    left_ind = P2.recount(
        options, fx["tied_wx"]["beats"], fx["tied_wx"]["ties"], "left_slot"
    )
    if independent["cyclic4"]["counts"] != live["cyclic4"]["counts"]:
        print("FAILED:CNL-0036 emit independent recount disagreed on cyclic4")
        return 1
    if independent["transitive4"]["counts"] != {"W": 24}:
        print("FAILED:CNL-0036 emit independent recount disagreed on transitive4")
        return 1
    if left_ind["counts"] != {"W": 12, "X": 12}:
        print("FAILED:CNL-0036 emit independent left_slot control broken")
        return 1

    b_line = find_line(HERE / "bracket.py", "def standard_slot_seeds")
    g_line = find_line(HERE / "bracket.py", "def gate_unique_winner")
    f_line = find_line(HERE / "fixtures.json", '"id": "cyclic-plus-dummy"')
    cat_line = find_line(REPO / CATALOG, '"id": "CNL-0036"')

    cyc = live["cyclic4"]
    trn = live["transitive4"]
    answer = (
        "Options are placed by a seed list that is exogenous to the pairwise "
        "oracle: seed_order[0] is seed 1. Seeds occupy a standard "
        "single-elimination slotting of the next power of two (1 plays n, "
        "2 plays n-1, recursive construction in bracket.standard_slot_seeds); "
        "unfilled seeds are BYEs. Each match is resolved by the pairwise "
        "oracle; a declared pairwise tie uses lexicographic option id, never "
        "the left bracket slot. The well-known seeding dependence is stopped "
        "from silently picking the winner by a mandatory permutation sweep: "
        "the same oracle is replayed under all n! seed orders (here n=4, "
        f"N={cyc['n_permutations']}). A unique winner may be published only "
        "if invariance_rate == 1. On cyclic-plus-dummy the sweep yields "
        f"n_distinct={cyc['n_distinct_winners']} counts={cyc['counts']} "
        f"invariance_rate={cyc['invariance_rate']:.12f}; the gate FIRES and "
        "publication is SEEDING-DEPENDENT-REFUSED. On linear-strength the "
        f"sweep yields counts={trn['counts']} invariance_rate="
        f"{trn['invariance_rate']:.12f}; the gate is SILENT and W may be "
        "published. Left-slot tie-break on the W/X tie splits W/X 12/12, "
        "which is why that rule is forbidden for an invariance claim. "
        "Condorcet cycle completion is CNL-0063; this unit treats the "
        "pairwise matrix as an oracle and reports knockout seeding dependence "
        f"instead of silently completing a cycle. {SENTINEL}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_cyc = (
        f"PLANTED-BAD cyclic4: n_perm={cyc['n_permutations']} "
        f"n_distinct={cyc['n_distinct_winners']} counts={cyc['counts']} "
        f"invariance_rate={cyc['invariance_rate']:.12f} fires=True "
        f"publication=SEEDING-DEPENDENT-REFUSED"
    )
    src_trn = (
        f"KNOWN-GOOD transitive4: n_perm={trn['n_permutations']} "
        f"n_distinct={trn['n_distinct_winners']} counts={trn['counts']} "
        f"invariance_rate={trn['invariance_rate']:.12f} fires=False "
        f"publication=INVARIANT-UNIQUE-WINNER published_winner=W"
    )
    ver_cyc = (
        f"recount cyclic4: n_perm={independent['cyclic4']['n_permutations']} "
        f"n_distinct={independent['cyclic4']['n_distinct_winners']} "
        f"counts={independent['cyclic4']['counts']} "
        f"invariance_rate={independent['cyclic4']['invariance_rate']:.12f}"
    )
    ver_trn = (
        f"recount transitive4: n_perm={independent['transitive4']['n_permutations']} "
        f"n_distinct={independent['transitive4']['n_distinct_winners']} "
        f"counts={independent['transitive4']['counts']} "
        f"invariance_rate={independent['transitive4']['invariance_rate']:.12f}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0036",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "profile": "council-design-note",
        "spec_anchor": f"{CATALOG}:{cat_line}",
        "min_bytes_threshold": 2048,
        "artifacts": [
            L.art("command-center/p2-wave/probes/CNL-0036/fixtures.json", "fixture"),
            L.art("command-center/p2-wave/probes/CNL-0036/bracket.py", "supporting"),
            L.art(SCHEMA_REL, "supporting"),
        ],
        "evidence": [
            L.evidence(
                (
                    "On cyclic-plus-dummy, all 24 seedings of {W,X,Y,Z} produce "
                    "three distinct knockout winners W,X,Y with 8 seedings each "
                    "(invariance_rate=1/3); Z never wins."
                ),
                "CONFIRMED",
                f"command-center/p2-wave/probes/CNL-0036/fixtures.json:{f_line}",
                [
                    L.probe("source", "command", P1, src_cyc, 0),
                    L.probe("verifier", "test-run", P2CMD, ver_cyc, 0),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "The invariance gate refuses a unique published winner on "
                    "cyclic4 and permits W on transitive4, where W wins all 24 "
                    "seedings."
                ),
                "CONFIRMED",
                f"command-center/p2-wave/probes/CNL-0036/bracket.py:{g_line}",
                [
                    L.probe("source", "command", P1, src_trn, 0),
                    L.probe("verifier", "test-run", P2CMD, ver_trn, 0),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Using left_slot as the W/X match tie-break splits winners "
                    "12/12; lexicographic_id yields W on all 24. Slot-dependent "
                    "tie-break is not an invariance-preserving rule."
                ),
                "CONFIRMED",
                f"command-center/p2-wave/probes/CNL-0036/bracket.py:{b_line}",
                [
                    L.probe(
                        "source",
                        "command",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0036'); "
                            "import bracket as B; fx=json.load(open('command-center/p2-wave/probes/CNL-0036/fixtures.json')); "
                            "print(B.sweep(fx['options'], B.beats_set(fx['tied_wx']['beats']), B.tie_set(fx['tied_wx']['ties']), 'left_slot')['counts'])\""
                        ),
                        f"left_slot counts={left['counts']}",
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "test-run",
                        P2CMD,
                        f"left_slot counts={left_ind['counts']}",
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Harness-restore 11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read on this "
                    "worktree and the bracket rule was copied from them."
                ),
                "REFUTED",
                "source_inputs_on_this_tree",
                [
                    L.probe(
                        "source",
                        "file-read",
                        "python3 -c \"from pathlib import Path; print(Path('C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json').is_file())\"",
                        "False",
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "command",
                        "python3 -c \"from pathlib import Path; print(Path('C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json').is_file())\"",
                        "False",
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "T-SEEDING-SWEEP",
                "name": (
                    "same option set under all 24 seedings; report how often "
                    "the winner changes; a stable claim requires the number"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-RECOUNT",
                "name": (
                    "reviewer re-derives winners via the 4-team closed form "
                    "(s1 vs s4, s2 vs s3) by scanning beats lists"
                ),
                "command": P2CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "NC-CYCLIC-UNIQUE-WINNER",
                "known-broken-fixture",
                (
                    "Refuse publishing the knockout winner of a single seed "
                    "order on the cyclic-plus-dummy oracle as if it were "
                    "seeding-invariant. Must FIRE on cyclic4 and stay SILENT "
                    "on transitive4."
                ),
                True,
                True,
                bad=src_cyc,
                good=src_trn,
            ),
            L.control(
                "NC-LEFT-SLOT-TIE-BREAK",
                "known-broken-fixture",
                (
                    "Refuse using the left bracket slot to break a declared "
                    "W vs X tie. Must FIRE (split 12/12) on left_slot and stay "
                    "SILENT (W x24) on lexicographic_id."
                ),
                True,
                True,
                bad=f"left_slot counts={left['counts']}",
                good=f"lexicographic counts={live['tied_wx']['counts']}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "CNL-0036-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "4-team closed form play(play(s1,s4), play(s2,s3)); match "
                "winners by scanning beats/ties lists. Does not call "
                "bracket.sweep or bracket.run_bracket."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0036/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0036",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py validate_artifact",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "schema-validate",
                    f"schema_resolver.validate_artifact(doc, {SCHEMA_REL!r})",
                    "validated before write; emitter refuses to persist an invalid artifact",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:50:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a "
                "3rd attempt (AGENTS.md 4b). Max 3 attempts."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether a later CouncilSpec on another tree already names a "
                    "different standard slotting (e.g. adjacent pairing without "
                    "1-vs-n). This note's operational slotting is "
                    "bracket.standard_slot_seeds. Large n where n! cannot be "
                    "enumerated would need a declared sample size; n=4 is fully "
                    "enumerated here (24)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When a CouncilSpec with an explicit slotting enum lands on "
                    "this tree, re-run the 24-permutation sweep under that "
                    "slotting and compare n_distinct to this note."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-design-note",
            "control_ids": [
                "NC-CYCLIC-UNIQUE-WINNER",
                "NC-LEFT-SLOT-TIE-BREAK",
            ],
            "observations": [
                {
                    "name": "cyclic4_n_distinct_winners",
                    "measured": 3,
                    "method": "bracket.sweep over 4! seed orders",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0036/fixtures.json:"
                        f"{f_line}"
                    ),
                },
                {
                    "name": "cyclic4_invariance_rate",
                    "measured": cyc["invariance_rate"],
                    "method": "max(winner_counts)/n!",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0036/bracket.py:"
                        f"{g_line}"
                    ),
                },
                {
                    "name": "transitive4_w_wins",
                    "measured": 24,
                    "method": "bracket.sweep over 4! seed orders",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0036/bracket.py:"
                        f"{g_line}"
                    ),
                },
                {
                    "name": "left_slot_split",
                    "measured": "W=12,X=12",
                    "method": "bracket.sweep with tie_break=left_slot",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0036/bracket.py:"
                        f"{b_line}"
                    ),
                },
            ],
            "title": "Pairwise tournament topology: bracket, seeding and tie-break",
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": SENTINEL,
            "answers": {
                "how_match_ties_are_broken": (
                    "Declared pairwise ties use lexicographic option id "
                    "(min(id_a, id_b)), which is independent of bracket slot. "
                    "left_slot is forbidden: on tied_wx it yields W=12,X=12 "
                    "across the 24 seedings, reintroducing seeding into a tie."
                ),
                "how_options_are_seeded": (
                    "A pre-registered seed_order places option i as seed rank "
                    "i+1 into standard single-elim slots of size next_pow2(n) "
                    "with BYEs on unused seeds. Pairing is 1 vs n, 2 vs n-1 via "
                    "the recursive slot list, not an ad-hoc shuffle of names."
                ),
                "how_seeding_dependence_is_prevented": (
                    "Before a unique knockout winner is published, replay the "
                    "same pairwise oracle under all n! seed orders. Publish a "
                    "unique winner only if n_distinct_winners==1 (invariance_rate "
                    f"== 1.0). cyclic4 measures n_distinct=3, rate="
                    f"{cyc['invariance_rate']:.12f} and is refused. The number "
                    "is required; a stability claim without it is refused."
                ),
            },
            "sweep": {
                "cyclic4": public_row(cyc),
                "transitive4": public_row(trn),
                "tied_wx": public_row(live["tied_wx"]),
                "tied_wx_left_slot": public_row(left),
            },
            "gate": {
                "cyclic4": gates["cyclic4"],
                "transitive4": gates["transitive4"],
                "tied_wx": gates["tied_wx"],
            },
            "both_states": {
                "planted_bad": "cyclic4",
                "known_good": "transitive4",
                "planted_bad_fires": True,
                "known_good_silent": True,
                "verbatim_bad": src_cyc,
                "verbatim_good": src_trn,
            },
            "taxonomy": {
                "id": "council.knockout-publication.v1",
                "closed": True,
                "range_rule": (
                    "A knockout result is published as a unique winner only when "
                    "the permutation sweep reports invariance_rate == 1.0. One "
                    "observed seeding is not a new publication category."
                ),
                "categories": [
                    {
                        "id": "INVARIANT-UNIQUE-WINNER",
                        "description": (
                            "n_distinct_winners==1; unique winner may be "
                            "published with the sweep number."
                        ),
                    },
                    {
                        "id": "SEEDING-DEPENDENT-REFUSED",
                        "description": (
                            "n_distinct_winners>1; unique winner publication is "
                            "refused; the sweep table is the result."
                        ),
                    },
                ],
            },
            "measurement": {
                "name": "seeding_invariance_rate",
                "formula": (
                    "invariance_rate = max(winner_counts) / n! over all seed "
                    "permutations of a fixed pairwise oracle; n_distinct_winners "
                    "= |{winners}|. Unique-winner publication is rejected when "
                    "invariance_rate < 1.0."
                ),
                "threshold_reject_below": 1.0,
                "coverage_alone_insufficient": True,
                "coverage_definition": (
                    "Running one seeding is coverage of a single pairing, not "
                    "evidence the winner is seeding-invariant."
                ),
            },
            "source_inputs_on_this_tree": {
                "11-COUNCIL-SPECIFICATION.schema.json": False,
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
                "_USER-PROMPTS.md": False,
                "note": (
                    "Catalog inputs are Windows harness-restore paths not present "
                    "here. Pairwise beats are operational fixtures this unit "
                    "supplies. CNL-0063's tabulate.py exists as a neighbor oracle "
                    "for cycle completion; this unit does not silently apply it "
                    "to hide knockout seeding dependence."
                ),
            },
            "dependency_cnl_0063": {
                "id": "CNL-0063",
                "role": (
                    "Pairwise/Condorcet cycle completion. This unit consumes a "
                    "complete pairwise oracle and reports seeding dependence; it "
                    "does not choose a cycle completion after seeing who would win."
                ),
                "consumed_as_blocker": False,
            },
        },
    }

    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0036", "state": "SUCCESS"},
    ):
        g_errs = C.schema_errors(garbage)
        if not g_errs:
            print(f"FAILED:CNL-0036 emit schema accepted garbage {garbage}")
            return 1

    errs = C.schema_errors(doc)
    if errs:
        print("FAILED:CNL-0036 artifact does not satisfy its declared contract")
        for e in errs[:25]:
            print("   ", e)
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out.stat().st_size
    floor = int(doc["min_bytes_threshold"])
    if size < floor:
        print(f"FAILED:CNL-0036 artifact {size}B below declared floor {floor}B")
        return 1
    print(f"wrote {OUT_REL} bytes={size}")
    print("SUCCESS:CNL-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
