#!/usr/bin/env python3
"""CNL-0015: represent expertise as a checkable claim, never as a weight input.

A free-text self-assertion is stored (audit) but is never load-bearing.
The selector may apply an expertise weight premium only after the evidence
bar PASSES for the specific task tag. Scores are computed from the pointed
probe file; claimed n_correct on the claim object is ignored.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Closed vocabulary: a tag outside this set fails closed. Invention of
# "universal-expert" as a tag is not a way around the bar.
CLOSED_VOCAB = frozenset(
    {
        "compiler-design",
        "cryptography",
        "distributed-systems",
        "incident-response",
        "numerical-analysis",
        "privacy-law",
        "tls",
    }
)

UNANSWERABLE_PASS = "idk"
MIN_VERIFIABLE = 3
FABRICATED_REASONS = frozenset(
    {
        "no-evidence",
        "self-assertion-only",
        "unknown-tag",
        "tag-not-claimed",
        "pointer-missing",
        "hash-mismatch",
        "hash-absent",
        "probe-too-small",
        "unanswerable-not-idk",
        "unanswerable-absent",
        "at-or-below-baseline",
        "probe-tag-mismatch",
        "empty-artifact",
        "kind-unknown",
        "all-evidence-rejected",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bind_live_hashes(claim: dict, repo: Path = REPO) -> dict:
    """Fill content_sha256 from the pointed file when bind_live_hash is true."""
    out = json.loads(json.dumps(claim))
    for item in out.get("evidence") or []:
        if item.get("bind_live_hash") and item.get("pointer"):
            p = repo / str(item["pointer"])
            if p.is_file():
                item["content_sha256"] = digest_file(p)
    return out


def score_probe_file(doc: dict) -> dict:
    """Independent of the claim object: count answers in the pointed file."""
    verifiable = list(doc.get("verifiable") or [])
    baseline = list(doc.get("baseline") or [])
    ua = doc.get("unanswerable") if isinstance(doc.get("unanswerable"), dict) else {}
    n_v = len(verifiable)
    n_c = sum(1 for q in verifiable if q.get("got") == q.get("expected"))
    n_b = sum(1 for q in baseline if q.get("got") == q.get("expected"))
    return {
        "domain_tag": doc.get("domain_tag"),
        "n_verifiable": n_v,
        "n_correct": n_c,
        "baseline_correct": n_b,
        "margin": n_c - n_b,
        "unanswerable_got": ua.get("got"),
        "unanswerable_expected": ua.get("expected", UNANSWERABLE_PASS),
    }


def _fail(reason: str, **extra: Any) -> dict:
    row = {
        "pass": False,
        "weight_eligible": False,
        "reason": reason,
        "margin": 0,
        "kind": None,
    }
    row.update(extra)
    return row


def _pass(reason: str, kind: str, margin: int, **extra: Any) -> dict:
    row = {
        "pass": True,
        "weight_eligible": True,
        "reason": reason,
        "margin": int(margin),
        "kind": kind,
    }
    row.update(extra)
    return row


def _check_item(item: dict, tag: str, repo: Path) -> dict:
    kind = str(item.get("kind") or "")
    pointer = str(item.get("pointer") or "")
    claimed_hash = str(item.get("content_sha256") or "")
    if not pointer:
        return _fail("pointer-missing", kind=kind or None)
    path = repo / pointer
    if not path.is_file():
        return _fail("pointer-missing", kind=kind or None, pointer=pointer)
    live = digest_file(path)
    if not claimed_hash:
        return _fail("hash-absent", kind=kind or None, pointer=pointer, live_sha256=live)
    if claimed_hash != live:
        return _fail(
            "hash-mismatch",
            kind=kind or None,
            pointer=pointer,
            claimed_sha256=claimed_hash,
            live_sha256=live,
        )
    raw = load_json(path)
    if kind == "competence_probe":
        scored = score_probe_file(raw)
        if scored.get("domain_tag") != tag:
            return _fail("probe-tag-mismatch", kind=kind, pointer=pointer, scored=scored)
        if int(scored["n_verifiable"]) < MIN_VERIFIABLE:
            return _fail("probe-too-small", kind=kind, pointer=pointer, scored=scored)
        if scored.get("unanswerable_got") is None:
            return _fail("unanswerable-absent", kind=kind, pointer=pointer, scored=scored)
        if scored.get("unanswerable_got") != UNANSWERABLE_PASS:
            return _fail("unanswerable-not-idk", kind=kind, pointer=pointer, scored=scored)
        if int(scored["n_correct"]) <= int(scored["baseline_correct"]):
            return _fail("at-or-below-baseline", kind=kind, pointer=pointer, scored=scored)
        return _pass(
            "competence_probe",
            kind,
            int(scored["margin"]),
            pointer=pointer,
            scored=scored,
            live_sha256=live,
        )
    if kind == "calibration_record":
        hist = float(raw.get("historical_accuracy"))
        base = float(raw.get("baseline_accuracy"))
        rec_tag = raw.get("domain_tag")
        if rec_tag != tag:
            return _fail("probe-tag-mismatch", kind=kind, pointer=pointer)
        if hist <= base:
            return _fail("at-or-below-baseline", kind=kind, pointer=pointer, historical_accuracy=hist, baseline_accuracy=base)
        margin = int(round((hist - base) * 100))
        return _pass("calibration_record", kind, margin, pointer=pointer, live_sha256=live)
    if kind == "attested_artifact":
        if path.stat().st_size <= 0:
            return _fail("empty-artifact", kind=kind, pointer=pointer)
        rec_tag = raw.get("domain_tag") if isinstance(raw, dict) else None
        if rec_tag != tag:
            return _fail("probe-tag-mismatch", kind=kind, pointer=pointer)
        return _pass("attested_artifact", kind, 1, pointer=pointer, live_sha256=live)
    return _fail("kind-unknown", kind=kind or None)


def evidence_bar(claim: dict, tag: str, repo: Path = REPO) -> dict:
    """Return whether this claim may be weighted for `tag`.

    Self-assertion text is ignored. Empty evidence is fabricated expertise.
    """
    assertion = str(claim.get("assertion") or "")
    tags = [str(t) for t in (claim.get("domain_tags") or [])]
    if tag not in CLOSED_VOCAB:
        return _fail("unknown-tag", assertion_present=bool(assertion))
    if tag not in tags:
        return _fail("tag-not-claimed", assertion_present=bool(assertion), domain_tags=tags)
    items = [
        e
        for e in (claim.get("evidence") or [])
        if isinstance(e, dict) and str(e.get("domain_tag") or "") == tag
    ]
    if not items:
        reason = "self-assertion-only" if assertion and not (claim.get("evidence") or []) else "no-evidence"
        return _fail(reason, assertion_present=bool(assertion), domain_tags=tags)
    rejections: list[str] = []
    for item in items:
        row = _check_item(item, tag, repo)
        if row["pass"]:
            row["participant_id"] = claim.get("participant_id")
            row["assertion_present"] = bool(assertion)
            row["assertion_is_load_bearing"] = False
            return row
        rejections.append(str(row.get("reason")))
    return _fail(
        "all-evidence-rejected",
        assertion_present=bool(assertion),
        rejected_reasons=rejections,
        participant_id=claim.get("participant_id"),
    )


def match_task(task: dict, claims: list[dict], repo: Path = REPO) -> dict:
    """Checkable match: set intersection of task tags with bar-passing claims.

    Uncovered tags stay uncovered. A failed bar never contributes weight.
    """
    required = [str(t) for t in (task.get("required_tags") or [])]
    covered: dict[str, list[dict]] = {}
    uncovered: list[str] = []
    rejected: list[dict] = []
    for tag in required:
        eligible: list[dict] = []
        for claim in claims:
            bound = bind_live_hashes(claim, repo)
            bar = evidence_bar(bound, tag, repo)
            row = {
                "participant_id": bound.get("participant_id"),
                "tag": tag,
                "pass": bar["pass"],
                "reason": bar["reason"],
                "margin": bar.get("margin") or 0,
                "kind": bar.get("kind"),
            }
            if bar["pass"]:
                eligible.append(row)
            elif tag in [str(t) for t in (bound.get("domain_tags") or [])]:
                rejected.append(row)
        if not eligible:
            uncovered.append(tag)
        else:
            eligible.sort(key=lambda r: (-int(r["margin"]), str(r["participant_id"])))
            covered[tag] = eligible
    weighted = []
    for tag, rows in covered.items():
        top = rows[0]
        weighted.append(
            {
                "participant_id": top["participant_id"],
                "tag": tag,
                "margin": top["margin"],
                "weight_premium": True,
                "rank": 1,
            }
        )
    return {
        "required_tags": required,
        "covered_tags": sorted(covered),
        "uncovered_tags": uncovered,
        "weighted": weighted,
        "rejected": rejected,
        "weight_premium_applied": bool(weighted),
    }


def weight_for(selection: dict, participant_id: str, tag: str) -> bool:
    for row in selection.get("weighted") or []:
        if row.get("participant_id") == participant_id and row.get("tag") == tag:
            return bool(row.get("weight_premium"))
    return False
