"""TST-0233 fusion admission gate.

Executes each workflow's handlers over the matched case set (deterministic
pass/fail per case), derives outcome vectors, and applies the receipt rule:

  REJECT FC-11334  outcome_vector(fusion) == outcome_vector(source) for any
                   source AND n_stages(fusion) > n_stages(source)
                   (stage-padded catalog gloss; stage count is reported but is
                   never a scoring component)
  REJECT FC-11333  score(fusion) < score(source) for EVERY source
  ACCEPT           iff every source is beaten (higher passed_cases) OR the
                   named complementarity rows show a case where the source
                   fails and the fusion succeeds
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "fixtures" / "corpus.json"

FC_PADDED = "FC-11334"
FC_WORSE = "FC-11333"


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or CORPUS_PATH).read_text(encoding="utf-8"))


def execute_workflow(wf: dict[str, Any], cases: list[str]) -> dict[str, Any]:
    """Run the handlers over the matched cases; returns the outcome vector."""
    handlers = wf.get("handlers") or {}
    vector: list[list[Any]] = []
    for case_id in cases:
        outcome = handlers.get(case_id)
        if outcome not in ("pass", "fail"):
            raise ValueError(f"workflow handler for {case_id} missing/invalid: {outcome!r}")
        vector.append([case_id, outcome == "pass"])
    return {
        "n_stages": len(wf.get("stages") or []),
        "outcome_vector": vector,
        "passed": sum(1 for _, ok in vector if ok),
        "score": sum(1 for _, ok in vector if ok),
    }


def _complement_rows_for(candidate: str, corpus: dict[str, Any]) -> list[dict[str, Any]]:
    named = corpus.get("named_complementarity_case") or {}
    if str(named.get("fusion_id")) != candidate:
        return []
    return [row for row in (named.get("rows") or []) if isinstance(row, dict)]


def evaluate(corpus: dict[str, Any]) -> dict[str, Any]:
    cases = [str(c) for c in corpus.get("cases") or []]
    sources = [str(s) for s in corpus.get("sources") or []]
    results: dict[str, dict[str, Any]] = {}
    for wf_id in [*sources, *[str(c) for c in corpus.get("candidates") or []]]:
        wf = (corpus.get("workflows") or {}).get(wf_id)
        if wf is None:
            raise ValueError(f"corpus is missing workflow {wf_id}")
        results[wf_id] = execute_workflow(wf, cases)

    verdicts: list[dict[str, Any]] = []
    for candidate in [str(c) for c in corpus.get("candidates") or []]:
        cand = results[candidate]
        verdict: dict[str, Any] = {
            "fusion_id": candidate,
            "n_stages": cand["n_stages"],
            "score": cand["score"],
            "outcome_vector": cand["outcome_vector"],
        }
        # FC-11334: identical behaviour to any source with more stages
        padded_of = [
            s for s in sources
            if results[s]["outcome_vector"] == cand["outcome_vector"]
            and cand["n_stages"] > results[s]["n_stages"]
        ]
        if padded_of:
            verdict.update(
                {
                    "decision": "REJECT",
                    "failure_class": FC_PADDED,
                    "reason": "identical behaviour to "
                    + ",".join(padded_of)
                    + " with more stages; stage count is not a scoring component",
                }
            )
            verdicts.append(verdict)
            continue
        # FC-11333: worse than every source
        if all(cand["score"] < results[s]["score"] for s in sources):
            verdict.update(
                {
                    "decision": "REJECT",
                    "failure_class": FC_WORSE,
                    "reason": "score below every source on matched cases",
                }
            )
            verdicts.append(verdict)
            continue
        # ACCEPT iff every source is beaten or materially complemented
        per_source: list[dict[str, Any]] = []
        for s in sources:
            beaten = cand["score"] > results[s]["score"]
            comp_case = None
            for row in _complement_rows_for(candidate, corpus):
                if str(row.get("source_id")) == s:
                    case_id = str(row.get("case_id"))
                    src_passed = next(
                        (ok for cid, ok in results[s]["outcome_vector"] if cid == case_id),
                        None,
                    )
                    fus_passed = next(
                        (ok for cid, ok in cand["outcome_vector"] if cid == case_id),
                        None,
                    )
                    if src_passed is False and fus_passed is True:
                        comp_case = {"case_id": case_id, "source_passed": False, "fusion_passed": True}
                        break
            per_source.append({"source_id": s, "beaten": beaten, "complementarity_case": comp_case})
        accepted = all(p["beaten"] or p["complementarity_case"] for p in per_source)
        verdict.update(
            {
                "decision": "ACCEPT" if accepted else "REJECT",
                "failure_class": None if accepted else FC_WORSE,
                "reason": "beats or materially complements every source"
                if accepted
                else "fails to beat or complement at least one source",
                "per_source": per_source,
            }
        )
        verdicts.append(verdict)

    return {
        "cases": cases,
        "budget": corpus.get("budget"),
        "budget_parity": all(r["n_stages"] <= int(corpus.get("budget", 0)) for r in results.values()),
        "results": {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()},
        "verdicts": verdicts,
    }


def evaluate_corpus(path: Path | None = None) -> dict[str, Any]:
    return evaluate(load_corpus(path))
