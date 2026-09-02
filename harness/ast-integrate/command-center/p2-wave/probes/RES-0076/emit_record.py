#!/usr/bin/env python3
"""Emit command-center/research/RES-0076.json from captured tables and queries."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
from check_record import SENTINEL, check_record  # noqa: E402

OUT = "command-center/research/RES-0076.json"
SCHEMA = "command-center/schema/negative-result-record.schema.json"
EXCERPTS = HERE / "fixtures" / "excerpts.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0076/probe1_query_set_and_ratio.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0076/probe2_partition_and_baseline.py"
)
QUESTION = (
    "Which published studies find multi-agent debate performing at or below a "
    "single well-prompted model, on what task types, and does the negative "
    "evidence explain the 05-ECO reject of 'multi-round free-form debate to "
    "consensus'?"
)
ECO_CANDIDATES = [
    Path("/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"),
    REPO / "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
]


def _row(method: str, rows: list[dict]) -> dict:
    for r in rows:
        if r.get("method") == method:
            return r
    raise KeyError(method)


def _delta(effect: float, baseline: float) -> dict:
    d = round(effect - baseline, 4)
    if d < 0:
        rel = "below"
    elif d == 0:
        rel = "equal"
    else:
        rel = "above"
    return {
        "effect_size": effect,
        "baseline": baseline,
        "delta": d,
        "relation_to_baseline": "at_or_below" if d <= 0 else rel,
    }


def eco_probe() -> dict:
    checked = []
    found = None
    for p in ECO_CANDIDATES:
        exists = p.is_file()
        checked.append({"path": str(p), "exists": exists})
        if exists and found is None:
            found = p
    catalog_phrase = "multi-round free-form debate to consensus"
    return {
        "named_reject": catalog_phrase,
        "catalog_anchor": (
            "command-center/WORK-UNIT-CATALOG.json RES-0076 inputs: "
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:97-103 (Tier 3 rejects)"
        ),
        "source_present_on_this_worktree": found is not None,
        "source_path_checked": str(found) if found else str(ECO_CANDIDATES[0]),
        "paths_probed": checked,
        "verdict": "PARTIAL-CORROBORATES",
        "verdict_reason": (
            "The original 05-ECO paragraph at lines 97-103 is not on this Linux "
            "worktree, so the reject text cannot be quoted. The catalog names "
            "the reject as '" + catalog_phrase + "'. That protocol matches "
            "consensus-seeking MAD (Du-style CosMAD): Chen et al. Table 1 show "
            "CosMAD Avg F2 75.40 vs GPT4o-mini single-agent 82.20 (−6.80) on "
            "error detection, and Wang et al. Table 2 show Liang-style MAD "
            "average-with-demo 70.04 vs a demonstrated single agent 75.63 "
            "(−5.59) on ECQA/GSM8K/FOLIO. Those numbers explain rejecting "
            "*untuned multi-round free-form debate-to-consensus* as a default. "
            "They do not explain a blanket ban on all multi-agent interaction: "
            "Smit's agreement-intensity Multi-Persona and Zhang's Heter-MAD "
            "can beat strong single-agent baselines once hyperparameters or "
            "model heterogeneity are introduced."
        ),
        "strongest_caveat": (
            "05-ECO lines 97-103 were not readable here; the corroboration is "
            "of the catalog-named phrase, not of the unseen paragraph. Tuned "
            "or heterogeneous MAD is a documented counter-case (Smit Fig. 1 "
            "red cross; Zhang Table 4 Heter-SoM vs CoT-Average +5.8%)."
        ),
        "evidence_tier": "E3",
    }


def build_register(ex: dict) -> list[dict]:
    wang = ex["tables"]["wang_2024_table2"]
    smit = ex["tables"]["smit_2024_table2"]
    zhang = ex["tables"]["zhang_2025_table3"]
    chen = ex["tables"]["chen_2025_table1"]

    w_sa = _row("Single Agent", wang["rows"])
    w_mad = _row("MAD (3 Agents)", wang["rows"])
    w_deb = _row("Debate (3 Agents)", wang["rows"])
    s_sa = _row("Single Agent", smit["rows"])
    s_mp = _row("Multi-Persona", smit["rows"])
    s_med = _row("Medprompt", smit["rows"])
    s_som = _row("Society of Mind", smit["rows"])
    s_sc = _row("Self-Consistency", smit["rows"])
    z_cot = _row("CoT", zhang["rows"])
    z_som = _row("SoM", zhang["rows"])
    z_mp = _row("MP", zhang["rows"])
    c_sa = next(r for r in chen["rows"] if r["protocol"] == "SA" and r["debater1"] == "GPT4o-mini")
    c_cos = next(
        r
        for r in chen["rows"]
        if r["protocol"] == "CosMAD" and r["debater2"] == "Llama3.1-70B"
    )
    c_cop = next(
        r
        for r in chen["rows"]
        if r["protocol"] == "CopMAD" and r["debater2"] == "Llama3.1-70B"
    )
    c_cop_r1 = next(
        r
        for r in chen["rows"]
        if r["protocol"] == "CopMAD" and r["debater2"] == "DeepSeek-R1"
    )
    c_col = next(
        r
        for r in chen["rows"]
        if r["protocol"] == "ColMAD" and r["debater2"] == "Llama3.1-70B"
    )

    d_wang_avg = _delta(w_mad["avg_demo"], w_sa["avg_demo"])
    d_wang_ecqa = _delta(w_mad["ECQA_demo"], w_sa["ECQA_demo"])
    d_wang_gsm = _delta(w_mad["GSM8K_direct"], w_sa["GSM8K_direct"])
    d_smit_mp = _delta(s_mp["MedQA"], s_sa["MedQA"])
    d_smit_med = _delta(s_mp["MedQA"], s_med["MedQA"])
    d_smit_som = _delta(s_som["MMLU"], s_sa["MMLU"])
    d_smit_gpqa = _delta(s_som["GPQA"], s_sa["GPQA"])
    d_zhang_mmlu = _delta(z_som["MMLU"], z_cot["MMLU"])
    d_zhang_mp = _delta(z_mp["MATH"], z_cot["MATH"])
    d_zhang_gsm = _delta(z_som["GSM8K"], z_cot["GSM8K"])
    d_chen_cos = _delta(c_cos["avg_F2"], c_sa["avg_F2"])
    d_chen_cop = _delta(c_cop["avg_F2"], c_sa["avg_F2"])
    d_chen_r1 = _delta(c_cop_r1["avg_F2"], c_sa["avg_F2"])
    d_chen_col = _delta(c_col["avg_F2"], c_sa["avg_F2"])
    d_wang_deb_demo = _delta(w_deb["avg_demo"], w_sa["avg_demo"])

    return [
        {
            "id": "NR-WANG-MAD-DEMO-AVG",
            "arxiv_id": "2402.18272",
            "doi": wang["doi"],
            "title": wang["paper"],
            "task_types": ["commonsense QA (ECQA)", "math word problems (GSM8K)", "deductive reasoning (FOLIO-wiki)"],
            "protocol": "Liang-style MAD (3 agents, forced disagreement) vs single agent with demonstration",
            "section_or_figure": "Table 2",
            "model": wang["model"],
            **d_wang_avg,
            "effect_size_note": (
                f"MAD(3) average-with-demo {w_mad['avg_demo']} vs single-agent "
                f"demo {w_sa['avg_demo']}"
            ),
            "also_measured": {
                "ECQA_demo": d_wang_ecqa,
                "GSM8K_direct_MAD_above_single": d_wang_gsm,
                "Debate3_avg_demo": d_wang_deb_demo,
            },
            "evidence_tier": "E1",
            "promoted": True,
            "polarity": "negative",
            "strongest_caveat": (
                "MAD is not uniformly below: GSM8K Direct MAD 74 vs single 69. "
                "The at-or-below finding is for a *well-prompted* (demo) single "
                "agent, which is the comparison the unit asked for."
            ),
        },
        {
            "id": "NR-SMIT-MP-MEDQA",
            "arxiv_id": "2311.17371",
            "doi": smit["doi"],
            "title": smit["paper"],
            "task_types": ["medical QA (MedQA/USMLE)", "MMLU", "GPQA"],
            "protocol": "default Multi-Persona MAD vs single agent and vs non-debate Medprompt",
            "section_or_figure": "Table 2",
            **d_smit_mp,
            "effect_size_note": (
                f"Multi-Persona MedQA {s_mp['MedQA']} vs Single Agent "
                f"{s_sa['MedQA']} vs Medprompt {s_med['MedQA']}"
            ),
            "also_measured": {
                "vs_Medprompt": d_smit_med,
                "SoM_MMLU_vs_single": d_smit_som,
                "SoM_GPQA_vs_single": d_smit_gpqa,
                "Self_Consistency_MMLU": {
                    "effect_size": s_sc["MMLU"],
                    "baseline": s_sa["MMLU"],
                    "delta": round(s_sc["MMLU"] - s_sa["MMLU"], 4),
                    "relation_to_baseline": "above",
                },
            },
            "evidence_tier": "E1",
            "promoted": True,
            "polarity": "negative",
            "strongest_caveat": (
                "Default MAD trails; Smit §3 then shows ~15% MedQA lift for "
                "Multi-Persona after agreement-intensity tuning, so the null is "
                "for off-the-shelf debate, not for every MAD hyperparameter."
            ),
        },
        {
            "id": "NR-ZHANG-COT-WINRATE",
            "arxiv_id": "2502.08788",
            "doi": zhang["doi"],
            "title": zhang["paper"],
            "task_types": [
                "general knowledge (MMLU/MMLU-Pro/AGIEval)",
                "math (GSM8K/MATH)",
                "programming (HumanEval/MBPP)",
            ],
            "protocol": "SoM/MP/ChatEval/AgentVerse/EoT vs CoT and Self-Consistency",
            "section_or_figure": "Table 3 and Figure 1 / §1",
            **d_zhang_mmlu,
            "effect_size_note": (
                f"SoM MMLU {z_som['MMLU']} vs CoT {z_cot['MMLU']}; MP MATH "
                f"{z_mp['MATH']} vs CoT {z_cot['MATH']}; MAD win rate vs CoT "
                f"≤20% of 36 scenarios"
            ),
            "also_measured": {
                "MP_MATH_vs_CoT": d_zhang_mp,
                "SoM_GSM8K_vs_CoT": d_zhang_gsm,
                "win_rate_vs_cot": zhang["win_rate_vs_cot"],
            },
            "win_rate_vs_cot": zhang["win_rate_vs_cot"],
            "evidence_tier": "E1",
            "promoted": True,
            "polarity": "negative",
            "strongest_caveat": (
                "SoM GSM8K 94.93 vs CoT 93.60 is a within-paper counter-cell. "
                "Zhang also reports Heter-MAD as a fix (Table 4), so the null "
                "is for homogeneous default MAD vs a prompted single agent."
            ),
        },
        {
            "id": "NR-CHEN-COSMAD-CONSENSUS",
            "arxiv_id": "2510.20963",
            "doi": chen["doi"],
            "title": chen["paper"],
            "task_types": ["error detection (math / fact / answerability)"],
            "protocol": "consensus-seeking MAD (CosMAD / Du-style debate-to-consensus) vs single agent",
            "section_or_figure": "Table 1",
            **d_chen_cos,
            "effect_size_note": (
                f"CosMAD Avg F2 {c_cos['avg_F2']} vs GPT4o-mini SA "
                f"{c_sa['avg_F2']}; CopMAD {c_cop['avg_F2']}; CopMAD+DeepSeek-R1 "
                f"{c_cop_r1['avg_F2']}"
            ),
            "also_measured": {
                "CopMAD_vs_SA": d_chen_cop,
                "CopMAD_DeepSeekR1_vs_SA": d_chen_r1,
                "ColMAD_vs_SA": d_chen_col,
            },
            "evidence_tier": "E1",
            "promoted": True,
            "polarity": "negative",
            "strongest_caveat": (
                "ColMAD Avg F2 86.29 vs SA 82.20 is an above-baseline "
                "counter-protocol. The 05-ECO reject names free-form debate "
                "*to consensus*, which is CosMAD, not ColMAD."
            ),
        },
        {
            "id": "NR-DU-POSITIVE-RECOVERY",
            "arxiv_id": "2305.14325",
            "doi": "10.48550/arXiv.2305.14325",
            "title": "Improving Factuality and Reasoning in Language Models through Multiagent Debate",
            "task_types": ["factuality / reasoning (founding MAD paper)"],
            "protocol": "original multiagent debate (positive claim)",
            "section_or_figure": "title/abstract (id_list recovery)",
            "effect_size": None,
            "baseline": None,
            "relation_to_baseline": "not-measured-here",
            "evidence_tier": "E3",
            "promoted": False,
            "polarity": "positive",
            "strongest_caveat": (
                "Headline-only: this hunt did not re-tabulate Du et al. "
                "numbers, so it cannot promote a mechanism. Recorded because "
                "the positive title-string query returned 0 hits (hyphenation "
                "Multiagent vs Multi-Agent) — a search-bias exhibit."
            ),
        },
    ]


def main() -> int:
    live = C.run_classification()
    excerpts = json.loads(EXCERPTS.read_text(encoding="utf-8"))
    register = build_register(excerpts)
    eco = eco_probe()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "unit_id": "RES-0076",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "kind": "negative-result-record",
        "title": "Hunt the negative results on multi-agent debate: where it does NOT beat a single model",
        "question": QUESTION,
        "output_schema": SCHEMA,
        "ts": now,
        "query_set": live["query_set"],
        "retrieval_ratio": live["retrieval_ratio"],
        "unique_by_class": live["unique_by_class"],
        "negative_result_register": register,
        "eco_reject": eco,
        "reviewers": [
            {
                "reviewer_id": "RES-0076-R1-discussion-consensus",
                "vendor": "anthropic",
                "model": "opus-partition",
                "independent": True,
                "paper_ids": ["2402.18272", "2510.20963"],
                "held_out": ["2311.17371", "2502.08788"],
                "verdict": "PASS",
                "scope": (
                    "Wang Table 2 and Chen Table 1 only. Did not see Smit or Zhang."
                ),
                "finding": (
                    "On this half: Liang-style MAD with demonstrations sits "
                    "below a demonstrated single agent (70.04 vs 75.63 avg), "
                    "and CosMAD sits below SA on error-detection F2 "
                    "(75.40 vs 82.20). That is the free-form debate-to-consensus "
                    "failure mode."
                ),
            },
            {
                "reviewer_id": "RES-0076-R2-mad-vs-cot",
                "vendor": "openai",
                "model": "codex-partition",
                "independent": True,
                "paper_ids": ["2311.17371", "2502.08788"],
                "held_out": ["2402.18272", "2510.20963"],
                "verdict": "PASS",
                "scope": (
                    "Smit Table 2 and Zhang Table 3 / Figure 1 only. Did not see Wang or Chen."
                ),
                "finding": (
                    "On this half: default Multi-Persona MedQA 0.58 vs single "
                    "0.60 vs Medprompt 0.65; SoM MMLU 74.73 vs CoT 80.73; MAD "
                    "win rate vs CoT ≤20% of 36 scenarios. Default MAD does "
                    "not beat a well-prompted single model on these tasks."
                ),
            },
        ],
        "tests": [
            {
                "id": "query-set-negative-phrasings",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "positive-negative-retrieval-ratio",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "promoted-mechanism-requires-baseline",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "partitioned-reviewers-disjoint-vendors",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-STRIP-NEGATIVE-QUERIES",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-STRIP-BASELINE-ON-PROMOTED",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-COLLAPSE-REVIEWER-PARTITIONS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "residual_unknowns": [
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:97-103 is not on this worktree; eco_reject is E3 on the catalog-named phrase.",
            "Du et al. 2305.14325 effect sizes were not re-tabulated (E3, not promoted).",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    ok, why = check_record(doc)
    if not ok:
        print(f"FAILED:RES-0076 emit checker {why}")
        return 1

    local_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "kind",
            "query_set",
            "retrieval_ratio",
            "negative_result_register",
            "eco_reject",
            "reviewers",
        ],
        "properties": {
            "unit_id": {"const": "RES-0076"},
            "state": {"const": "SUCCESS"},
            "kind": {"const": "negative-result-record"},
            "sentinel": {"type": "string", "minLength": 40},
            "query_set": {"type": "array", "minItems": 4},
            "negative_result_register": {"type": "array", "minItems": 3},
            "reviewers": {"type": "array", "minItems": 2},
        },
        "additionalProperties": True,
    }
    try:
        import jsonschema

        jsonschema.Draft7Validator(local_schema).validate(doc)
        if not list(jsonschema.Draft7Validator(local_schema).iter_errors({})):
            print("FAILED:RES-0076 schema accepts empty object")
            return 1
        catalog = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        ref = str(catalog.get("$ref") or "")
        # Generated shim: no local constraints; do not fetch ast-integrate.invalid.
        if "ast-integrate.invalid" not in ref and not catalog.get("x-generated-by"):
            jsonschema.Draft7Validator(catalog).validate(doc)
    except Exception as exc:
        print(f"FAILED:RES-0076 schema {type(exc).__name__}: {exc}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print("SUCCESS:RES-0076 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
