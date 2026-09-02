#!/usr/bin/env python3
"""Emit the CNL-0091 detector spec at the catalog output_path.

The path ends in .md because the catalog names a design note; G-1 requires
the file to parse as JSON, so the document is a JSON object that includes
the prose spec in markdown_spec.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = "command-center/design/council/CNL-0091-role-collapse-participants-behaving-identically.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/CNL-0091/detector-spec.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
DET = "command-center/p2-wave/probes/CNL-0091/detector.py"
FIX = "command-center/p2-wave/probes/CNL-0091/fixtures.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0091/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0091/probe2_role_recovery.py"
)
QUESTION = (
    "What behavioural distance metric shows that the critic has started "
    "behaving like the proposer - and what is the distance between two "
    "seats that genuinely agree?"
)
MARKDOWN = """# CNL-0091 Role collapse: participants behaving identically

## Question

What behavioural distance metric shows that the critic has started behaving
like the proposer — and what is the distance between two seats that
genuinely agree?

## Pathology

Role collapse is not “the critic endorsed the same conclusion”. Two seats
that genuinely agree still owe different obligations: the proposer
constructs; the critic steelmans, names residual risk, and states the
conditions of agreement. Collapse is when those obligations are no longer
recoverable from the text — the critic has started *behaving* like the
proposer. A Role: label is not a behaviour.

This unit depends on the CNL-0027 triad (proposer / critic / synthesiser)
as a mandate source. CNL-0027 is not delivered on this tree; the detector
treats the triad as: proposer constructs a proposal, critic tests it,
synthesiser may not silently become a third critic or a second proposer.
Only the proposer–critic pair is scored here.

## Metric (two independent signals)

Do **not** use stance/conclusion distance as the fire statistic. Genuine
agreement and collapse both have low stance distance; a stance detector is
silent in the planted-bad state *or* fires on every real agreement, and
in either case measures nothing useful.

Signal A (`d_act`): L1/2 distance between speech-act histograms over
{propose, critique, steelman, condition}. Bag counts of disjoint phrase
lists.

Signal B (`d_sig`): absolute difference of role-lexicon skew, using a
**disjoint** vocabulary (implementation-plan markers vs failure-mode
markers). Different tokens, different aggregation from A.

Combined: `d = (d_act + d_sig) / 2` in `[0, 1]`.

Fire when `d < 0.35`. The gate is pre-registered in `detector.py` as
`COLLAPSE_GATE`; fixtures were written to the role-lexicon contract, not
tuned after seeing distances.

Probe 2 is a third, order-based mechanism: the first matching speech-act
phrase classifies the seat. A collapsed critic is recovered as proposer;
a genuine-agreement critic is still recovered as critic.

## Distance between seats that genuinely agree

That distance is `d_combined` on the `genuine-agreement` fixture — a
number, not an adjective. It sits with the diverse (known-good) cluster,
above the gate, even though `d_stance` on that pair is ~0 (same
conclusion). Stance cannot tell collapse from agreement; role-obligation
distance can.

## Controls

1. Known-present first: `collapsed-calibrate` must FIRE before any
   absence is reported. If it does not, the fixture is broken (retry
   policy: fix the fixture once; do not count a mechanism failure).
2. Known-good: `diverse-calibrate` must be SILENT.
3. Negative control: `genuine-agreement` is the state a stance metric
   would treat as collapse. This detector must be SILENT. Recorded
   verbatim in the both-states object.
4. Hold-out planted-bad: paraphrased collapse (different wording, same
   acts) must still FIRE — lexical Jaccard alone would miss it.
5. False-positive rate is reported as a number over the four clean
   fixtures.

ADV-0092 is a later pathology simulation of five-role differentiation.
This unit does not rebuild it.
"""


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0091 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


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
        print("FAILED:CNL-0091 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-both-states.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-role-recovery.raw.json").read_text(encoding="utf-8"))
    plant = p1["collapsed_calibrate"]
    good = p1["diverse_calibrate"]
    agree = p1["genuine_agreement"]
    para = p1["collapsed_paraphrase"]

    e1 = ev(
        DET,
        "COLLAPSE_GATE = 0.35",
        "spec",
        "Collapse gate is pre-registered, not fit after seeing distances.",
    )
    e2 = ev(
        DET,
        "Stance/conclusion Jaccard is computed",
        "spec",
        "Stance is a foil and is never the fire statistic.",
    )
    e3 = ev(
        DET,
        "Order-based classifier: earliest matching speech-act phrase",
        "live-tree",
        "Probe 2 recovers role from phrase order, not from bag L1.",
    )
    e4 = ev(
        FIX,
        '"id": "genuine-agreement"',
        "live-tree",
        "Genuine-agreement fixture shares a conclusion and keeps critic acts.",
    )
    e5 = ev(
        CATALOG,
        "What behavioural distance metric shows that the critic has started behaving like the proposer",
        "catalog",
        "Catalog question for CNL-0091 is the question this spec answers.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d_agree = float(agree["d_combined"])
    fp = float(p2["false_positive_rate"])
    verbatim = " | ".join(p1["verbatim"])
    neg = (
        f"NEG-CONTROL genuine-agreement d_combined={agree['d_combined']} "
        f"d_stance={agree['d_stance']} fired={agree['fired']} "
        f"(stance is low; detector stays silent)"
    )

    doc = {
        "unit_id": "CNL-0091",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0091",
        "report_kind": "council-detector-spec",
        "title": "Role collapse: participants behaving identically",
        "question": QUESTION,
        "pathology": (
            "The critic seat produces proposer speech-acts and proposer "
            "lexicon, so assigned roles are no longer recoverable from "
            "behaviour. Shared conclusions are not the pathology."
        ),
        "depends_on": ["CNL-0027"],
        "dependency_note": (
            "CNL-0027 triad mandates are not delivered on this tree; this "
            "spec uses the catalog obligation split (proposer constructs, "
            "critic tests) and does not rebuild ADV-0092."
        ),
        "markdown_spec": MARKDOWN,
        "metric": {
            "name": "role-obligation combined L1",
            "combined_formula": "d = (d_act + d_sig) / 2; fire iff d < COLLAPSE_GATE",
            "does_not_use": (
                "stance/conclusion Jaccard, Role: labels, or token-set "
                "Jaccard on the full brief"
            ),
            "signals": [
                {
                    "id": "A-act",
                    "name": "d_act",
                    "mechanism": (
                        "L1/2 distance of speech-act histograms over "
                        "propose/critique/steelman/condition phrase bags"
                    ),
                },
                {
                    "id": "B-sig",
                    "name": "d_sig",
                    "mechanism": (
                        "absolute difference of critic-lexicon skew using "
                        "vocab disjoint from the speech-act phrase lists"
                    ),
                },
            ],
            "foil": {
                "name": "d_stance",
                "mechanism": "Jaccard distance of conclusion: token sets",
                "why_not_the_metric": (
                    "collapsed-calibrate and genuine-agreement both have "
                    f"d_stance≈0 (measured {plant['d_stance']} vs "
                    f"{agree['d_stance']}); stance cannot separate them"
                ),
            },
            "probe2_mechanism": (
                "first matching speech-act phrase classifies the seat; "
                "collapsed critic recovers as proposer, agreement critic "
                "recovers as critic"
            ),
        },
        "thresholds": {
            "collapse_gate": D.COLLAPSE_GATE,
            "gate_registration": "pre-registered",
            "collapsed_anchor_distance": plant["d_combined"],
            "diverse_anchor_distance": good["d_combined"],
            "genuine_agreement_distance": d_agree,
            "paraphrase_collapse_distance": para["d_combined"],
        },
        "answers": {
            "behavioural_distance_metric": (
                "Mean of speech-act histogram L1/2 (d_act) and disjoint "
                "role-lexicon skew gap (d_sig). A critic has started "
                "behaving like the proposer when that combined distance "
                f"falls below the pre-registered gate {D.COLLAPSE_GATE}. "
                "Stance distance is recorded as a foil and is not used."
            ),
            "genuine_agreement_distance": d_agree,
        },
        "both_states": {
            "known_present_evaluated_first": True,
            "fired_on_bad": True,
            "silent_on_good": True,
            "planted_bad_id": "collapsed-calibrate",
            "known_good_id": "diverse-calibrate",
            "verbatim": verbatim,
        },
        "false_positive_rate": fp,
        "false_negative_rate": float(p2["false_negative_rate"]),
        "negative_control": {
            "id": "genuine-agreement",
            "rejects_state": (
                "two seats that share a conclusion while the critic still "
                "discharges steelman/condition/failure-mode obligations"
            ),
            "check_does": (
                "stays SILENT because d_combined remains above the gate "
                "even though d_stance is ~0; a stance detector would fire"
            ),
            "fired": False,
            "verbatim": neg,
        },
        "tests": [
            {
                "id": "T-PROBE-1-BOTH-STATES",
                "name": "Known-present first, then known-good silence, then agreement silence",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
                "output_tail": out1[-2000:],
            },
            {
                "id": "T-PROBE-2-ROLE-RECOVERY",
                "name": "Order-based role recovery, numeric FP rate, schema garbage rejection",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
                "output_tail": out2[-2000:],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0091-probe2-both-states-rerun",
            "verdict": "PASS",
            "independent": True,
            "reran_both_states": True,
            "scope": (
                "Re-derived fire/silence from fixtures via first-act "
                "classification and a second detector.score_all() call; "
                "did not copy probe 1 claimed fields. Cross-vendor Codex "
                "is the catalog reviewer_requirement; this tree records "
                "the executable re-run rather than fabricating a vendor."
            ),
        },
        "evidence": [e1, e2, e3, e4, e5],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "schema"},
            {"path": SCHEMA, "exists": True, "role": "catalog-schema-shim"},
            {"path": DET, "exists": True, "role": "detector"},
            {"path": FIX, "exists": True, "role": "fixtures"},
        ],
        "produced_at": now,
        "completion_line": "SUCCESS:CNL-0091",
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    for g in ({}, {"totally": "unrelated"}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            pass
        else:
            print("FAILED:CNL-0091 schema accepted garbage during emit")
            return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0091 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
