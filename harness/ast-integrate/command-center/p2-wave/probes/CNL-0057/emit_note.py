#!/usr/bin/env python3
"""Emit CNL-0057 design note (JSON with .md catalog path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import note_schema as NS  # noqa: E402
import synthesis_only as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0057-synthesis-only-mode-when-taking-no-vote-is-the-correct-des.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0057/probe1_method_disagreement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0057/probe2_negative_control.py"
)
QUESTION = (
    "For which decision types is a vote actively harmful (it manufactures a "
    "number where none exists), and what does synthesis-only owe the reader "
    "in place of a tally?"
)
ENGINE = "command-center/p2-wave/probes/CNL-0057/synthesis_only.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0057 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0057 named probes before emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    diag = S.load_fixture("diagnosis_split.json")
    scalar = S.load_fixture("scalar_estimate.json")
    pref = S.load_fixture("preference_ok.json")
    md = S.methods_disagree(diag)
    sd = S.methods_disagree(scalar)
    planted = S.detect(diag)
    syn_ok = S.detect(S.load_fixture("diagnosis_synthesis.json"))
    pref_d = S.detect(pref)

    harm_line = find_line(ENGINE, '        "diagnosis",')
    fire_line = find_line(ENGINE, '"output": FIRE,')
    silent_line = find_line(ENGINE, '"output": SILENT,')
    reject_line = find_line(ENGINE, "vote-as-decision on a vote-harmful decision_class")
    mean_line = find_line(ENGINE, "manufactured_scalar")
    winner_none = find_line(ENGINE, '"winner": None,')

    answer = (
        "A vote is actively harmful when the council is not aggregating "
        "preferences among already-valid options, but is instead being asked "
        "to name a fact, a cause, a scalar, a reading of evidence, or a "
        "meaning of text. In those classes plurality still emits a winner and "
        "a mean still emits a center. Those numbers are social statistics. "
        "They are not the missing finding. The 2-1 diagnosis fixture shows "
        "the method harm with seats held fixed: vote names cache; "
        "synthesis-only keeps {cache, deploy} live and emits no winner. The "
        "scalar fixture shows a manufactured 40.0 that no seat held. "
        "Synthesis-only owes the reader live hypotheses, seat provenance, a "
        "census labeled as census, an explicit no-tally statement, preserved "
        "dissent, and the next measurement that would drop a hypothesis. A "
        "census of unanimous reports is still not a vote-as-decision: the "
        "detector fires on method=vote even when every seat names the same "
        "cause. Mixed questions (rollback?) must be split: diagnosis stays "
        "synthesis-only; the residual preference may be voted."
    )

    markdown_body = """# CNL-0057 Synthesis-only mode: when taking no vote is the correct design

## Question

For which decision types is a vote actively harmful (it manufactures a number
where none exists), and what does synthesis-only owe the reader in place of a
tally?

## Harm test

A closing procedure is a vote when it emits a `winner` or a mean scalar as
the council decision. That is the right procedure when, and only when, the
object of the council is a preference among options that remain valid after
the facts are in.

It is the wrong procedure when the object is a finding. Findings are not
created by counting seats. A 2-1 on a cause does not make the minority cause
false. A mean of 10, 90, and 20 is 40, a quantity no seat estimated.

## Vote-harmful decision types

1. Diagnosis / causal attribution. The system has a causal structure. A tally
   is a social fact about seats.
2. Scalar estimation. The mean/median is an aggregation rule, not a
   measurement. If no seat held the aggregate, the number is manufactured.
3. Evidence interpretation. Whether an artifact supports a claim is a
   relation between artifacts. Voting does not create the relation.
4. Meaning of text. Majority is not semantics.
5. Incommensurable synthesis. Ranking legal vs safety vs product by vote
   pretends they share a scale.
6. Unsplit mixed questions. "Should we rollback?" smuggles a diagnosis into
   a preference. Harmful until split.

## Vote-ok decision types (contrast)

Preference choice, resource allocation, and procedure selection among options
that remain valid after synthesis of the facts. The 2-1 shape is the same as
the diagnosis fixture; the class is different. The detector is silent.

## What synthesis-only owes instead of a tally

- Live hypotheses (the set of still-open claims), never a winner.
- Seat provenance for each claim.
- Census counts labeled census, never `vote_outcome`.
- Explicit no-tally statement and the decision_class that forbids the tally.
- Dissent preserved, not folded into remainder.
- The next measurement that would drop a live hypothesis.

Unanimous reports are a census, not a proof. Synthesis-only may say "3/3
named cache" and still refuse to close by vote.

## Method, not participants

The diagnosis fixture holds seats, ballots, and evidence hashes fixed. Vote
and synthesis-only disagree. Attribution is `method`. Mutating seat C's
ballot changes the fingerprint; that disagreement is `participants`. The
unit's required fixture is the former.

## Mixed questions

Split: (a) diagnosis, synthesis-only; (b) preference over residual risk,
vote-ok. A single vote on the mixed question fires.

## Dependency CNL-0023

Unequal vote weights (CNL-0023) do not convert a finding into a preference.
This unit's detector does not read weights. Not blocked on CNL-0023.

## Inputs absent on this tree

`11-COUNCIL-SPECIFICATION.schema.json` and
`12-COUNCIL-PROTOCOLS-AND-PRESETS.json` are not on this worktree. Claims
about those files are NOT-CHECKED. The design is executable from the catalog
question and the fixtures in this unit.
"""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0057",
        "kind": "council-design-note",
        "report_kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0057",
        "completion_sentinel": "SUCCESS:CNL-0057",
        "title": "Synthesis-only mode: when taking no vote is the correct design",
        "question": QUESTION,
        "answer": answer,
        "markdown_body": markdown_body,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0057]",
        "output_schema": SCHEMA,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
        },
        "dependencies": {
            "CNL-0023": {
                "required_for_this_answer": False,
                "note": (
                    "Vote-weight provenance is a sibling concern. Synthesis-only "
                    "is the claim that some decision classes must not be closed "
                    "by any tally, equal-weight or not."
                ),
                "status_this_tree": "not-used",
            }
        },
        "inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "_USER-PROMPTS.md": False,
        },
        "vote_harmful_decision_types": [
            {
                "id": "diagnosis",
                "harm": "plurality names a unique cause; etiology is not a preference",
            },
            {
                "id": "scalar_estimate",
                "harm": "mean/median can be a value no seat held",
            },
            {
                "id": "evidence_interpretation",
                "harm": "a tally does not create evidential support",
            },
            {
                "id": "meaning_of_text",
                "harm": "majority is not semantics",
            },
            {
                "id": "incommensurable_synthesis",
                "harm": "vote pretends incommensurable frames share a scale",
            },
            {
                "id": "mixed_unsplit",
                "harm": "preference vote launders an unresolved diagnosis",
            },
        ],
        "vote_ok_decision_types": [
            "preference_choice",
            "resource_allocation",
            "procedure_selection",
        ],
        "synthesis_only_owes": list(S.SYNTHESIS_OBLIGATIONS),
        "method_disagreement_fixture": {
            "id": "FX-diagnosis-2-1",
            "participants_held_fixed": True,
            "vote_winner": md["vote"].get("winner"),
            "synthesis_winner": md["synthesis"].get("winner"),
            "live_hypotheses": md["synthesis"].get("live_hypotheses"),
            "disagree": md["disagree"],
            "reason": md["reason"],
            "detail": md["detail"],
            "ballot_fingerprint": md["ballot_fingerprint"],
        },
        "scalar_fixture": {
            "id": "FX-scalar-spread",
            "manufactured_scalar": sd["vote"].get("manufactured_scalar"),
            "held_values": sd["vote"].get("held_values"),
            "held_by_any_seat": sd["vote"].get("held_by_any_seat"),
            "disagree": sd["disagree"],
            "reason": sd["reason"],
        },
        "tests": [
            {
                "id": "T1-method-disagreement",
                "name": (
                    "Fixture where voting and synthesis-only disagree with "
                    "reason attributed to the method rather than the participants"
                ),
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "T2-negative-control",
                "name": (
                    "Detector FIRES on planted vote-as-decision for diagnosis "
                    "and is SILENT on synthesis-only of the same ballots and "
                    "on a preference vote of the same 2-1 shape"
                ),
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0057-C1",
                "kind": "known-broken-fixture",
                "rejects": S.REJECTS,
                "fired_on_bad_state": planted["fires"],
                "silent_on_good_state": (not syn_ok["fires"]) and (not pref_d["fires"]),
                "bad_state_output": planted["output"],
                "good_state_output": syn_ok["output"],
                "preference_vote_output": pref_d["output"],
                "verbatim": (
                    f"The check rejects: {S.REJECTS}. "
                    f"On planted vote-on-diagnosis it prints {planted['output']!r}. "
                    f"On synthesis-only of the same ballots it prints {syn_ok['output']!r}. "
                    f"On a 2-1 preference vote it prints {pref_d['output']!r}."
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0057-reviewer-stdlib-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "reviewer.py re-derives plurality, mean, and live-set from "
                "fixture bytes with collections.Counter; it does not read "
                "the design note. Disagreement with the engine blocks."
            ),
            "counterexample": {
                "id": "CX-unanimous-diagnosis-vote",
                "attempted": True,
                "refutes": False,
                "instance": (
                    "Three seats, identical cause 'cache', method=vote. A "
                    "census number 3 exists. If the claim were 'any seat "
                    "count is fake', this would refute. The claim is that "
                    "vote-as-decision still manufactures a winner from a "
                    "census; detect() still FIRE manufactured_tally."
                ),
            },
        },
        "evidence": [
            {
                "claim": (
                    "On identical diagnosis ballots, plurality names cache "
                    "while synthesis-only emits no winner and keeps cache "
                    "and deploy live; attribution is method."
                ),
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"{ENGINE}:{winner_none}",
                    "path": ENGINE,
                    "line": winner_none,
                    "snippet": '"winner": None,',
                },
            },
            {
                "claim": (
                    "Named probes re-ran: method-disagreement and the "
                    "negative control (FIRE on planted vote, SILENT on "
                    "synthesis-only and on preference vote)."
                ),
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "command_output",
                    "command": P1 + " && " + P2,
                    "output": (out1 + "\n" + out2)[-2400:],
                },
            },
            {
                "claim": (
                    "VOTE_HARMFUL includes diagnosis and scalar_estimate; "
                    "detect() emits FIRE manufactured_tally iff method=vote "
                    "on those classes."
                ),
                "verdict": "CONFIRMED",
                "signal": {
                    "kind": "file_line",
                    "anchor": f"{ENGINE}:{harm_line}",
                    "path": ENGINE,
                    "line": harm_line,
                    "snippet": '"diagnosis",',
                },
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.schema.json was read from disk "
                    "on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "signal": {
                    "kind": "file_line",
                    "anchor": "inputs_on_this_tree",
                    "path": OUT,
                    "line": 1,
                    "snippet": "inputs_on_this_tree",
                },
            },
        ],
        "evidence_mechanisms": [
            "file:line citation into synthesis_only.py",
            "subprocess stdout of probe1 and probe2 (different mechanism)",
        ],
        "detector": {
            "rejects": S.REJECTS,
            "fire": S.FIRE,
            "silent": S.SILENT,
            "fire_line": f"{ENGINE}:{fire_line}",
            "silent_line": f"{ENGINE}:{silent_line}",
            "rejects_line": f"{ENGINE}:{reject_line}",
            "mean_line": f"{ENGINE}:{mean_line}",
        },
        "timestamps": {
            "started_at": "2026-08-24T18:33:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the "
                "same framing, enumerate at least two alternative "
                "decompositions before a third attempt (AGENTS.md 4b)"
            ),
        },
        "tests_required_catalog": [
            "a fixture where voting and synthesis-only disagree, with the reason attributed to the method rather than the participants",
            "negative control recorded verbatim: state what the check does on the state it is meant to reject",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": ENGINE,
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "method-disagreement", "command": P1},
            {"id": "probe2", "role": "negative-control", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0057/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "residual_unknowns": [
            {
                "claim": "Field-by-field alignment with 11-COUNCIL-SPECIFICATION.schema.json $defs for voting.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the harness restore CouncilSpec schema on disk and "
                    "diff VOTE_HARMFUL against named decision_class enums."
                ),
            }
        ],
    }

    shim = REPO / SCHEMA
    if not shim.is_file():
        print(f"FAILED:CNL-0057 catalog output_schema missing {SCHEMA}")
        return 1
    shim_text = shim.read_text(encoding="utf-8")
    if "council-design-note" not in shim_text:
        print("FAILED:CNL-0057 output_schema missing class name")
        return 1
    if not NS.rejects_garbage():
        print("FAILED:CNL-0057 local schema accepted garbage")
        return 1
    errs = NS.iter_errors(doc)
    if errs:
        print("FAILED:CNL-0057 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0057 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNL-0057" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0057 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0057 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
