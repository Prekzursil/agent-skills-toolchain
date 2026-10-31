"""Deep-research workflow under measurement (TST-0319).

The honest workflow honours the configured favourable/unfavourable quotas,
runs a real contradiction search, and preserves negative and contradicting
evidence all the way into the FINAL report's contradiction appendix - not
just into the working notes. A queried claim with zero matching sources
produces a proof-of-impossibility record (never a consensus-over-nothing),
and contradicting evidence stronger than the supporting evidence is reported
as CONTRADICTION-DOMINANT, never as CONSENSUS.

Artifacts written per run (out_dir):
  notes.json         working notes: every retrieved observation, contradictions included
  final_report.md    BEGIN_SELECTED mix + BEGIN_CONTRADICTIONS appendix + Verdict line
  final_report.json  the machine-readable final report
  impossibility.json only on the proof-of-impossibility code path
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

STANCE_SUPPORT = "support"
STANCE_CONTRADICT = "contradict"

VERDICT_CONSENSUS = "CONSENSUS"
VERDICT_CONTRADICTION_DOMINANT = "CONTRADICTION-DOMINANT"
VERDICT_IMPOSSIBLE = "IMPOSSIBLE"

MARK_SEL_BEGIN = "BEGIN_SELECTED"
MARK_SEL_END = "END_SELECTED"
MARK_CON_BEGIN = "BEGIN_CONTRADICTIONS"
MARK_CON_END = "END_CONTRADICTIONS"

DEFAULT_CONFIG: dict[str, Any] = {
    "favourable_quota": 0.70,
    "unfavourable_quota": 0.30,
    "contradiction_search": True,
    "preserve_negative": True,
    "report_slot_budget": 10,
}


def corpus_sources(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [s for s in (corpus.get("sources") or []) if isinstance(s, dict)]


def query_claim_id(corpus: Mapping[str, Any]) -> str:
    return str(corpus.get("query_claim_id") or corpus.get("claim_id") or "")


def retrieve(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    claim = query_claim_id(corpus)
    return [s for s in corpus_sources(corpus) if s.get("claim_id") == claim]


def find_contradictions(
    retrieved: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair supporting against contradicting observations per claim."""
    support = [s for s in retrieved if s.get("stance") == STANCE_SUPPORT]
    contradict = [s for s in retrieved if s.get("stance") == STANCE_CONTRADICT]
    pairs: list[dict[str, Any]] = []
    for c in contradict:
        for s in support:
            if s.get("claim_id") == c.get("claim_id"):
                pairs.append(
                    {
                        "claim_id": c.get("claim_id"),
                        "support_token": s.get("token"),
                        "contradict_token": c.get("token"),
                        "strength_delta": round(
                            float(c.get("strength") or 0.0)
                            - float(s.get("strength") or 0.0),
                            6,
                        ),
                    }
                )
    return pairs


def build_notes(
    corpus: Mapping[str, Any],
    retrieved: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Working notes carry EVERY retrieved observation - contradictions included.

    Intermediate notes never count as survival; the final appendix does. But
    the notes are where contradicting evidence is first recorded, so a
    synthesizer that drops them later is detectable by exactly this
    notes-vs-final differential.
    """
    return {
        "kind": "working-notes",
        "corpus_id": corpus.get("id"),
        "query_claim_id": query_claim_id(corpus),
        "preserve_negative": True,
        "observations": [
            {
                "id": s.get("id"),
                "token": s.get("token"),
                "claim_id": s.get("claim_id"),
                "stance": s.get("stance"),
                "strength": s.get("strength"),
                "source_class": s.get("source_class"),
                "excerpt": str(s.get("body") or "")[:240],
            }
            for s in retrieved
        ],
        "contradiction_pairs": contradictions,
    }


def quota_counts(config: Mapping[str, Any]) -> tuple[int, int, int]:
    budget = int(config.get("report_slot_budget") or 10)
    fav_q = float(config.get("favourable_quota") or 0.0)
    n_fav = int(round(budget * fav_q))
    return budget, n_fav, budget - n_fav


def _strength_sum(rows: list[dict[str, Any]]) -> float:
    return sum(float(s.get("strength") or 0.0) for s in rows)


def _emit_impossibility_record(
    corpus: Mapping[str, Any], claim: str
) -> dict[str, Any]:
    """Proof-of-impossibility: not-found is a finding with a falsifier, not a quiet consensus."""
    exhausted = sorted({str(s.get("source_class") or "unknown") for s in corpus_sources(corpus)})
    queries_run = [
        {"source_class": cls, "query": f"{claim} {cls}", "hits": 0}
        for cls in exhausted
    ]
    return {
        "kind": "proof-of-impossibility",
        "code_path": "emit_impossibility_record",
        "corpus_id": corpus.get("id"),
        "claim_id": claim,
        "exhausted_source_classes": exhausted,
        "queries_run": queries_run,
        "falsifier": (
            f"any source with claim_id {claim} inside an exhausted source class "
            "overturns this record"
        ),
        "expiry": "recheck on next corpus refresh, or 30 days, whichever comes first",
    }


def run_research(
    corpus: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    claim = query_claim_id(corpus)
    retrieved = retrieve(corpus)
    contradictions = find_contradictions(retrieved)
    notes = build_notes(corpus, retrieved, contradictions)

    if not retrieved:
        impossibility = _emit_impossibility_record(corpus, claim)
        report = {
            "kind": "final-report",
            "corpus_id": corpus.get("id"),
            "query_claim_id": claim,
            "verdict": VERDICT_IMPOSSIBLE,
            "configured_quota": {
                "favourable": float(cfg.get("favourable_quota") or 0.0),
                "unfavourable": float(cfg.get("unfavourable_quota") or 0.0),
                "report_slot_budget": int(cfg.get("report_slot_budget") or 10),
            },
            "returned_proportion": {
                "support": 0.0,
                "contradict": 0.0,
                "polar_n": 0,
                "support_tokens": [],
                "contradict_tokens": [],
            },
            "selected_ids": [],
            "selected_tokens": [],
            "contradiction_appendix_tokens": [],
            "contradiction_pair_count": 0,
            "preserve_negative": bool(cfg.get("preserve_negative")),
            "code_path": "emit_impossibility_record",
        }
        result = {
            "verdict": VERDICT_IMPOSSIBLE,
            "notes": notes,
            "final_report": report,
            "impossibility": impossibility,
            "selected": [],
            "retrieved": [],
            "contradictions": contradictions,
        }
        if out_dir is not None:
            write_artifacts(Path(out_dir), result)
        return result

    support = [s for s in retrieved if s.get("stance") == STANCE_SUPPORT]
    contradict = [s for s in retrieved if s.get("stance") == STANCE_CONTRADICT]
    support.sort(key=lambda s: (-float(s.get("strength") or 0.0), str(s.get("id"))))
    contradict.sort(key=lambda s: (-float(s.get("strength") or 0.0), str(s.get("id"))))

    budget, n_fav, n_unfav = quota_counts(cfg)
    sel_support = support[:n_fav]
    sel_contradict = contradict[:n_unfav]
    selected = sel_support + sel_contradict
    polar_n = len(sel_support) + len(sel_contradict)

    sup_strength = _strength_sum(support)
    con_strength = _strength_sum(contradict)
    verdict = (
        VERDICT_CONTRADICTION_DOMINANT if con_strength > sup_strength else VERDICT_CONSENSUS
    )

    # Preserve negative: every contradicting token found reaches the appendix.
    appendix_tokens: list[str] = []
    for s in contradict:
        tok = str(s.get("token"))
        if tok not in appendix_tokens:
            appendix_tokens.append(tok)

    report = {
        "kind": "final-report",
        "corpus_id": corpus.get("id"),
        "query_claim_id": claim,
        "verdict": verdict,
        "configured_quota": {
            "favourable": float(cfg.get("favourable_quota") or 0.0),
            "unfavourable": float(cfg.get("unfavourable_quota") or 0.0),
            "report_slot_budget": budget,
        },
        "returned_proportion": {
            "support": (len(sel_support) / polar_n) if polar_n else 0.0,
            "contradict": (len(sel_contradict) / polar_n) if polar_n else 0.0,
            "polar_n": polar_n,
            "support_tokens": [str(s.get("token")) for s in sel_support],
            "contradict_tokens": [str(s.get("token")) for s in sel_contradict],
        },
        "selected_ids": [str(s.get("id")) for s in selected],
        "selected_tokens": [str(s.get("token")) for s in selected],
        "contradiction_appendix_tokens": appendix_tokens,
        "contradiction_pair_count": len(contradictions),
        "preserve_negative": bool(cfg.get("preserve_negative")),
        "strength_totals": {"support": sup_strength, "contradict": con_strength},
        "code_path": "run_research",
    }
    result = {
        "verdict": verdict,
        "notes": notes,
        "final_report": report,
        "impossibility": None,
        "selected": selected,
        "retrieved": list(retrieved),
        "contradictions": contradictions,
    }
    if out_dir is not None:
        write_artifacts(Path(out_dir), result)
    return result


def write_artifacts(out_dir: Path, result: Mapping[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = result.get("notes")
    (out_dir / "notes.json").write_text(
        json.dumps(notes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = result.get("final_report") or {}
    (out_dir / "final_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sel_tokens = [str(t) for t in (report.get("selected_tokens") or [])]
    appendix = [str(t) for t in (report.get("contradiction_appendix_tokens") or [])]
    lines = [
        f"# Final research report - {report.get('corpus_id')}",
        f"Query claim: {report.get('query_claim_id')}",
        "",
        MARK_SEL_BEGIN,
        *sel_tokens,
        MARK_SEL_END,
        "",
        MARK_CON_BEGIN,
        *appendix,
        MARK_CON_END,
        "",
        f"Verdict: {report.get('verdict')}",
        "",
    ]
    (out_dir / "final_report.md").write_text("\n".join(lines), encoding="utf-8")
    impossibility = result.get("impossibility")
    if impossibility is not None:
        (out_dir / "impossibility.json").write_text(
            json.dumps(impossibility, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


__all__ = [
    "DEFAULT_CONFIG",
    "MARK_CON_BEGIN",
    "MARK_CON_END",
    "MARK_SEL_BEGIN",
    "MARK_SEL_END",
    "STANCE_CONTRADICT",
    "STANCE_SUPPORT",
    "VERDICT_CONSENSUS",
    "VERDICT_CONTRADICTION_DOMINANT",
    "VERDICT_IMPOSSIBLE",
    "build_notes",
    "corpus_sources",
    "find_contradictions",
    "query_claim_id",
    "quota_counts",
    "retrieve",
    "run_research",
    "write_artifacts",
]
