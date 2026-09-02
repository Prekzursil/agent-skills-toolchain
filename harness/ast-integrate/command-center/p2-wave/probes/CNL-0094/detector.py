"""Evidence-free majority blocker.

A ballot COUNTS only when it binds at least one resolvable evidence node.
A raw majority whose counting-ballot count is zero does not bind.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


COUNTING_RULE = (
    "A vote counts iff at least one registry id resolves to an on-disk file "
    "whose sha256 matches the registry and whose supports equals the ballot "
    "position."
)

NON_COUNTING = (
    "empty-attachment",
    "unknown-id",
    "missing-file",
    "digest-mismatch",
    "support-mismatch",
)


def repo_root(start: Path | None = None) -> Path:
    here = start or Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise RuntimeError("repo root not found")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_council(fixture_root: Path) -> dict[str, Any]:
    path = fixture_root / "council.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _attachment_ok(
    ballot: dict[str, Any],
    att: dict[str, Any],
    registry: dict[str, Any],
    fixture_root: Path,
) -> tuple[bool, str]:
    eid = str(att.get("id") or "").strip()
    if not eid:
        return False, "empty-attachment"
    rec = registry.get(eid)
    if not isinstance(rec, dict):
        return False, "unknown-id"
    rel = str(rec.get("path") or rec.get("path") or "").replace("\\", "/").lstrip("/")
    if not rel:
        return False, "missing-file"
    fpath = fixture_root / rel
    if not fpath.is_file():
        return False, "missing-file"
    digest = sha256_bytes(fpath.read_bytes())
    claimed = str(rec.get("sha256") or "")
    if not claimed or claimed != digest:
        return False, "digest-mismatch"
    att_sha = str(att.get("sha256") or "")
    if att_sha and att_sha != digest:
        return False, "digest-mismatch"
    supports = str(rec.get("supports") or "")
    position = str(ballot.get("position") or "")
    if not supports or supports != position:
        return False, "support-mismatch"
    return True, "ok"


def ballot_status(
    ballot: dict[str, Any],
    registry: dict[str, Any],
    fixture_root: Path,
) -> dict[str, Any]:
    attachments = ballot.get("evidence") or []
    if not isinstance(attachments, list) or not attachments:
        return {
            "voter_id": ballot.get("voter_id") or ballot.get("voter_id"),
            "position": ballot.get("position"),
            "counting": False,
            "reasons": ["empty-attachment"],
        }
    reasons: list[str] = []
    counting = False
    for att in attachments:
        if not isinstance(att, dict):
            reasons.append("empty-attachment")
            continue
        ok, why = _attachment_ok(ballot, att, registry, fixture_root)
        if ok:
            counting = True
        else:
            reasons.append(why)
    if counting:
        reasons = ["ok"]
    elif not reasons:
        reasons = ["empty-attachment"]
    return {
        "voter_id": ballot.get("voter_id") or ballot.get("voter_id"),
        "position": ballot.get("position"),
        "counting": counting,
        "reasons": reasons,
    }


def _unique_majority(counter: Counter[str], n: int) -> str | None:
    if n <= 0:
        return None
    if not counter:
        return None
    top = counter.most_common()
    winner, count = top[0]
    if count <= n / 2:
        return None
    if len(top) > 1 and top[1][1] == count:
        return None
    return winner


def _unique_plurality(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    top = counter.most_common()
    winner, count = top[0]
    if count <= 0:
        return None
    if len(top) > 1 and top[1][1] == count:
        return None
    return winner


def detect(fixture_root: Path) -> dict[str, Any]:
    """FIRE when a strict raw majority has zero counting ballots.

    Outcome is the unique plurality of counting ballots, else NOT-BINDING.
    Unbacked votes never decide.
    """
    root = Path(fixture_root)
    council = load_council(root)
    registry = council.get("evidence_registry") or {}
    if not isinstance(registry, dict):
        registry = {}
    ballots = council.get("ballots") or []
    if not isinstance(ballots, list):
        ballots = []

    statuses = [ballot_status(b, registry, root) for b in ballots if isinstance(b, dict)]
    raw = Counter(str(s["position"]) for s in statuses)
    counting_rows = [s for s in statuses if s["counting"]]
    counting = Counter(str(s["position"]) for s in counting_rows)
    n = len(statuses)
    raw_majority = _unique_majority(raw, n)
    majority_counting = 0
    if raw_majority is not None:
        majority_counting = sum(
            1 for s in counting_rows if str(s["position"]) == raw_majority
        )
    fired = bool(raw_majority is not None and majority_counting == 0)
    counting_outcome = _unique_plurality(counting)
    if counting_outcome is None:
        outcome = "NOT-BINDING"
    else:
        outcome = counting_outcome
    return {
        "council_id": council.get("council_id"),
        "fired": fired,
        "silent": not fired,
        "raw_tally": dict(raw),
        "counting_tally": dict(counting),
        "raw_majority": raw_majority,
        "counting_majority_of_raw_winner": majority_counting,
        "n_ballots": n,
        "n_counting": len(counting_rows),
        "outcome": outcome,
        "ballots": statuses,
        "pathology": "EVIDENCE-FREE-MAJORITY" if fired else None,
        "rule": (
            "A vote counts iff at least one registry id resolves to an on-disk "
            "file whose sha256 matches the registry and whose supports equals "
            "the ballot position. A strict raw majority with zero counting "
            "ballots is EVIDENCE-FREE-MAJORITY: it does not bind. Remaining "
            "counting ballots are retallied; unique plurality wins, else "
            "NOT-BINDING."
        ),
    }
