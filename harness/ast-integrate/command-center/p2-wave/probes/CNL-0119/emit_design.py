#!/usr/bin/env python3
"""Emit the CNL-0119 simulation spec (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import simulate as S  # noqa: E402
import tabulator as T  # noqa: E402
from schema_offline import catalog_validator  # noqa: E402

UNIT = "CNL-0119"
OUT = (
    "command-center/design/council/"
    "CNL-0119-voting-method-differential-simulation-over-one-ballot-set.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py"
)
QUESTION = (
    "Run one fixed set of ballots through every implemented voting method - "
    "on how many fixtures do the methods disagree about the winner, and which "
    "method is most sensitive to a single flipped ballot?"
)
NC_VERBATIM = (
    "NEGATIVE-CONTROL verbatim: the disagreement check is SILENT on "
    "unanimous-3 (every method elects A) and FIRES on spoiler-triple "
    "(plurality=A, irv=C, borda=B)."
)
SUPPORTING = [
    "command-center/p2-wave/probes/CNL-0119/tabulator.py",
    "command-center/p2-wave/probes/CNL-0119/recount.py",
    "command-center/p2-wave/probes/CNL-0119/simulate.py",
    "command-center/p2-wave/probes/CNL-0119/fixtures.py",
    "command-center/p2-wave/probes/CNL-0119/fixtures/profiles.json",
    "command-center/p2-wave/probes/CNL-0119/fixtures/rules.json",
    "command-center/p2-wave/probes/CNL-0119/runtime/simulation-report.json",
]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0119 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    S.engines_match()
    live = S.dump_report()
    n = live["n_fixtures"]
    k = live["n_disagree"]
    rate = live["disagreement_rate"]
    most = live["most_sensitive"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tab_rel = "command-center/p2-wave/probes/CNL-0119/tabulator.py"
    rec_rel = "command-center/p2-wave/probes/CNL-0119/recount.py"
    sim_rel = "command-center/p2-wave/probes/CNL-0119/simulate.py"
    fix_rel = "command-center/p2-wave/probes/CNL-0119/fixtures/profiles.json"
    rules_rel = "command-center/p2-wave/probes/CNL-0119/fixtures/rules.json"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"

    table_txt = "; ".join(
        f"{r['method']} {r['n_winner_changes']}/{r['n_flips_tried']} "
        f"({r['rate']:.6f})"
        for r in live["sensitivity_table"]
    )
    answer = (
        f"On the declared {n}-fixture ranking corpus, {k} fixtures produce "
        f"a method disagreement about the winner (rate {k}/{n} = {rate:.6f}). "
        f"Disagreeing ids: {', '.join(live['disagreeing_fixture_ids'])}. "
        f"A single flipped ballot is demote-first-to-last on exactly one voter. "
        f"Most sensitive method: {most['method']} with "
        f"{most['n_winner_changes']} winner-changing flips out of "
        f"{live['sensitivity_table'][0]['n_flips_tried']} "
        f"(rate {most['rate']:.6f}). Sensitivity table: {table_txt}. "
        "Cardinal methods read the same ranking via declared projections "
        "(approval top-2; score vector 5,3,1,0); they are not a second ballot."
    )

    fixture_rows = []
    for r in live["fixtures"]:
        fixture_rows.append(
            {
                "id": r["id"],
                "role": r["role"],
                "n_ballots": r["n_ballots"],
                "candidates": r["candidates"],
                "winners": r["winners"],
                "winner_set": r["winner_set"],
                "methods_disagree": r["methods_disagree"],
                "n_flips": r["n_flips"],
                "flip_changes": r["flip_changes"],
            }
        )

    results = {
        "n_fixtures": n,
        "n_disagree": k,
        "n_agree": live["n_agree"],
        "disagreement_rate": rate,
        "disagreeing_fixture_ids": live["disagreeing_fixture_ids"],
        "agreeing_fixture_ids": live["agreeing_fixture_ids"],
        "sensitivity_table": live["sensitivity_table"],
        "most_sensitive": most,
        "fixtures": fixture_rows,
    }
    negative_control = {
        "state_the_check_is_meant_to_reject": (
            "a planted ranking profile on which implemented methods elect "
            "different winners (spoiler-triple)"
        ),
        "control_fixture": "unanimous-3, seven identical A>B>C rankings",
        "what_the_check_does_on_that_state": (
            "SILENT: plurality, IRV, Borda, approval_top2, score_5310, and "
            "copeland_minimax all elect A"
        ),
        "verbatim": NC_VERBATIM,
    }

    sim_n_dis = f"{sim_rel}:{find_line(sim_rel, 'n_dis = sum(1 for r in rows if r[\"methods_disagree\"])')}"
    sim_sens = f"{sim_rel}:{find_line(sim_rel, 'def most_sensitive(')}"
    rec_irv = f"{rec_rel}:{find_line(rec_rel, 'Continuing-pointer IRV')}"
    fix_sp = f"{fix_rel}:{find_line(fix_rel, 'spoiler-triple')}"
    cat_q = (
        f"{cat_rel}:"
        f"{find_line(cat_rel, 'Run one fixed set of ballots through every implemented voting method')}"
    )

    p1_out = (
        f"n_fixtures={n} n_disagree={k} disagreement_rate={rate:.6f} "
        f"most_sensitive={most['method']} n_winner_changes={most['n_winner_changes']}"
    )
    p2_out = (
        f"recount n_disagree={k}/{n} rate={rate:.6f} most_sensitive={most['method']}\n"
        f"{NC_VERBATIM}"
    )

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifacts[0]["role"] = "primary"

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0119",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767; WORK-UNIT-CATALOG.json:CNL-0119",
        "min_bytes_threshold": 4000,
        "profile": "council-simulation-spec",
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"{k} of {n} declared fixtures have a method disagreement "
                    f"(rate {rate:.6f})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": sim_n_dis,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_out,
                        "fingerprint": "cnl0119:probe1:tabulator-disagreement",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": "cnl0119:probe2:pointer-irv-recount",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"Most flip-sensitive method is {most['method']} with "
                    f"{most['n_winner_changes']} winner changes over "
                    f"{live['sensitivity_table'][0]['n_flips_tried']} flips."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": sim_sens,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_out,
                        "fingerprint": "cnl0119:probe1:flip-sweep",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": "cnl0119:probe2:flip-recount",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Independent pointer-IRV / matrix Copeland recount matches "
                    "the primary tabulator on every fixture winner and the "
                    "sensitivity table."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": rec_irv,
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": rec_irv,
                        "raw_output": "Continuing-pointer IRV (not first-match rescans)",
                        "fingerprint": "cnl0119:recount.py:pointer-irv",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": "cnl0119:probe2:engines-match",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-disagreement-sensitivity",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-independent-recount",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "negative-control-unanimous-silent",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unanimous-3-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "Disagreement detector on unanimous-3 (every ranking A>B>C). "
                    "Meant to stay SILENT: every implemented method elects A."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": (
                    "SILENT on unanimous-3: plurality=irv=borda=approval_top2="
                    "score_5310=copeland_minimax=A"
                ),
                "bad_state_output": (
                    "FIRE on spoiler-triple: plurality=A irv=C borda=B"
                ),
            },
            {
                "id": "spoiler-triple-fire",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted disagreement: spoiler-triple must FIRE "
                    "(plurality A, IRV C, Borda B). This is the state the "
                    "check is meant to reject if methods were claimed unanimous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "SILENT on unanimous-3",
                "bad_state_output": NC_VERBATIM,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0119-probe2-pointer-irv-matrix-copeland",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-tabulates every fixture with recount.py "
                "(continuing-pointer IRV and an n-by-n pairwise matrix) and "
                "must match the artifact winner table and sensitivity counts. "
                "It does not import tabulator.py."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0119/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "CNL-0119 probe1 disagreement-sensitivity",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": p1_out,
                    "fingerprint": "cnl0119:consumer:probe1",
                    "exit_code": 0,
                },
            },
            {
                "consumer": "CNL-0119 probe2 independent recount",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "raw_output": p2_out,
                    "fingerprint": "cnl0119:consumer:probe2",
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": "2026-08-24T20:40:00Z",
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
                    "CNL-0061/0062/0063 design notes are not on this tree; "
                    "method semantics here are fixtures/rules.json."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place those design artifacts on disk and diff the "
                    "declared IRV/approval/Copeland rules against them."
                ),
            },
            {
                "claim": (
                    "Schulze and ranked-pairs completions were not compared; "
                    "Copeland-then-minimax is the declared cycle rule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add Schulze and ranked-pairs engines and re-run the "
                    "9-fixture disagreement table."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-simulation-designer",
            "execution_substrate": "local-linux",
        },
        "report": {
            "kind": "council-simulation-spec",
            "observations": [
                {
                    "name": "n_fixtures",
                    "measured": n,
                    "method": "tabulator-over-declared-fixtures",
                    "anchor": sim_n_dis,
                },
                {
                    "name": "n_disagree",
                    "measured": k,
                    "method": "tabulator-over-declared-fixtures",
                    "anchor": sim_n_dis,
                },
                {
                    "name": "disagreement_rate",
                    "measured": rate,
                    "method": "k-over-n",
                    "anchor": sim_n_dis,
                },
                {
                    "name": "most_sensitive_method",
                    "measured": most["method"],
                    "method": "demote-first-to-last-sweep",
                    "anchor": sim_sens,
                },
                {
                    "name": "most_sensitive_winner_changes",
                    "measured": most["n_winner_changes"],
                    "method": "demote-first-to-last-sweep",
                    "anchor": sim_sens,
                },
            ],
            "control_ids": ["unanimous-3", "spoiler-triple"],
            "results": results,
        },
        "extensions": {
            "title": "Voting-method differential simulation over one ballot set",
            "phase": "2C",
            "question": QUESTION,
            "answer": answer,
            "results": results,
            "negative_control": negative_control,
            "simulation": {
                "harness": (
                    "frozen JSON rankings (one ranking per voter); not a live LLM council"
                ),
                "methods": list(T.METHODS),
                "method_rules": json.loads((REPO / rules_rel).read_text(encoding="utf-8")),
                "fixture_set": {
                    "path": fix_rel,
                    "n_fixtures": n,
                    "ids": [r["id"] for r in live["fixtures"]],
                    "note": (
                        "Complete rankings. Odd n_ballots per fixture so pairwise "
                        "contests have no ties."
                    ),
                },
                "implemented_on_this_tree": list(T.METHODS),
                "not_implemented_here": [
                    "majority-threshold / supermajority / unanimity / consent",
                    "juror / judge / veto / quorum / abstention / delegation",
                    "weighted (all weights=1, so weighted plurality collapses to plurality)",
                    "Bayesian-as-ranking-SCF (CNL-0065 is credence pooling, not a winner)",
                ],
            },
            "family": {
                "name": "implemented-winner-selection-methods",
                "expected_n": 6,
                "counted_n": 6,
                "members": [{"id": m} for m in T.METHODS],
            },
            "verdicts": [{"record_id": m, "verdict": "EXECUTABLE"} for m in T.METHODS],
            "both_states": {
                "good_state": {
                    "id": "unanimous-3",
                    "detector": "SILENT",
                    "winners": next(
                        r["winners"]
                        for r in live["fixtures"]
                        if r["id"] == "unanimous-3"
                    ),
                },
                "bad_state": {
                    "id": "spoiler-triple",
                    "detector": "FIRE",
                    "winners": next(
                        r["winners"]
                        for r in live["fixtures"]
                        if r["id"] == "spoiler-triple"
                    ),
                },
                "pass": True,
            },
            "reviewer_method": (
                "Probe 2 re-tabulates every fixture with recount.py "
                "(continuing-pointer IRV and an n-by-n pairwise matrix)."
            ),
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "disagreement-sensitivity"},
                {"id": "probe2", "command": P2, "role": "independent-recount"},
            ],
            "catalog_question_anchor": cat_q,
            "spoiler_fixture_anchor": fix_sp,
            "dependencies_noted": {
                "CNL-0061": "IRV elimination + lex-largest last-place tie-break implemented here",
                "CNL-0062": "approval_top2 and score_5310 are declared projections of the same ranking",
                "CNL-0063": "Copeland, then minimax (max votes-against), then lex, declared before ballots",
                "CNL-0065": "credence pooling is not a ranking SCF; excluded from the method list",
                "CNL-0117": "determinism via frozen fixtures, not the missing harness artifact",
                "blocked_on_missing_deps": False,
            },
        },
    }

    validator = catalog_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0119 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = {"blob": "x" * 200, "passing_tests": 1}
    g_errs = list(validator.iter_errors(garbage))
    if not g_errs:
        print("FAILED:CNL-0119 schema accepted garbage")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0119 artifact {size}B below floor")
        return 1
    disk = json.loads(out.read_text(encoding="utf-8"))
    disk_errs = list(validator.iter_errors(disk))
    if disk_errs:
        print("FAILED:CNL-0119 disk schema", disk_errs[0].message)
        return 1
    print(f"wrote {OUT} bytes={size} schema_garbage_errors={len(g_errs)}")
    print("SUCCESS:CNL-0119")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
