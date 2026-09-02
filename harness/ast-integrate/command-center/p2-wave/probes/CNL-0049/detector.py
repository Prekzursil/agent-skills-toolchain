#!/usr/bin/env python3
"""CNL-0049 steelman-happened detector.

Machine-checkable property: a turn (or turn sequence) is a genuine steelman
of opponent position P iff BOTH signals pass:

  S1 coverage (set algebra on claim ids + polarity + non-token body +
     content-token overlap with the source claim).
  S2 ordering (event sequence): no attack is emitted while S1 is incomplete.

The check FIRES when either signal fails (fake / token concession / strawman
label / attack-first). The check is SILENT when both pass.

Not the measure: byte length, the speech_act string "steelman", a concession
lexicon hit by itself, or original-author acceptance (that is IMP-0293).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "of",
        "to",
        "for",
        "in",
        "on",
        "is",
        "are",
        "be",
        "as",
        "that",
        "this",
        "it",
        "its",
        "by",
        "with",
        "from",
        "not",
        "no",
        "so",
        "than",
        "then",
        "into",
        "over",
        "under",
        "must",
        "should",
        "would",
        "can",
        "cannot",
        "only",
        "also",
        "their",
        "they",
        "them",
        "we",
        "you",
        "your",
        "i",
        "me",
        "my",
        "our",
        "at",
        "after",
        "before",
        "because",
        "about",
        "case",
        "strongest",
    }
)

# Bodies whose content tokens are only these fillers count as token concessions.
FILLER = frozenset(
    {
        "fair",
        "enough",
        "point",
        "good",
        "granted",
        "sure",
        "okay",
        "understand",
        "understood",
        "see",
        "hear",
        "agree",
        "concession",
        "fine",
        "right",
        "true",
        "yes",
        "however",
        "indeed",
        "noted",
        "thanks",
    }
)


def content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOP and len(w) > 2}


def is_token_body(text: str) -> bool:
    toks = content_tokens(text)
    if not toks:
        return True
    if toks <= FILLER:
        return True
    if len(toks) <= 1:
        return True
    return False


def load_bearing_claims(doc: dict[str, Any]) -> list[dict[str, Any]]:
    opp = doc.get("opponent") or {}
    claims = opp.get("claims") or []
    out = []
    for c in claims:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        if c.get("load_bearing", True):
            out.append(c)
    return out


def events_of(turn: dict[str, Any]) -> list[dict[str, Any]]:
    raw = turn.get("events")
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    events: list[dict[str, Any]] = []
    for r in turn.get("restatements") or []:
        if isinstance(r, dict):
            ev = dict(r)
            ev["kind"] = "restatement"
            events.append(ev)
    for a in turn.get("attacks") or []:
        if isinstance(a, dict):
            ev = dict(a)
            ev["kind"] = "attack"
            events.append(ev)
    return events


def restatement_binds(claim: dict[str, Any], ev: dict[str, Any]) -> bool:
    if ev.get("restates") != claim["id"]:
        return False
    if ev.get("polarity") != claim.get("polarity"):
        return False
    body = str(ev.get("text") or "")
    if is_token_body(body):
        return False
    src = content_tokens(str(claim.get("text") or ""))
    rst = content_tokens(body)
    if src and not (src & rst):
        return False
    return True


def evaluate(doc: dict[str, Any]) -> dict[str, Any]:
    claims = load_bearing_claims(doc)
    claim_ids = [c["id"] for c in claims]
    covered: set[str] = set()
    reasons: list[str] = []
    attack_before_coverage = False
    restatement_events = 0
    attack_events = 0

    turns = doc.get("turns") or []
    if not isinstance(turns, list):
        turns = []

    for i, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        for ev in events_of(turn):
            kind = ev.get("kind")
            if kind == "restatement":
                restatement_events += 1
                for c in claims:
                    if restatement_binds(c, ev):
                        covered.add(c["id"])
            elif kind == "attack":
                attack_events += 1
                missing = [cid for cid in claim_ids if cid not in covered]
                if missing:
                    attack_before_coverage = True
                    reasons.append(
                        f"turn[{i}]:attack-before-coverage missing={missing}"
                    )

    missing = [cid for cid in claim_ids if cid not in covered]
    coverage_ok = bool(claims) and not missing
    ordering_ok = not attack_before_coverage
    if not claims:
        reasons.append("no-load-bearing-claims")
        coverage_ok = False
    if missing:
        reasons.append(f"coverage-incomplete missing={missing}")

    fired = (not coverage_ok) or (not ordering_ok)
    return {
        "fired": fired,
        "silent": not fired,
        "verdict": "FAIL" if fired else "PASS",
        "coverage_ok": coverage_ok,
        "ordering_ok": ordering_ok,
        "covered_claim_ids": sorted(covered),
        "missing_claim_ids": missing,
        "claim_count": len(claims),
        "covered_count": len(covered),
        "restatement_events": restatement_events,
        "attack_events": attack_events,
        "reasons": reasons,
        "fixture_id": doc.get("id"),
    }


def evaluate_path(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = evaluate(doc)
    result["path"] = str(path)
    return result


def main() -> int:
    import sys

    if len(sys.argv) < 2:
        print("FAILED:detector usage detector.py <fixture.json>")
        return 2
    result = evaluate_path(Path(sys.argv[1]))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
