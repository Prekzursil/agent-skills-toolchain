"""CNL-0070 minority-report generation and mandatory preservation.

The check FIRES when a recorded dissent is omitted, unattributed, or
collapsed to a footnote in the synthesis minority_report. It is SILENT
only when every transcript dissent_id is present as a keyed object with
required fields, attribution, claim substance, and verbatim token.

Signal 1 is set-difference on dissent_id. Signal 2 is claim/token
substance (a different field, not a second reading of the same set).
"""
from __future__ import annotations

import json
from typing import Any

REQUIRED_FIELDS = (
    "dissent_id",
    "participant_id",
    "claim",
    "evidence",
    "verbatim_token",
)
FOOTNOTE_CLAIMS = frozenset(
    {
        "dissent noted",
        "minority views were considered",
        "some disagreement was recorded",
        "dissent was recorded",
        "see above",
    }
)
DISSENT_TURN_KINDS = frozenset(
    {"dissent", "minority-report", "forced-dissent", "vote-against"}
)
DISSENT_VOTE_VALUES = frozenset({"no", "against", "dissent", "nay", "block"})
MANDATORY_PROTOCOL_MARKERS = frozenset(
    {"P56", "p56", "minority-report-mandatory", "P56 minority-report-mandatory"}
)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("dissents", "items", "entries", "rows"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
        return [value]
    return []


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _is_footnote(claim: str) -> bool:
    return _norm(claim).lower() in FOOTNOTE_CLAIMS


def collect_transcript_dissents(bundle: dict) -> list[dict]:
    """Every dissent the transcript actually recorded (id required)."""
    found: dict[str, dict] = {}
    transcript = bundle.get("transcript") or {}

    def add(raw: dict, source: str) -> None:
        if not isinstance(raw, dict):
            return
        did = _norm(raw.get("dissent_id"))
        if not did:
            return
        row = {
            "dissent_id": did,
            "participant_id": _norm(raw.get("participant_id") or raw.get("seat")),
            "claim": _norm(raw.get("claim") or raw.get("position")),
            "evidence": _norm(raw.get("evidence") or raw.get("cited_turn")),
            "verbatim_token": _norm(raw.get("verbatim_token") or raw.get("token")),
            "source": source,
        }
        prev = found.get(did)
        if prev is None:
            found[did] = row
            return
        for key in ("participant_id", "claim", "evidence", "verbatim_token"):
            if not prev.get(key) and row.get(key):
                prev[key] = row[key]

    for item in _as_list(transcript.get("dissents")):
        add(item, "transcript.dissents")
    for turn in _as_list(transcript.get("turns")):
        if not isinstance(turn, dict):
            continue
        kind = _norm(turn.get("kind")).lower()
        if kind in DISSENT_TURN_KINDS or turn.get("dissent_id"):
            add(turn, "transcript.turns")
    for vote in _as_list(transcript.get("votes") or bundle.get("votes")):
        if not isinstance(vote, dict):
            continue
        val = _norm(vote.get("vote") or vote.get("value")).lower()
        if val in DISSENT_VOTE_VALUES or vote.get("dissent_id"):
            add(vote, "transcript.votes")
    return [found[k] for k in sorted(found)]


def collect_report_dissents(bundle: dict) -> list[dict]:
    synthesis = bundle.get("synthesis") or {}
    outcome = bundle.get("outcome") or synthesis.get("outcome") or {}
    report = (
        synthesis.get("minority_report")
        if "minority_report" in synthesis
        else None
    )
    if report is None:
        report = outcome.get("minority_report") if isinstance(outcome, dict) else None
    rows = []
    for item in _as_list(report):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "dissent_id": _norm(item.get("dissent_id")),
                "participant_id": _norm(item.get("participant_id") or item.get("seat")),
                "claim": _norm(item.get("claim") or item.get("position")),
                "evidence": _norm(item.get("evidence") or item.get("cited_turn")),
                "verbatim_token": _norm(item.get("verbatim_token") or item.get("token")),
                "raw": item,
            }
        )
    return rows


def ballot_unanimous(bundle: dict) -> bool:
    votes = _as_list((bundle.get("transcript") or {}).get("votes") or bundle.get("votes"))
    values = set()
    for vote in votes:
        if not isinstance(vote, dict):
            continue
        val = _norm(vote.get("vote") or vote.get("value")).lower()
        if val:
            values.add(val)
    if not values:
        return not collect_transcript_dissents(bundle)
    return len(values) == 1 and next(iter(values)) not in DISSENT_VOTE_VALUES


def protocol_markers(bundle: dict) -> set[str]:
    markers: set[str] = set()
    for item in _as_list(bundle.get("protocols")):
        if isinstance(item, str):
            markers.add(item)
        elif isinstance(item, dict):
            for key in ("id", "name", "slug"):
                if item.get(key):
                    markers.add(str(item[key]))
    return markers


def minority_report_mandatory(bundle: dict) -> bool:
    """When a keyed minority_report is required (empty array is a drop if dissents exist)."""
    recorded = collect_transcript_dissents(bundle)
    if recorded:
        return True
    unanimous = ballot_unanimous(bundle)
    markers = protocol_markers(bundle)
    if markers & MANDATORY_PROTOCOL_MARKERS and not unanimous:
        return True
    stopping = bundle.get("stopping") or {}
    if stopping.get("mandatory_minority_report") and not unanimous:
        return True
    voting = bundle.get("voting") or (bundle.get("transcript") or {}).get("voting") or {}
    if _norm(voting.get("rule")) == "unanimous-or-record-dissent" and not unanimous:
        return True
    outcome = bundle.get("outcome") or (bundle.get("synthesis") or {}).get("outcome") or {}
    variant = _norm(
        outcome.get("variant") if isinstance(outcome, dict) else outcome
    )
    if variant == "dissent-with-minority-report":
        return True
    return False


def check(bundle: dict) -> dict:
    recorded = collect_transcript_dissents(bundle)
    reported = collect_report_dissents(bundle)
    rec_ids = {d["dissent_id"] for d in recorded if d.get("dissent_id")}
    rep_ids = {d["dissent_id"] for d in reported if d.get("dissent_id")}
    missing_ids = sorted(rec_ids - rep_ids)
    extra_ids = sorted(rep_ids - rec_ids)
    by_report = {d["dissent_id"]: d for d in reported if d.get("dissent_id")}

    capture_failures: list[str] = []
    if not ballot_unanimous(bundle) and not recorded:
        capture_failures.append(
            "non-unanimous-ballot-with-no-dissent-id (capture failed before preservation)"
        )

    unattributed: list[str] = []
    footnote: list[str] = []
    token_missing: list[str] = []
    claim_dropped: list[str] = []
    field_missing: list[dict] = []

    for rec in recorded:
        did = rec["dissent_id"]
        row = by_report.get(did)
        if row is None:
            continue
        blob = json.dumps(row.get("raw") or row, sort_keys=True, ensure_ascii=True)
        for field in REQUIRED_FIELDS:
            if not _norm(row.get(field)):
                field_missing.append({"dissent_id": did, "field": field})
        if not _norm(row.get("participant_id")):
            unattributed.append(did)
        if _is_footnote(row.get("claim") or ""):
            footnote.append(did)
        token = rec.get("verbatim_token") or ""
        if token and token not in blob:
            token_missing.append(did)
        tclaim = rec.get("claim") or ""
        rclaim = row.get("claim") or ""
        if tclaim and tclaim not in rclaim:
            claim_dropped.append(did)

    mandatory = minority_report_mandatory(bundle)
    empty_when_mandatory = bool(mandatory and rec_ids and not rep_ids)
    fired = bool(
        missing_ids
        or unattributed
        or footnote
        or token_missing
        or claim_dropped
        or field_missing
        or capture_failures
        or empty_when_mandatory
    )
    return {
        "fired": fired,
        "silent": not fired,
        "mandatory": mandatory,
        "unanimous": ballot_unanimous(bundle),
        "conservation": {
            "transcript_ids": sorted(rec_ids),
            "report_ids": sorted(rep_ids),
            "missing_ids": missing_ids,
            "extra_ids": extra_ids,
            "empty_difference": not missing_ids,
        },
        "unattributed_ids": unattributed,
        "footnote_ids": footnote,
        "token_missing_ids": token_missing,
        "claim_dropped_ids": claim_dropped,
        "field_missing": field_missing,
        "capture_failures": capture_failures,
        "empty_when_mandatory": empty_when_mandatory,
        "recorded_count": len(recorded),
        "reported_count": len(reported),
        "signals": ["dissent_id-set-difference", "claim-and-verbatim-token"],
    }


def plant_drop(bundle: dict, dissent_id: str | None = None) -> dict:
    """Return a copy of bundle whose synthesis omits one recorded dissent."""
    clone = json.loads(json.dumps(bundle))
    recorded = collect_transcript_dissents(clone)
    if not recorded:
        raise ValueError("plant_drop requires a recorded dissent")
    target = dissent_id or recorded[0]["dissent_id"]
    synthesis = clone.setdefault("synthesis", {})
    report = [
        row
        for row in _as_list(synthesis.get("minority_report"))
        if isinstance(row, dict) and _norm(row.get("dissent_id")) != target
    ]
    synthesis["minority_report"] = report
    return clone
