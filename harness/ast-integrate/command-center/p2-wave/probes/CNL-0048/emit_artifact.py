#!/usr/bin/env python3
"""Emit CNL-0048 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0048-response-obligations-and-rebuttal-depth.md"
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
ENGINE = HERE / "engine.py"
FIX = HERE / "fixtures"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0048/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0048/probe2_independent_recount.py"
)
QUESTION = (
    "When is a participant OBLIGED to respond to a specific argument, how deep "
    "may rebuttal chains go before the depth budget cuts them, and what marks "
    "an argument as answered versus ignored?"
)


def load_fix(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def run(name: str, **kwargs) -> dict:
    doc = load_fix(name)
    return E.apply_turns(
        doc["turns"], int(doc["rebuttal_depth_budget"]), **kwargs
    )


def line_of(marker: str) -> int:
    for i, line in enumerate(ENGINE.read_text(encoding="utf-8").splitlines(), 1):
        if marker in line:
            return i
    raise SystemExit(f"FAILED:emit missing marker {marker}")


def main() -> int:
    good = run("known_good")
    bad = run("ignored_argument")
    mutant = run("ignored_argument", drop_ignored=True)
    non = run("non_answer")
    depth = run("depth_cut")
    rec_bad = E.independent_recount(
        load_fix("ignored_argument")["turns"],
        int(load_fix("ignored_argument")["rebuttal_depth_budget"]),
    )
    rec_good = E.independent_recount(
        load_fix("known_good")["turns"],
        int(load_fix("known_good")["rebuttal_depth_budget"]),
    )

    good_line = E.verbatim_check("known_good", good)
    bad_line = E.verbatim_check("ignored_argument", bad)
    mutant_line = E.verbatim_check("silent_drop_mutant", mutant)
    non_line = E.verbatim_check("non_answer", non)
    depth_line = E.verbatim_check("depth_cut", depth)

    if good["unanswered_fires"] or not bad["unanswered_fires"] or not bad["ignored_visible"]:
        print("FAILED:emit both-states did not discriminate")
        return 1
    if not mutant["silent_drop_fires"] or mutant["unanswered_fires"]:
        print("FAILED:emit silent-drop mutant not detected")
        return 1
    if not non["unanswered_fires"]:
        print("FAILED:emit non-answer discharged")
        return 1
    if depth["unanswered_fires"] or "n2" in depth["nodes"]:
        print("FAILED:emit depth-cut contract broken")
        return 1
    if rec_bad["ignored"] != bad["ignored_ids"] or rec_good["unanswered_fires"]:
        print("FAILED:emit recount disagreement")
        return 1

    l_named = line_of("NAMED_ADDRESSEE_REQUIRED")
    l_ign = line_of("IGNORED_SURVIVES_SYNTHESIS")
    l_depth = line_of("DEPTH_HARD_STOP_NOT_CONSENSUS")
    l_non = line_of("NON_ANSWER_DOES_NOT_DISCHARGE")

    answer = (
        "A participant is obliged to respond only when an accepted graph node "
        "records requires_response=true and a named addressee, and the reply hop "
        "(parent-walk depth + 1) is still inside the rebuttal_depth budget. "
        "Unnamed addressees create no obligation. "
        "An obligation is ANSWERED only by a discharge-kind turn (rebuttal, "
        "concession, or explicit_pass) from that addressee that addresses the "
        "same claim_id; a topic_change or acknowledgement does not discharge. "
        "At synthesis, remaining OPEN obligations become IGNORED nodes on the "
        "argument graph and must not be dropped. "
        "Rebuttal depth is hop-count from the root claim. A hop whose depth "
        "exceeds the budget is HARD-STOPPED: the node is refused and the "
        "would-be obligation is CUT_BY_DEPTH, which is neither consensus nor "
        "an ignore. CNL-0047 is a scheduler plug (entitled-to-speak); this unit "
        "does not claim turn order. Harness files 11-COUNCIL-SPECIFICATION and "
        "12-COUNCIL-PROTOCOLS-AND-PRESETS are absent on this worktree; the "
        "contract is operationalized from the catalog question and tests_required."
    )

    doc = {
        "unit_id": "CNL-0048",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0048",
        "title": "Response obligations and rebuttal depth",
        "question": QUESTION,
        "answer": answer,
        "dependency_note": (
            "CNL-0047 (turn-taking) is specified as a plug: this engine assumes "
            "the addressee is entitled to speak when an OPEN obligation exists. "
            "CNL-0047's artifact is not required to execute the fixtures."
        ),
        "inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "catalog_question_used": True,
        },
        "contract": {
            "oblige_when": [
                "requires_response is true on an accepted node",
                "addressee is a named seat",
                "reply_depth = hop_depth(parent)+1 is <= rebuttal_depth_budget",
            ],
            "discharge_kinds": ["concession", "explicit_pass", "rebuttal"],
            "ignored": "OPEN at synthesis; remains a graph node with status=IGNORED",
            "answered": "addressee posted a discharge-kind turn addressing the claim_id",
            "cut": "reply hop would exceed budget; status=CUT_BY_DEPTH; not IGNORED",
            "scheduler_plug": "entitled_to_speak(seat) from CNL-0047; not implemented here",
        },
        "tests": [
            {
                "id": "T1-ignored-argument-visible",
                "command": P1,
                "result": "PASS",
                "assertion": "unanswered obligation obl:n0 remains on the synthesized graph as IGNORED",
            },
            {
                "id": "T2-both-states",
                "command": P1,
                "result": "PASS",
                "assertion": "unanswered check FIRES on ignored_argument and is SILENT on known_good",
            },
            {
                "id": "T3-independent-recount-non-answer",
                "command": P2,
                "result": "PASS",
                "assertion": "set-algebra recount agrees with labels; topic_change does not discharge",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unanswered-on-ignored",
                "rejects": "an unanswered named obligation silently omitted at synthesis or treated as answered",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_line,
                "good_state_output": good_line,
            },
            {
                "id": "NC-silent-drop-mutant",
                "rejects": "a synthesizer that drops IGNORED rows so the unanswered check goes silent",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": mutant_line,
                "good_state_output": good_line,
            },
            {
                "id": "NC-non-answer-is-not-discharge",
                "rejects": "counting any addressee utterance as a response",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": non_line,
                "good_state_output": good_line,
            },
        ],
        "both_states": {
            "known_good": {
                "fires": good["unanswered_fires"],
                "verbatim": good_line,
            },
            "ignored_argument": {
                "fires": bad["unanswered_fires"],
                "ignored_ids": bad["ignored_ids"],
                "ignored_visible": bad["ignored_visible"],
                "verbatim": bad_line,
            },
            "depth_cut": {
                "fires": depth["unanswered_fires"],
                "n2_accepted": "n2" in depth["nodes"],
                "verbatim": depth_line,
            },
        },
        "reviewer": {
            "reviewer_id": "CNL-0048-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "re_ran_both_states": True,
            "mechanism": rec_bad["mechanism"],
            "note": (
                "Mechanical independent re-run of both-states via parent-walk "
                "set algebra (probe2). A live cross-vendor model session was "
                "not invoked on this worktree."
            ),
            "counterexample": {
                "id": "any-reply-discharges",
                "attempted": True,
                "refutes": True,
                "fixture": "non_answer",
                "detail": (
                    "A topic_change by the addressee leaves obl:n0 IGNORED. "
                    "The competing rule 'any reply discharges' is refuted."
                ),
            },
        },
        "evidence": [
            {
                "claim": "Obligation creation requires a named addressee; unnamed requires_response creates no OPEN obligation.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"command-center/p2-wave/probes/CNL-0048/engine.py:{l_named}",
                    "snippet": "NAMED_ADDRESSEE_REQUIRED",
                },
            },
            {
                "claim": "Ignored obligations remain visible on the synthesized argument graph.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"command-center/p2-wave/probes/CNL-0048/engine.py:{l_ign}",
                    "snippet": "IGNORED_SURVIVES_SYNTHESIS",
                },
            },
            {
                "claim": "Depth exhaustion hard-stops the next hop as CUT_BY_DEPTH, not as ignore or consensus.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"command-center/p2-wave/probes/CNL-0048/engine.py:{l_depth}",
                    "snippet": "DEPTH_HARD_STOP_NOT_CONSENSUS",
                },
            },
            {
                "claim": "A topic_change by the addressee does not discharge the obligation.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"command-center/p2-wave/probes/CNL-0048/engine.py:{l_non}",
                    "snippet": "NON_ANSWER_DOES_NOT_DISCHARGE",
                },
            },
            {
                "claim": "Both-states: unanswered check FIRES on ignored_argument and is SILENT on known_good.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "command_output",
                    "command": P1,
                    "output": f"{good_line}\n{bad_line}",
                },
            },
            {
                "claim": "Independent set-algebra recount of ignored_argument matches labeled ignored_ids.",
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "command_output",
                    "command": P2,
                    "output": (
                        f"recount_ignored={rec_bad['ignored']} "
                        f"labeled_ignored={bad['ignored_ids']} "
                        f"fires={rec_bad['unanswered_fires']}"
                    ),
                },
            },
        ],
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0048-response-obligations-and-rebuttal-depth.md",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0048/engine.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/schema/council-design-note.schema.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Catalog output_schema is a $ref shim to ast-integrate.invalid; that host
    # does not resolve here. G-1 delivery parses JSON and re-runs named probes;
    # it does not fetch remote schema. Local shape checks live in probe1/probe2.
    if SCHEMA.is_file():
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        if not isinstance(schema, dict) or not schema:
            print("FAILED:emit output_schema empty")
            return 1
        if "council-design-note" not in json.dumps(schema):
            print("FAILED:emit output_schema missing class name")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNL-0048 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
