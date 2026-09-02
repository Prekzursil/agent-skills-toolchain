"""Lost-dissent detector: mechanical transcript-vs-synthesis diff.

Dissent is harvested only from the transcript (turns, votes, minority
records). Coverage is harvested only from the synthesis body. The
synthesizer's self-attestation is ignored. A dissent is lost when its
content-token set is not covered by the synthesis. That is a computed
set-difference, not a judgement by the agent that dropped the claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PATHOLOGY = "lost-dissent"
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "their",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "with",
        "yes",
    }
)
DISSENT_KINDS = frozenset(
    {
        "dissent",
        "minority_report",
        "minority",
        "objection",
        "dissenting_vote_reason",
    }
)
DISSENT_STANCES = frozenset({"against", "dissent", "oppose", "no", "nay"})
AGAINST_VOTES = frozenset({"against", "no", "nay", "oppose", "dissent"})
COVERAGE_THRESHOLD = 0.8
MIN_CONTENT_TOKENS = 5

_CONTROL_FIRED = False


def tokens(text: str) -> set[str]:
    found = TOKEN_RE.findall((text or "").lower())
    return {t for t in found if t not in STOP and len(t) > 1}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key in (
            "text",
            "body",
            "reason",
            "claim",
            "summary",
            "recommendation",
            "minority_report",
        ):
            if key in value:
                parts.append(_blob(value[key]))
        for item in value.get("minority_reports") or []:
            parts.append(_blob(item))
        for item in value.get("acknowledged_dissent") or []:
            parts.append(_blob(item))
        return "\n".join(p for p in parts if p)
    if isinstance(value, list):
        return "\n".join(_blob(x) for x in value)
    return str(value)


def _record_id(prefix: str, speaker: str, text: str, explicit: str | None) -> str:
    if explicit:
        return str(explicit)
    digest = hashlib.sha256(f"{speaker}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def extract_transcript_dissent(council: dict) -> list[dict]:
    """Harvest dissent from the transcript only. Synthesis is never a source."""
    transcript = council.get("transcript") or {}
    if not isinstance(transcript, dict):
        transcript = {}
    seen: dict[str, dict] = {}

    def add(rec: dict) -> None:
        did = rec["dissent_id"]
        if did in seen:
            prev = seen[did]
            if len(rec.get("text") or "") > len(prev.get("text") or ""):
                seen[did] = rec
            return
        seen[did] = rec

    for turn in _as_list(transcript.get("turns") or council.get("turns")):
        if not isinstance(turn, dict):
            continue
        kind = str(turn.get("kind") or turn.get("kind") or turn.get("type") or "").lower()
        stance = str(turn.get("stance") or "").lower()
        flagged = bool(turn.get("is_dissent") or turn.get("dissent"))
        if kind not in DISSENT_KINDS and stance not in DISSENT_STANCES and not flagged:
            continue
        text = _blob(turn.get("text") or turn.get("body") or turn.get("claim") or "")
        speaker = str(turn.get("speaker") or turn.get("role") or "unknown")
        did = _record_id(
            "d",
            speaker,
            text,
            turn.get("dissent_id") or turn.get("id") or turn.get("claim_id"),
        )
        add(
            {
                "dissent_id": did,
                "claim_id": str(turn.get("claim_id") or did),
                "speaker": speaker,
                "source": "turn",
                "text": text,
                "tokens": sorted(tokens(text)),
            }
        )

    for vote in _as_list(transcript.get("votes") or council.get("votes")):
        if not isinstance(vote, dict):
            continue
        ballot = str(vote.get("vote") or vote.get("ballot") or "").lower()
        if ballot not in AGAINST_VOTES:
            continue
        text = _blob(vote.get("reason") or vote.get("text") or vote.get("claim") or "")
        speaker = str(vote.get("speaker") or vote.get("role") or "unknown")
        explicit = vote.get("dissent_id") or vote.get("claim_id")
        did = _record_id("v", speaker, text, explicit)
        add(
            {
                "dissent_id": did,
                "claim_id": str(vote.get("claim_id") or did),
                "speaker": speaker,
                "source": "vote",
                "text": text,
                "tokens": sorted(tokens(text)),
            }
        )

    for report in _as_list(
        transcript.get("minority_reports") or transcript.get("minority_reports") or []
    ):
        if not isinstance(report, dict):
            continue
        text = _blob(report.get("text") or report.get("body") or report)
        speaker = str(report.get("speaker") or report.get("author") or "unknown")
        did = _record_id(
            "m",
            speaker,
            text,
            report.get("dissent_id") or report.get("id"),
        )
        add(
            {
                "dissent_id": did,
                "claim_id": str(report.get("claim_id") or did),
                "speaker": speaker,
                "source": "minority_report",
                "text": text,
                "tokens": sorted(tokens(text)),
            }
        )

    return list(seen.values())


def synthesis_text(council: dict) -> str:
    syn = council.get("synthesis") or {}
    return _blob(syn)


def synthesis_acknowledged_ids(council: dict) -> set[str]:
    syn = council.get("synthesis") or {}
    if not isinstance(syn, dict):
        return set()
    ids: set[str] = set()
    for key in (
        "acknowledged_dissent_ids",
        "acknowledged_dissent_ids",
        "minority_report_ids",
        "preserved_dissent_ids",
    ):
        for item in _as_list(syn.get(key)):
            ids.add(str(item))
    for item in _as_list(syn.get("minority_reports")):
        if isinstance(item, dict):
            for key in ("dissent_id", "id", "claim_id"):
                if item.get(key):
                    ids.add(str(item[key]))
    return ids


def self_attestation_healthy(council: dict) -> bool | None:
    syn = council.get("synthesis") or {}
    if not isinstance(syn, dict):
        return None
    att = (
        syn.get("self_attestation")
        or syn.get("self_attestation")
        or syn.get("attestation")
        or {}
    )
    if not isinstance(att, dict):
        return None
    for key in (
        "all_dissent_preserved",
        "all_dissent_preserved",
        "all_dissent_healthy",
        "no_lost_dissent",
        "healthy",
    ):
        if key in att:
            return bool(att[key])
    return None


def body_coverage(dissent_tokens: set[str], syn_tokens: set[str]) -> float:
    if not dissent_tokens:
        return 0.0
    return len(dissent_tokens & syn_tokens) / len(dissent_tokens)


def body_appears(dissent: dict, syn_tokens: set[str], syn_text: str) -> bool:
    dtoks = set(dissent.get("tokens") or [])
    if len(dtoks) < MIN_CONTENT_TOKENS:
        needle = re.sub(r"\s+", " ", (dissent.get("text") or "").strip().lower())
        if not needle:
            return False
        return needle in re.sub(r"\s+", " ", syn_text.lower())
    return body_coverage(dtoks, syn_tokens) >= COVERAGE_THRESHOLD


def detect(council: dict) -> dict:
    """Return a computed diff. Never consults synthesizer self-attestation."""
    dissent = extract_transcript_dissent(council)
    syn_text = synthesis_text(council)
    syn_tokens = tokens(syn_text)
    ack_ids = synthesis_acknowledged_ids(council)
    lost = []
    preserved = []
    for rec in dissent:
        dtoks = set(rec.get("tokens") or [])
        cov = body_coverage(dtoks, syn_tokens) if dtoks else 0.0
        appears = body_appears(rec, syn_tokens, syn_text)
        id_present = rec["dissent_id"] in ack_ids or rec["claim_id"] in ack_ids
        row = {
            "dissent_id": rec["dissent_id"],
            "claim_id": rec["claim_id"],
            "speaker": rec["speaker"],
            "source": rec["source"],
            "text": rec["text"],
            "id_listed_in_synthesis": id_present,
            "content_token_coverage": round(cov, 4),
            "content_appears_in_synthesis": appears,
        }
        if appears:
            preserved.append(row)
        else:
            row["why"] = (
                "transcript dissent content-token set is not covered by the "
                "synthesis body (computed diff; synthesizer judgement unused)"
            )
            lost.append(row)
    fired = bool(lost)
    attestation = self_attestation_healthy(council)
    return {
        "pathology": PATHOLOGY,
        "fixture_id": council.get("id"),
        "fired": fired,
        "silent": not fired,
        "transcript_dissent_count": len(dissent),
        "lost_count": len(lost),
        "preserved_count": len(preserved),
        "lost_ids": [r["dissent_id"] for r in lost],
        "preserved_ids": [r["dissent_id"] for r in preserved],
        "lost": lost,
        "preserved": preserved,
        "ignored_synthesizer_self_attestation": True,
        "synthesizer_self_attestation_healthy": attestation,
        "signals": [
            "transcript-only dissent harvest",
            "synthesis content-token coverage (threshold "
            f"{COVERAGE_THRESHOLD}, min {MIN_CONTENT_TOKENS} tokens)",
        ],
        "coverage_threshold": COVERAGE_THRESHOLD,
    }


def detect_path(path: Path) -> dict:
    council = json.loads(path.read_text(encoding="utf-8"))
    result = detect(council)
    result["fixture_path"] = str(path)
    result["fixture_id"] = council.get("id") or path.stem
    return result


def detector_control_known_present(council: dict) -> dict:
    """Must FIRE on a known-present pathology before any absence is reported."""
    global _CONTROL_FIRED
    result = detect(council)
    if result["fired"]:
        _CONTROL_FIRED = True
    result["detector_control_known_present"] = True
    return result


def detect_after_control(council: dict) -> dict:
    if not _CONTROL_FIRED:
        raise RuntimeError(
            "detector-control: refusing to report absence before a known-present "
            "instance has fired in this process"
        )
    return detect(council)


def reset_control() -> None:
    global _CONTROL_FIRED
    _CONTROL_FIRED = False


def false_positive_rate(results: list[dict]) -> dict:
    """FP = fires on a fixture labelled clean. Reported as a number."""
    n = len(results)
    if n < 1:
        raise ValueError("false_positive_rate requires at least one clean fixture")
    fires = [r for r in results if r.get("fired")]
    return {
        "value": len(fires) / n,
        "numerator": len(fires),
        "denominator": n,
        "fired_ids": [r.get("fixture_id") for r in fires],
        "fixture_ids": [r.get("fixture_id") for r in results],
    }
