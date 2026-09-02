"""Extract recorded scorecard dissents and compute preservation as a set difference.

Identity of a recorded dissent is judge|entry|dimension. The check that
fails the unit is:

    missing = scorecard_ids - report_ids

A non-empty missing set is dissent-loss. Extra report rows are reported
but do not satisfy preservation by themselves. Comparing the report to
itself is refused: both operands must come from distinct sources.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_SCORECARDS = "command-center/phase3/SCORECARDS.json"
LIVE_RANKING = "command-center/phase3/AGGREGATE-RANKING.json"
FIXTURE_SCORECARDS = (
    "command-center/p2-wave/probes/ARC-0071/fixtures/SCORECARDS.json"
)
FIXTURE_RANKING = (
    "command-center/p2-wave/probes/ARC-0071/fixtures/AGGREGATE-RANKING.json"
)

CANON_FIELDS = (
    "judge_id",
    "entry_id",
    "dimension",
    "score",
    "reasoning",
    "evidence_citation",
)

DISSENT_LIST_KEYS = (
    "dissents",
    "minority_positions",
    "recorded_dissents",
    "disagreements",
)


def dissent_id(rec: dict[str, Any]) -> str:
    """ARC-0071 identity: judge|entry|dimension"""
    return f"{rec['judge_id']}|{rec['entry_id']}|{rec['dimension']}"


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonicalize(card: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    dim = item.get("dimension") or item.get("axis") or item.get("criterion")
    rec = {
        "judge_id": _as_str(item.get("judge_id") or card.get("judge_id")),
        "entry_id": _as_str(item.get("entry_id") or card.get("entry_id")),
        "dimension": _as_str(dim),
        "score": item.get("score"),
        "reasoning": _as_str(
            item.get("reasoning") or item.get("rationale") or item.get("reason")
        ),
        "evidence_citation": _as_str(
            item.get("evidence_citation")
            or item.get("evidence")
            or item.get("citation")
        ),
    }
    if rec["score"] is not None:
        rec["score"] = float(rec["score"])
    majority = item.get("majority_score")
    if majority is not None:
        rec["majority_score"] = float(majority)
    rec["dissent_id"] = dissent_id(rec)
    return rec


def _valid(rec: dict[str, Any]) -> bool:
    return bool(
        rec.get("judge_id")
        and rec.get("entry_id")
        and rec.get("dimension")
        and rec.get("reasoning")
        and rec.get("evidence_citation")
        and rec.get("score") is not None
    )


def _items_from_card(card: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in DISSENT_LIST_KEYS:
        val = card.get(key)
        if isinstance(val, list):
            items.extend(x for x in val if isinstance(x, dict))
    for dim in card.get("dimensions") or card.get("scores") or []:
        if not isinstance(dim, dict):
            continue
        flagged = dim.get("dissent") or dim.get("is_dissent") or dim.get("minority")
        if flagged is True:
            items.append(dim)
    return items


def extract_dissents(scorecards_doc: dict[str, Any]) -> list[dict[str, Any]]:
    cards = scorecards_doc.get("scorecards")
    if not isinstance(cards, list):
        cards = scorecards_doc.get("cards") or []
    found: dict[str, dict[str, Any]] = {}
    for card in cards:
        if not isinstance(card, dict):
            continue
        for item in _items_from_card(card):
            rec = canonicalize(card, item)
            if not _valid(rec):
                continue
            # First writer wins: explicit dissents[] precedes dimension flags.
            if rec["dissent_id"] not in found:
                found[rec["dissent_id"]] = rec
    return [found[k] for k in sorted(found)]


def extract_report_positions(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (
        report.get("minority_positions")
        or report.get("dissents")
        or report.get("positions")
        or []
    )
    found: dict[str, dict[str, Any]] = {}
    empty_card: dict[str, Any] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        rec = canonicalize(empty_card, item)
        if not _valid(rec):
            continue
        found[rec["dissent_id"]] = rec
    return [found[k] for k in sorted(found)]


def id_set(rows: list[dict[str, Any]]) -> set[str]:
    return {r["dissent_id"] for r in rows}


def preservation_diff(
    scorecard_ids: set[str],
    report_ids: set[str],
    *,
    scorecard_source: str,
    report_source: str,
) -> dict[str, Any]:
    """Set-difference of recorded-dissent ids. Not a narration.

    Operands must name distinct sources. Using the report as both sides
    is a tautology and is refused.
    """
    if scorecard_source == report_source:
        raise ValueError("tautology: scorecard_source == report_source")
    missing = sorted(scorecard_ids - report_ids)
    extra = sorted(report_ids - scorecard_ids)
    return {
        "method": "set-difference",
        "formula": "missing = scorecard_ids - report_ids",
        "scorecard_source": scorecard_source,
        "report_source": report_source,
        "scorecard_dissent_ids": sorted(scorecard_ids),
        "report_dissent_ids": sorted(report_ids),
        "scorecard_minus_report": missing,
        "report_minus_scorecard": extra,
        "scorecard_count": len(scorecard_ids),
        "report_count": len(report_ids),
        "missing_count": len(missing),
        "preserved": missing == [],
    }


def both_states(
    scorecard_rows: list[dict[str, Any]],
    report_rows: list[dict[str, Any]],
    scorecard_source: str,
) -> dict[str, Any]:
    sc_ids = id_set(scorecard_rows)
    if not sc_ids:
        return {
            "discriminates": False,
            "reason": "no recorded dissents to delete",
        }
    intact = preservation_diff(
        sc_ids,
        id_set(report_rows),
        scorecard_source=scorecard_source,
        report_source="report:intact",
    )
    victim = sorted(sc_ids)[0]
    mutant_rows = [r for r in report_rows if r["dissent_id"] != victim]
    fired = preservation_diff(
        sc_ids,
        id_set(mutant_rows),
        scorecard_source=scorecard_source,
        report_source="report:deleted-one-dissent",
    )
    return {
        "victim_id": victim,
        "intact_preserved": intact["preserved"],
        "intact_missing": intact["scorecard_minus_report"],
        "mutant_preserved": fired["preserved"],
        "mutant_missing": fired["scorecard_minus_report"],
        "mutant_missing_contains_victim": victim in fired["scorecard_minus_report"],
        "silent_on_clean": intact["preserved"] is True,
        "fires_on_delete": (
            fired["preserved"] is False
            and victim in fired["scorecard_minus_report"]
        ),
        "discriminates": (
            intact["preserved"] is True
            and fired["preserved"] is False
            and victim in fired["scorecard_minus_report"]
        ),
    }


def undistorted(
    scorecard_rows: list[dict[str, Any]],
    report_rows: list[dict[str, Any]],
    judge_id: str,
) -> dict[str, Any]:
    """A dissenting judge's rows must reappear field-for-field."""
    sc = [r for r in scorecard_rows if r["judge_id"] == judge_id]
    rp_by_id = {r["dissent_id"]: r for r in report_rows}
    mismatches: list[dict[str, Any]] = []
    missing: list[str] = []
    for rec in sc:
        other = rp_by_id.get(rec["dissent_id"])
        if other is None:
            missing.append(rec["dissent_id"])
            continue
        for field in CANON_FIELDS:
            if rec.get(field) != other.get(field):
                mismatches.append(
                    {
                        "dissent_id": rec["dissent_id"],
                        "field": field,
                        "scorecard": rec.get(field),
                        "report": other.get(field),
                    }
                )
    return {
        "judge_id": judge_id,
        "scorecard_rows": len(sc),
        "missing_from_report": missing,
        "field_mismatches": mismatches,
        "undistorted": (not missing) and (not mismatches) and len(sc) >= 1,
    }


def distort_reasoning(
    report_rows: list[dict[str, Any]], victim_id: str
) -> list[dict[str, Any]]:
    mutant = copy.deepcopy(report_rows)
    for rec in mutant:
        if rec["dissent_id"] == victim_id:
            rec["reasoning"] = "DISTORTED: " + rec["reasoning"]
    return mutant


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_inputs(repo: Path | None = None) -> dict[str, Any]:
    import fixtures as F  # local

    root = repo or REPO
    F.dump(root / "command-center/p2-wave/probes/ARC-0071/fixtures")
    live_sc = root / LIVE_SCORECARDS
    live_rk = root / LIVE_RANKING
    if live_sc.is_file() and live_sc.stat().st_size > 0:
        sc_doc = load_json(live_sc)
        sc_rel, sc_live = LIVE_SCORECARDS, True
    else:
        sc_doc = F.scorecards()
        sc_rel, sc_live = FIXTURE_SCORECARDS, False
    if live_rk.is_file() and live_rk.stat().st_size > 0:
        rk_doc = load_json(live_rk)
        rk_rel, rk_live = LIVE_RANKING, True
    else:
        rk_doc = F.ranking()
        rk_rel, rk_live = FIXTURE_RANKING, False
    winner = (
        rk_doc.get("winner_entry_id")
        or rk_doc.get("winner")
        or (rk_doc.get("ranking") or [{}])[0].get("entry_id")
    )
    return {
        "scorecards": sc_doc,
        "ranking": rk_doc,
        "scorecards_path": sc_rel,
        "ranking_path": rk_rel,
        "scorecards_live": sc_live,
        "ranking_live": rk_live,
        "winner_entry_id": winner,
        "reviewer_judge_id": sc_doc.get("reviewer_judge_id") or F.REVIEWER_JUDGE,
    }
