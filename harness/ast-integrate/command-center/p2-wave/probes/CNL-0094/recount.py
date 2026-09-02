"""Independent recount: sha256+registry join without calling detector.detect."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recount(fixture_root: Path) -> dict[str, Any]:
    root = Path(fixture_root)
    council = json.loads((root / "council.json").read_text(encoding="utf-8"))
    registry = council.get("evidence_registry") or {}
    ballots = [b for b in (council.get("ballots") or []) if isinstance(b, dict)]
    counting_ids: list[str] = []
    non_counting: list[dict[str, Any]] = []
    counting_positions: list[str] = []
    raw_positions: list[str] = []
    for b in ballots:
        vid = str(b.get("voter_id") or b.get("voter_id") or "")
        pos = str(b.get("position") or "")
        raw_positions.append(pos)
        ok = False
        why = "empty-attachment"
        for att in b.get("evidence") or []:
            if not isinstance(att, dict):
                why = "empty-attachment"
                continue
            eid = str(att.get("id") or "").strip()
            rec = registry.get(eid) if eid else None
            if not eid:
                why = "empty-attachment"
                continue
            if not isinstance(rec, dict):
                why = "unknown-id"
                continue
            rel = str(rec.get("path") or rec.get("path") or "").replace("\\", "/").lstrip("/")
            fpath = root / rel
            if not rel or not fpath.is_file():
                why = "missing-file"
                continue
            digest = _digest(fpath)
            if digest != str(rec.get("sha256") or ""):
                why = "digest-mismatch"
                continue
            if str(rec.get("supports") or "") != pos:
                why = "support-mismatch"
                continue
            ok = True
            why = "ok"
            break
        if ok:
            counting_ids.append(vid)
            counting_positions.append(pos)
        else:
            non_counting.append({"voter_id": vid, "position": pos, "reason": why})
    raw = Counter(raw_positions)
    cnt = Counter(counting_positions)
    n = len(ballots)
    raw_majority = None
    if n and raw:
        winner, count = raw.most_common(1)[0]
        tied = len(raw) > 1 and raw.most_common(2)[1][1] == count
        if count > n / 2 and not tied:
            raw_majority = winner
    majority_counting = cnt.get(raw_majority, 0) if raw_majority else 0
    fired = bool(raw_majority is not None and majority_counting == 0)
    outcome = None
    if cnt:
        ow, oc = cnt.most_common(1)[0]
        otied = len(cnt) > 1 and cnt.most_common(2)[1][1] == oc
        if oc > 0 and not otied:
            outcome = ow
    return {
        "council_id": council.get("council_id"),
        "method": "sha256-join-without-detector.detect",
        "fired": fired,
        "silent": not fired,
        "raw_tally": dict(raw),
        "counting_tally": dict(cnt),
        "raw_majority": raw_majority,
        "counting_ids": counting_ids,
        "non_counting": non_counting,
        "n_ballots": n,
        "n_counting": len(counting_ids),
        "outcome": outcome or "NOT-BINDING",
    }
