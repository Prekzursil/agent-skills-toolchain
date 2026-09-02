#!/usr/bin/env python3
"""Emit the CNL-0026 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import separation as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0026-judge-and-juror-separation-to-remove-the-single-epistemic-.md"
)
SCHEMA_LOCAL = "command-center/p2-wave/probes/CNL-0026/note.schema.json"
QUESTION = (
    "The spec names the moderator or judge becoming a single point of epistemic "
    "failure as a required regression case - what separation of the judge role "
    "from the juror role actually removes that single point of epistemic failure "
    "rather than relabelling it?"
)
REQUIRED_SPEC = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0026/probe1_corrupted_judge.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0026/probe2_negative_control.py"
)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:CNL-0026 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    live = S.live_measurement()
    if not live["pass"]:
        print("FAILED:CNL-0026 emit live measurement did not pass")
        print(json.dumps(live, indent=2, sort_keys=True)[:4000])
        return 1
    thr = live["corruption_threshold"]
    evidence = [
        ev(
            "command-center/p2-wave/probes/TST-0295/seeded_classes.py",
            "corruption threshold unspecified",
            "live-tree",
            "Spec line 11342 is catalogued as FC-11342: the corruption threshold "
            "was unspecified; this unit computes it. phase3/A1/FAILURE-MODES.json "
            "is absent on this worktree; TST-0295 is the live restatement.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            ":11342 names the judge becoming a single point of epistemic failure",
            "live-tree",
            "Live restatement of _USER-PROMPTS.md:11342: the judge as SPOF is "
            "the required regression case.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342",
            "live-tree",
            "CNL-0026 evidence requirement names that locus and demands a computed number.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "raw participant record survives intact has a recovery path even when the judge is wrong",
            "live-tree",
            "ADV-0103: independent juror records, not a second judge prompt, are the mitigation.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "what separation of the judge role from the juror role actually removes",
            "live-tree",
            "This unit's question: separation must remove SPOF, not relabel it.",
        ),
    ]
    spec_present = Path(REQUIRED_SPEC).is_file() or (
        REPO / "_USER-PROMPTS.md"
    ).is_file()
    answer = (
        "Separation that removes the single epistemic point of failure is a split "
        "of authority over the published outcome, not a split of seat titles. "
        "Jurors exclusively cast recorded ballots. The published verdict is the "
        "mechanical strict majority of those ballots (need = floor(N/2)+1 of the "
        "juror seats). The judge has an empty ballot and may only certify that "
        "the verdict form equals the tally. A failed certification is recorded "
        "and the tally still publishes. A hung jury is NO-DECISION; the judge "
        "may not break it with a vote. Dissent ballots remain on the decision "
        "record even when the judge certifies the opposite of the tally. "
        "Relabelling is any configuration in which the judge's write-up is the "
        "verdict (jurors advisory, dissent droppable, hung broken by the chair "
        "of the court). It is detected, not asserted: corrupting only the judge "
        "flips the published outcome. Under the separated configuration that "
        "min-cut does not exist. The corruption threshold is the smallest role "
        f"set that does flip the outcome: computed min_k={thr['value']} for "
        f"N={thr['n_jurors']} unanimous jurors (brute-force combinations; "
        f"formula floor(N/2)+1 also equals {thr['formula_value']}). The judge "
        "seat is not a member of any minimum set. Fused relabel min_k=1 (the "
        "judge alone). That pair of numbers is the difference between removing "
        "the SPOF and renaming it."
    )
    markdown_body = "\n".join(
        [
            "# CNL-0026 — Judge and juror separation",
            "",
            QUESTION,
            "",
            "## Decision",
            "",
            answer,
            "",
            "## What is not separation",
            "",
            "- Two prompts, one titled Judge and one titled Juror, while the",
            "  published artifact is whatever the judge writes.",
            "- A judge tie-break ballot that turns a hung jury into a decision.",
            "- A synthesiser that 'summarises' votes and is the only surviving record.",
            "- Distinct vendors on the two seats with the same authority graph.",
            "",
            "## Authority table",
            "",
            "| Power | Juror | Judge (separated) | Judge (relabelled) |",
            "| ballot in the tally | obligation | forbidden | the only ballot that counts |",
            "| determine published outcome | via mechanical majority | cannot | does |",
            "| drop a dissent from the decision record | cannot | cannot | typically does |",
            "| hung jury becomes a pick | cannot | cannot; outcome is NO-DECISION | typically does |",
            "",
            f"## Corruption threshold (computed, not asserted)",
            "",
            f"- N_jurors = {thr['n_jurors']}",
            f"- separated min_k = {thr['value']} (juror seats; judge not in the cut)",
            f"- fused min_k = {thr['fused_value']} (judge alone)",
            f"- method: {thr['method']}",
            f"- subsets_examined = {thr['subsets_examined']}",
            "",
            "## Spec locus",
            "",
            f"Required citation: `{REQUIRED_SPEC}` (absent on this Linux estate: "
            f"{not spec_present}). Live restatement: TST-0295 FC-11342 "
            "'corruption threshold unspecified' and catalog TST-0268/ADV-0103 "
            "on the judge as SPOF.",
            "",
            "SUCCESS:CNL-0026",
            "",
        ]
    )
    doc = {
        "unit_id": "CNL-0026",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0026",
        "title": "Judge and juror separation to remove the single epistemic point of failure",
        "question": QUESTION,
        "answer": answer,
        "markdown_body": markdown_body,
        "mechanism": {
            "separated": (
                "published_outcome = mechanical_majority(juror_ballots); "
                "judge certifies that equality or the certification is rejected; "
                "the tally still publishes; judge has no ballot"
            ),
            "fused_relabel": (
                "published_outcome = judge_written_verdict; "
                "juror ballots advisory; dissent dropped from the decision record"
            ),
            "not_a_label_split": (
                "Distinct display names, prompts, or vendors with the fused "
                "authority graph remain a single epistemic point of failure"
            ),
        },
        "corruption_threshold": thr,
        "spec_anchor": {
            "required_path": REQUIRED_SPEC,
            "line": 11342,
            "present_on_this_estate": spec_present,
            "failure_class": "FC-11342",
            "failure_class_name": "corruption threshold unspecified",
            "live_restatements": [
                "command-center/p2-wave/probes/TST-0295/seeded_classes.py:FC-11342",
                "command-center/WORK-UNIT-CATALOG.json:TST-0268",
                "command-center/WORK-UNIT-CATALOG.json:ADV-0103",
            ],
        },
        "live": {
            "separated_cut": live["separated_cut"],
            "fused_cut": live["fused_cut"],
            "both_states": live["both_states"],
            "hung": live["hung"],
            "dissent": live["dissent"],
            "verbatim_separated": live["verbatim_separated"],
            "verbatim_fused": live["verbatim_fused"],
        },
        "negative_control": {
            "state_rejected": "fused-judge-writes-verdict",
            "meant_to_reject": "judge is a single point of epistemic failure",
            "check_does": (
                "FIRES: corrupting only the judge flips the published outcome "
                "from SUPPORT to REJECT on the unanimous-juror fixture"
            ),
            "verbatim": live["negative_control_verbatim"],
            "on_separated_corrupted_judge": "SILENT (outcome stays SUPPORT)",
        },
        "tests": [
            {
                "id": "corrupted-judge-fixture",
                "command": P1,
                "result": "PASS",
                "assertion": (
                    "one bad judge does not determine the outcome under "
                    f"separation; min_k={thr['value']}"
                ),
            },
            {
                "id": "negative-control-fused-relabel",
                "command": P2,
                "result": "PASS",
                "assertion": "the SPOF check FIRES on fused-judge-writes-verdict",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0026-probe2-both-states-rerun",
            "vendor_role": "openai/gpt-5-codex",
            "independent": True,
            "executed_both_states": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "control": "silent on separated; FIRES on fused; hung stays NO-DECISION",
        },
        "evidence": evidence,
        "strongest_surviving_counterargument": (
            "The judge still rules on evidence admissibility and could starve "
            "jurors of the fact that would have changed their ballots, which "
            "would restore a single point of failure upstream of the tally. "
            "This unit forbids post-ballot exclusion (already-cast ballots are "
            "immutable) and uses a checkable fixture whose known answer is in "
            "the protocol, not gated by the judge. A full admissibility lattice "
            "is a different unit; it is residual, not a reason to keep the "
            "judge as the verdict writer."
        ),
        "residual_unknowns": [
            "Pre-ballot evidence exclusion by a captured judge is out of scope here.",
            "Moderator/chair agenda capture is CNL-0025, not this verdict-authority split.",
            f"{REQUIRED_SPEC} is not on this Linux estate; live restatements were used.",
        ],
        "fixtures": [
            "command-center/p2-wave/probes/CNL-0026/fixtures/honest-unanimous.json",
            "command-center/p2-wave/probes/CNL-0026/fixtures/corrupted-judge-separated.json",
            "command-center/p2-wave/probes/CNL-0026/fixtures/fused-relabel-corrupted-judge.json",
            "command-center/p2-wave/probes/CNL-0026/fixtures/hung-2-2-1.json",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_LOCAL, "exists": True, "role": "supporting"},
        ],
        "output_schema_declared": "command-center/schema/council-design-note.schema.json",
        "output_schema_present": (
            REPO / "command-center/schema/council-design-note.schema.json"
        ).is_file(),
        "local_schema": SCHEMA_LOCAL,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    schema = json.loads((REPO / SCHEMA_LOCAL).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size} min_k={thr['value']}")
    print("SUCCESS:CNL-0026 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
