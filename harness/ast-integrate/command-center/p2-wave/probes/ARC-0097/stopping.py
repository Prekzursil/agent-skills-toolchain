"""Stopping-condition table and PR-ONLY satisfiability for ARC-0097.

Re-derives SC-13 unsatisfiability from (1) the stopping-condition text and
(2) the owner PR-ONLY decision. Does not inherit PHASE-GRAPH.json.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0097.json"
OWNER_DECISIONS = REPO / "command-center" / "OWNER-DECISIONS.md"
PHASE_GRAPH = REPO / "command-center" / "PHASE-GRAPH.json"
ALLOWED = frozenset({"SATISFIABLE", "UNSATISFIABLE-AS-WRITTEN", "NOT-CHECKED"})
CONFIDENCE = frozenset({"QUOTED", "RECONSTRUCTED", "ABSENT-VERBATIM"})

# Spec lines 11378-11398 are the 21 conditions (catalog cites :11378 as SC-1).
# Verbatim _USER-PROMPTS.md is absent on this worktree. Each row names how
# its text was obtained. ABSENT-VERBATIM rows are NOT-CHECKED, not guessed.
CONDITION_SEEDS = [
    {
        "id": 1,
        "spec_line": 11378,
        "text": (
            "Every selected option id is in exactly one terminal state: "
            "IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "WORK-UNIT-CATALOG.json ARC-0111 / SYN-0028: stopping condition 1, "
            "_USER-PROMPTS.md:11378"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": (
            "PR-ONLY constrains publication, not option-id disposition. A PR "
            "tree can still implement, supersede, or reject every selected id."
        ),
    },
    {
        "id": 2,
        "spec_line": 11379,
        "text": (
            "Verbatim stopping-condition text for spec line 11379 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only; no catalog quotation of this line",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": (
            "Cannot evaluate satisfiability without the predicate text. "
            "PR-ONLY is not assumed to make an unknown condition unsatisfiable."
        ),
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
    {
        "id": 3,
        "spec_line": 11380,
        "text": (
            "Verbatim stopping-condition text for spec line 11380 is not on "
            "this worktree. Adjacent citation: ADV-0090 spec_anchor "
            "_USER-PROMPTS.md:11380 (flaky / rerun-until-green evidence)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "ADV-0090 spec_anchor :11380, 11059",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": (
            "Adjacent citation is not the predicate. Satisfiability left "
            "NOT-CHECKED rather than reconstructed into a silent pass."
        ),
        "settling_experiment": (
            "Read spec line 11380 verbatim and re-classify this row."
        ),
    },
    {
        "id": 4,
        "spec_line": 11381,
        "text": "No required test is red.",
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "WORK-UNIT-CATALOG.json SYN-0043 tests_required: "
            "'condition 4 (no required test is red)'"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": (
            "CI-on-PR-head can be green. PR-ONLY does not forbid a green "
            "required-test set."
        ),
    },
    {
        "id": 5,
        "spec_line": 11382,
        "text": (
            "Mutation and negative-control coverage demonstrate detector "
            "validity."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "CC-0014 / ADV-0010 spec_anchor _USER-PROMPTS.md:11325, 11382"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Detector evidence is local; PR-ONLY does not remove it.",
    },
    {
        "id": 6,
        "spec_line": 11383,
        "text": (
            "Verbatim stopping-condition text for spec line 11383 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": "Predicate text absent; not guessed.",
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
    {
        "id": 7,
        "spec_line": 11384,
        "text": (
            "Compatibility-matrix cells may only be marked supported by a "
            "recorded test run; an untested cell is NOT-CHECKED, never a pass."
        ),
        "text_confidence": "RECONSTRUCTED",
        "catalog_anchor": "ARC-0095 inputs cite _USER-PROMPTS.md:11384",
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": (
            "A matrix with honest NOT-CHECKED cells is expressible under "
            "PR-ONLY. Untested-as-pass is a representation rule, not a "
            "canary channel."
        ),
    },
    {
        "id": 8,
        "spec_line": 11385,
        "text": (
            "Benchmark results show the intended improvement without material "
            "regression."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "SYN / TST units: stopping condition 8, _USER-PROMPTS.md:11385"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Benchmarks run on a PR head; no canary required.",
    },
    {
        "id": 9,
        "spec_line": 11386,
        "text": (
            "Verbatim stopping-condition text for spec line 11386 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": "Predicate text absent; not guessed.",
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
    {
        "id": 10,
        "spec_line": 11387,
        "text": (
            "Verbatim stopping-condition text for spec line 11387 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": "Predicate text absent; not guessed.",
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
    {
        "id": 11,
        "spec_line": 11388,
        "text": (
            "Release-time re-execution of vulnerability and license scanners "
            "(a stored implementation-time scan does not satisfy)."
        ),
        "text_confidence": "RECONSTRUCTED",
        "catalog_anchor": "ADV-0016 spec_anchor _USER-PROMPTS.md:11112, 11129, 11388",
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": (
            "A PR CI job can re-run scanners at merge-candidate time. "
            "PR-ONLY does not require a canary to make a fresh scan."
        ),
    },
    {
        "id": 12,
        "spec_line": 11389,
        "text": "Docs and code agree.",
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "ARC-0106 / ADV-0112: stopping condition 12, _USER-PROMPTS.md:11389"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Parity is a repo property; PR-ONLY does not block it.",
    },
    {
        "id": 13,
        "spec_line": 11390,
        "text": "Release/canary succeeds.",
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "ARC-0097 / REL-0003 / CC-0015: stop condition 13, spec 11390, "
            "'release/canary succeeds'"
        ),
        "satisfiability_under_pr_only": "UNSATISFIABLE-AS-WRITTEN",
        "reason": (
            "As written the predicate requires a canary (or a marketplace "
            "release) to succeed. Binding PR-ONLY forbids both. See "
            "unsatisfiability_rederivation: two independent readings."
        ),
    },
    {
        "id": 14,
        "spec_line": 11391,
        "text": "Rollback is tested.",
        "text_confidence": "QUOTED",
        "catalog_anchor": "REL / ADV-0119: _USER-PROMPTS.md:11391 (rollback is tested)",
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": (
            "OQ-9's throwaway-prefix install/upgrade/rollback rehearsal is "
            "exactly this class of evidence, and it does not need a canary "
            "channel."
        ),
    },
    {
        "id": 15,
        "spec_line": 11392,
        "text": (
            "Every residual unknown has a named settling experiment and an "
            "owner-visible impact statement."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "AUD / SYN units: stopping condition 15, _USER-PROMPTS.md:11392"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Unknowns-register work is independent of release channel.",
    },
    {
        "id": 16,
        "spec_line": 11393,
        "text": (
            "At least 160 workflow candidates/mechanisms researched and "
            "classified with provenance/license records."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": (
            "WFA-0123 title: Prove program stopping condition 16; :11393"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Count floors are corpus properties, not publish channels.",
    },
    {
        "id": 17,
        "spec_line": 11394,
        "text": (
            "At least 96 materially distinct workflow blueprints executable "
            "under the selected quality tiers."
        ),
        "text_confidence": "QUOTED",
        "catalog_anchor": "WFA-0124 inputs _USER-PROMPTS.md:11394",
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Executability is local; PR-ONLY does not remove blueprints.",
    },
    {
        "id": 18,
        "spec_line": 11395,
        "text": (
            "Numeric floors packed into stopping conditions 16-19 include "
            ">=48 council protocols (and the paired preset floor on 11396)."
        ),
        "text_confidence": "RECONSTRUCTED",
        "catalog_anchor": (
            "SYN-0031: stopping conditions 16-19, :11393-11396; floors "
            ">=160 candidates, >=96 blueprints, >=48 protocols, >=64 presets, "
            ">=2048 work units, >=160 platform options"
        ),
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Floor counts are independent of canary/marketplace.",
    },
    {
        "id": 19,
        "spec_line": 11396,
        "text": (
            "Numeric floors packed into stopping conditions 16-19 include "
            ">=64 presets, >=2048 work units, and >=160 platform options."
        ),
        "text_confidence": "RECONSTRUCTED",
        "catalog_anchor": "SYN-0031 / CNF-0188 :11393-11396 (the floors)",
        "satisfiability_under_pr_only": "SATISFIABLE",
        "reason": "Floor counts are independent of canary/marketplace.",
    },
    {
        "id": 20,
        "spec_line": 11397,
        "text": (
            "Verbatim stopping-condition text for spec line 11397 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": "Predicate text absent; not guessed.",
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
    {
        "id": 21,
        "spec_line": 11398,
        "text": (
            "Verbatim stopping-condition text for spec line 11398 is not on "
            "this worktree (_USER-PROMPTS.md absent)."
        ),
        "text_confidence": "ABSENT-VERBATIM",
        "catalog_anchor": "line number only",
        "satisfiability_under_pr_only": "NOT-CHECKED",
        "reason": "Predicate text absent; not guessed.",
        "settling_experiment": (
            "Place _USER-PROMPTS.md:11376-11398 on disk and re-run probe1."
        ),
    },
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def owner_question(catalog: dict, qid: str) -> dict | None:
    for row in catalog.get("owner_questions") or []:
        if isinstance(row, dict) and row.get("id") == qid:
            return row
    return None


def input_presence() -> dict:
    return {
        "USER_PROMPTS_md": (REPO / "_USER-PROMPTS.md").is_file(),
        "OWNER_DECISIONS_md": OWNER_DECISIONS.is_file(),
        "RELEASE_CHECKLIST_md": (
            REPO / "command-center" / "RELEASE-CHECKLIST.md"
        ).is_file(),
        "PHASE_GRAPH_json": PHASE_GRAPH.is_file(),
        "WINNING_ARCHITECTURE_json": (
            REPO / "command-center" / "phase3" / "WINNING-ARCHITECTURE.json"
        ).is_file(),
        "ARCHITECTURE_RATIFICATION_json": (
            REPO / "command-center" / "phase3" / "ARCHITECTURE-RATIFICATION.json"
        ).is_file(),
        "WORK_UNIT_CATALOG_json": CATALOG.is_file(),
        "owner_decisions_working_source": (
            "OWNER-DECISIONS.md (rendered table) plus "
            "WORK-UNIT-CATALOG.json owner_questions (structured)"
            if OWNER_DECISIONS.is_file()
            else (
                "command-center/WORK-UNIT-CATALOG.json owner_questions "
                "(OWNER-DECISIONS.md absent on this worktree)"
            )
        ),
    }


def load_owner_context() -> dict:
    catalog = load_json(CATALOG)
    if not isinstance(catalog, dict):
        raise RuntimeError("catalog unreadable")
    oq3 = owner_question(catalog, "OQ-3")
    oq9 = owner_question(catalog, "OQ-9")
    if not isinstance(oq3, dict) or not isinstance(oq9, dict):
        raise RuntimeError("OQ-3 or OQ-9 missing from catalog owner_questions")
    return {"catalog": catalog, "oq3": oq3, "oq9": oq9}


def owner_md_corroborates_pr_only() -> dict:
    """Markdown render of owner questions. Not PHASE-GRAPH.json."""
    present = OWNER_DECISIONS.is_file()
    if not present:
        return {
            "present": False,
            "corroborates": False,
            "path": "command-center/OWNER-DECISIONS.md",
        }
    text = OWNER_DECISIONS.read_text(encoding="utf-8")
    low = text.lower()
    corroborates = (
        "OQ-3" in text
        and "PR-ONLY" in text
        and "never a private canary" in low
        and "never a public marketplace" in low
    )
    return {
        "present": True,
        "corroborates": corroborates,
        "path": "command-center/OWNER-DECISIONS.md",
        "field": "markdown-table-plus-answered-section",
        "not_phase_graph": True,
    }


def is_pr_only(oq3: dict) -> bool:
    ans = str(oq3.get("answer") or "").strip().upper()
    detail = str(oq3.get("answer_detail") or "").upper()
    return ans.startswith("PR-ONLY") and "PR-ONLY" in detail and oq3.get("state") == "ANSWERED"


def forbids_canary(oq3: dict) -> bool:
    detail = str(oq3.get("answer_detail") or "").lower()
    return "never a private canary" in detail and "never a public marketplace" in detail


def rederive_sc13(oq3: dict) -> dict:
    """Independent of PHASE-GRAPH. Two readings, both recorded."""
    sc13 = next(r for r in CONDITION_SEEDS if r["id"] == 13)
    text = sc13["text"]
    text_has_canary = "canary" in text.lower()
    reading_text = {
        "source": "stopping-condition-text",
        "spec_line": 11390,
        "quoted_text": text,
        "observation": (
            "The predicate 'release/canary succeeds' names a canary (and/or a "
            "release) as the event that must succeed. A canary channel is a "
            "referent the predicate requires."
        ),
        "under_pr_only": (
            "PR-ONLY has no canary channel, so the canary disjunct has no "
            "satisfiable referent. A public/marketplace 'release succeeds' "
            "disjunct is likewise forbidden by the same mode. As written, "
            "neither disjunct can become true."
        ),
        "text_mentions_canary": text_has_canary,
        "verdict": "UNSATISFIABLE-AS-WRITTEN",
    }
    reading_owner = {
        "source": "owner-decision",
        "owner_question_id": "OQ-3",
        "state": oq3.get("state"),
        "answer": oq3.get("answer"),
        "answered_on": oq3.get("answered_on"),
        "answer_provenance": oq3.get("answer_provenance"),
        "quoted_detail": oq3.get("answer_detail"),
        "observation": (
            "OQ-3 binds release mode to PR-ONLY: propose changes as pull "
            "requests, never a private canary and never a public marketplace "
            "release."
        ),
        "under_pr_only": (
            "The owner decision independently removes both referents the "
            "as-written predicate needs. This reading does not cite "
            "PHASE-GRAPH.json."
        ),
        "forbids_private_canary": forbids_canary(oq3),
        "owner_decisions_md": owner_md_corroborates_pr_only(),
        "verdict": "UNSATISFIABLE-AS-WRITTEN",
    }
    md = reading_owner["owner_decisions_md"]
    agree = (
        reading_text["verdict"] == "UNSATISFIABLE-AS-WRITTEN"
        and reading_owner["verdict"] == "UNSATISFIABLE-AS-WRITTEN"
        and text_has_canary
        and forbids_canary(oq3)
        and is_pr_only(oq3)
        and (not md["present"] or md["corroborates"])
    )
    return {
        "inherited_from_phase_graph": False,
        "phase_graph_present": PHASE_GRAPH.is_file(),
        "phase_graph_used_as_source": False,
        "owner_decisions_md_present": OWNER_DECISIONS.is_file(),
        "working_owner_record": "WORK-UNIT-CATALOG.json owner_questions OQ-3",
        "reading_from_stopping_condition_text": reading_text,
        "reading_from_owner_decision": reading_owner,
        "readings_agree": agree,
        "verdict": "UNSATISFIABLE-AS-WRITTEN",
    }


def conditions() -> list[dict]:
    rows = []
    for seed in CONDITION_SEEDS:
        row = dict(seed)
        if row["satisfiability_under_pr_only"] not in ALLOWED:
            raise RuntimeError(f"bad verdict {row['id']}")
        if row["text_confidence"] not in CONFIDENCE:
            raise RuntimeError(f"bad confidence {row['id']}")
        rows.append(row)
    if len(rows) != 21 or [r["id"] for r in rows] != list(range(1, 22)):
        raise RuntimeError("condition table is not 1..21")
    if [r["spec_line"] for r in rows] != list(range(11378, 11399)):
        raise RuntimeError("spec lines are not 11378-11398")
    return rows


def evaluate() -> dict:
    ctx = load_owner_context()
    oq3, oq9 = ctx["oq3"], ctx["oq9"]
    rows = conditions()
    red = rederive_sc13(oq3)
    sc13 = next(r for r in rows if r["id"] == 13)
    counts = {k: 0 for k in ALLOWED}
    for r in rows:
        counts[r["satisfiability_under_pr_only"]] += 1
    return {
        "unit_id": "ARC-0097",
        "release_mode": {
            "binding": "PR-ONLY",
            "owner_question_id": "OQ-3",
            "state": oq3.get("state"),
            "answer": oq3.get("answer"),
            "answer_detail": oq3.get("answer_detail"),
            "answered_on": oq3.get("answered_on"),
            "answer_provenance": oq3.get("answer_provenance"),
            "forbids": [
                "private canary channel",
                "public marketplace release",
            ],
        },
        "oq9_canary_substitute": {
            "owner_question_id": "OQ-9",
            "state": oq9.get("state"),
            "answer": oq9.get("answer"),
            "answer_detail": oq9.get("answer_detail"),
            "answered_on": oq9.get("answered_on"),
            "answer_provenance": oq9.get("answer_provenance"),
        },
        "stopping_conditions": rows,
        "counts": counts,
        "sc13": sc13,
        "unsatisfiability_rederivation": red,
        "input_presence": input_presence(),
        "ok": (
            is_pr_only(oq3)
            and oq9.get("state") == "ANSWERED"
            and sc13["satisfiability_under_pr_only"] == "UNSATISFIABLE-AS-WRITTEN"
            and red["readings_agree"] is True
            and red["inherited_from_phase_graph"] is False
            and len(rows) == 21
            and counts["UNSATISFIABLE-AS-WRITTEN"] >= 1
            and all(r["satisfiability_under_pr_only"] in ALLOWED for r in rows)
        ),
    }


def load_contract() -> dict | None:
    data = load_json(CONTRACT)
    return data if isinstance(data, dict) else None


def contract_payload(doc: dict) -> dict:
    """Receipt-core documents park domain fields under report.

    Probes still read stopping_conditions / sc13_handling as if they were
    top-level. Merge report over the receipt without dropping unit_id/state.
    """
    if not isinstance(doc, dict):
        return {}
    out = dict(doc)
    report = doc.get("report")
    if not isinstance(report, dict):
        return out
    domain = (
        "stopping_conditions",
        "stopping_condition_counts",
        "sc13_handling",
        "unsatisfiability_rederivation",
        "waiver_discipline",
        "gates",
        "release_mode",
        "oq9_canary_substitute",
        "honesty",
        "input_presence",
        "sign_off",
    )
    for key in domain:
        if key in report:
            out[key] = report[key]
    return out
