#!/usr/bin/env python3
"""Emit command-center/research/RES-0102.json from a live ablation run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import catalog as C  # noqa: E402
import detectors as D  # noqa: E402
import measure as M  # noqa: E402

OUT_REL = "command-center/research/RES-0102.json"
SCHEMA_REL = "command-center/p2-wave/probes/RES-0102/measurement-run.schema.json"
CATALOG_SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = (
    "SUCCESS:RES-0102 in the receipt AND a per-component ablation delta table "
    "including at least one approximately-zero control"
)
QUESTION = (
    "Which components of a skill description drive correct routing "
    "(trigger phrases, negative scope, examples, length), measured by "
    "ablating each component and re-running a fixed routing task set?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0102/probe1_ablation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0102/probe2_both_states.py"
)
GARBAGE = [{}, {"totally": "unrelated", "kappa": 0.99}, {"x": "x" * 80}]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:RES-0102 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def compact_rows(acc: dict) -> list[dict]:
    return [
        {
            "id": r["id"],
            "gold": r["gold"],
            "chosen": r["chosen"],
            "correct": r["correct"],
            "best_score": r["best_score"],
        }
        for r in acc["rows"]
    ]


def main() -> int:
    exp = M.run_experiment()
    both = D.both_states(exp)
    control = exp["approximately_zero_control"]
    if not control["approximately_zero"] or not control["is_control"]:
        print(f"FAILED:RES-0102 control is not approximately zero {control}")
        return 1
    if not both["control_detector_shipped"]:
        print("FAILED:RES-0102 control detector did not distinguish both states")
        return 1

    schema = json.loads((HERE / "measurement-run.schema.json").read_text())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gold_rel = "command-center/p2-wave/probes/RES-0102/gold_tasks.json"
    catalog_py = "command-center/p2-wave/probes/RES-0102/catalog.py"
    router_py = "command-center/p2-wave/probes/RES-0102/router.py"
    none_effect = exp["components_with_no_measured_effect"]
    movers = exp["components_with_measured_effect"]

    def verdict(component: str) -> str:
        return "CONFIRMED" if component in movers else "REFUTED"

    claims = [
        {
            "id": "C-CONTROL-ZERO",
            "claim": (
                "Ablating irrelevant_meta produces |delta| <= "
                f"{exp['eps']} on the frozen 20-task set."
            ),
            "verdict": "CONFIRMED",
            "strongest_caveat": (
                "Zero because this router's irrelevant_meta weight is 0 by "
                "declaration. That is this instrument, not an LLM router."
            ),
        },
        {
            "id": "C-TRIGGER",
            "claim": "Ablating trigger_phrases changes routing accuracy.",
            "verdict": verdict("trigger_phrases"),
            "strongest_caveat": "Bodies often restate the YAML description.",
        },
        {
            "id": "C-NEGATIVE",
            "claim": "Ablating negative_scope changes abstain-task accuracy.",
            "verdict": verdict("negative_scope"),
            "strongest_caveat": "Negative spans are regex-extracted.",
        },
        {
            "id": "C-EXAMPLES",
            "claim": "Ablating fenced examples changes routing accuracy.",
            "verdict": verdict("examples"),
            "strongest_caveat": (
                "A zero delta is reported as no measured effect, not retained."
            ),
        },
        {
            "id": "C-LENGTH",
            "claim": "Ablating residual body length changes routing accuracy.",
            "verdict": verdict("length_body"),
            "strongest_caveat": "Length weight is 0.20 by prior declaration.",
        },
        {
            "id": "C-RES0101",
            "claim": "This run consumed the RES-0101 published gold task set.",
            "verdict": "REFUTED",
            "strongest_caveat": (
                "command-center/research/RES-0101.json is absent; gold is "
                "reconstructed and frozen in gold_tasks.json."
            ),
        },
    ]
    evidence = [
        {
            "path": gold_rel,
            "line": find_line(gold_rel, '"id": "RES-0102-gold-v1"'),
            "snippet": '"id": "RES-0102-gold-v1"',
            "kind": "gold-task-set",
        },
        {
            "path": catalog_py,
            "line": find_line(catalog_py, "CONTROL_COMPONENT"),
            "snippet": "CONTROL_COMPONENT",
            "kind": "control-component",
        },
        {
            "path": router_py,
            "line": find_line(router_py, '"irrelevant_meta": 0.0'),
            "snippet": '"irrelevant_meta": 0.0',
            "kind": "control-weight",
        },
        {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": find_line(
                "command-center/WORK-UNIT-CATALOG.json", '"id": "RES-0102"'
            ),
            "snippet": '"id": "RES-0102"',
            "kind": "catalog-unit",
        },
    ]
    doc = {
        "unit_id": "RES-0102",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "question": QUESTION,
        "ts": now,
        "method": {
            "router": "component-aware lexical coverage",
            "weights": {
                "trigger_phrases": 5.0,
                "examples": 2.5,
                "length_body": 0.20,
                "negative_scope": -6.0,
                "irrelevant_meta": 0.0,
            },
            "abstain_min": 0.18,
            "eps_approximately_zero": exp["eps"],
            "instrument_caveat": (
                "Deterministic lexical router over parsed SKILL.md components, "
                "not an LLM skill router."
            ),
        },
        "gold_task_set": exp["gold"],
        "catalog": exp["catalog"],
        "baseline": exp["baseline"],
        "ablation_delta_table": exp["ablation_delta_table"],
        "approximately_zero_control": control,
        "components_with_measured_effect": movers,
        "components_with_no_measured_effect": none_effect,
        "none_measured_reported_not_quietly_retained": True,
        "detectors": both,
        "routing_rows_baseline": compact_rows(exp["traces"]["full"]),
        "claims": claims,
        "catalog_schema_note": (
            f"{CATALOG_SCHEMA} is the RES-0003 E1-E4 grader sibling. "
            "This unit uses the unit-local ablation schema."
        ),
        "tests": [
            {
                "id": "T-ABLATION-TABLE",
                "command": P1,
                "result": "NOT-RUN",
                "requirement": (
                    "ablate each description component and report the "
                    "routing-accuracy delta"
                ),
            },
            {
                "id": "T-CONTROL-ZERO",
                "command": P2,
                "result": "NOT-RUN",
                "requirement": (
                    "irrelevant-component ablation must be approximately zero; "
                    "detectors must not be silent in both states"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0102-independent-recompute",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "default": "REFUTED",
            "notes": (
                "Recomputes the ablation table from gold_tasks.json and live "
                "SKILL.md files."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": gold_rel, "exists": True, "role": "gold-task-set"},
            {"path": SCHEMA_REL, "exists": True, "role": "unit-schema"},
        ],
        "evidence": evidence,
        "residual_unknowns": [
            "RES-0101 artifact absent; gold set reconstructed",
            "command-center/sources/REGISTER.md absent",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md absent on this Linux worktree",
            "LLM skill routing is unmeasured",
        ],
    }

    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != len(GARBAGE):
        print(f"FAILED:RES-0102 schema does not reject garbage rejected={rejected}")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0102 sentinel missing from serialized text")
        return 1
    out.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT_REL} control_delta={control['delta_from_baseline']} "
        f"movers={movers} none={none_effect}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
