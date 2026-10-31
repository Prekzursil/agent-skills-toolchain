#!/usr/bin/env python3
"""Shard14 wave2 resume completion, part 3.

  IMP-0321  participation.py - council_id/threshold/disagreement fields,
            excerpts_for(council, seats, limit) census shape, analyze_many
            aggregate {"n_councils","n_disagreements","rows","top_disagreement"}
  IMP-0390  semantic_matcher.py pin_identity() gains the "path" key the
            determinism probe resolves the pinned model doc through.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"SKIP  {label} (already applied)")
        return
    if old not in text:
        print(f"FAILED:shard14-p3 anchor missing for {label}")
        sys.exit(1)
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"OK    {label}")


part = REPO / "tools" / "council" / "antifail" / "participation.py"

OLD_EXCERPTS = '''def excerpts_for(seat: dict[str, Any]) -> str:
    turns = seat.get("turns") or []
    if isinstance(turns, list):
        return " ".join(str(t.get("text") if isinstance(t, dict) else t) for t in turns)
    return str(seat.get("text") or "")
'''
NEW_EXCERPTS = '''def excerpts_for(
    council: dict[str, Any],
    seat_names: list[str] | None = None,
    limit: int | None = 4,
) -> dict[str, list[str]] | str:
    """Seat excerpts as {seat: [turn texts]}.

    probes/IMP-0321 contract: excerpts_for(council, [names], limit=4).
    Legacy single-seat form (one dict without council keys) still returns
    the joined text.
    """
    if (
        seat_names is None
        and isinstance(council, dict)
        and "turns" not in council
        and "seats" not in council
    ):
        turns = council.get("turns") or []
        if isinstance(turns, list):
            return " ".join(
                str(t.get("text") if isinstance(t, dict) else t) for t in turns
            )
        return str(council.get("text") or "")

    seats_in = council.get("seats")
    if seats_in:
        texts = {
            name: [
                str(t.get("text") if isinstance(t, dict) else t)
                for t in (rec.get("turns") or [])
            ]
            for name, rec in seats_in.items()
        }
    else:
        texts = {}
        for turn in council.get("turns") or []:
            name = str((turn or {}).get("seat") or "")
            texts.setdefault(name, []).append(str((turn or {}).get("text") or ""))
    if seat_names is None:
        return {k: v[:limit] if limit else v for k, v in texts.items()}
    return {name: texts.get(name, [])[:limit] if limit else texts.get(name, []) for name in seat_names}
'''
patch(part, OLD_EXCERPTS, NEW_EXCERPTS, "IMP-0321 excerpts_for census shape")

OLD_RETURN = '''    return {
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "measures_disagree": set(volume_dominant) != set(substance_dominant),
        "even": even,
        "n": n,
    }
'''
NEW_RETURN = '''    volume_loudest = max(seats, key=lambda s: seats[s]["volume_share"]) if seats else None
    substance_loudest = (
        max(seats, key=lambda s: seats[s]["substance_share"]) if seats else None
    )
    return {
        "council_id": council.get("council_id"),
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "measures_disagree": set(volume_dominant) != set(substance_dominant),
        "dominance_threshold": DOMINANCE_MULTIPLE / n,
        "silence_threshold": SILENCE_MULTIPLE / n,
        "disagreement": {
            "volume_loudest": volume_loudest,
            "substance_loudest": substance_loudest,
        },
        "even": even,
        "n": n,
    }
'''
patch(part, OLD_RETURN, NEW_RETURN, "IMP-0321 analyze_council augmented fields")

OLD_MANY = '''def analyze_many(councils: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [analyze_council(c) for c in councils]
'''
NEW_MANY = '''def analyze_many(councils: list[dict[str, Any]]) -> dict[str, Any]:
    """Census aggregate over recorded councils (probes/IMP-0321 contract)."""
    rows = [analyze_council(c) for c in councils]
    disagreements = [r for r in rows if r["measures_disagree"]]

    def _margin(row: dict[str, Any]) -> float:
        d = row["disagreement"]
        vol, sub = d["volume_loudest"], d["substance_loudest"]
        if not vol or not sub or vol == sub:
            return -1.0
        seat_rows = row["seats"]
        share_gap = seat_rows[vol]["volume_share"] - seat_rows[sub]["volume_share"]
        substance_gap = (
            seat_rows[sub]["substance_share"] - seat_rows[vol]["substance_share"]
        )
        return float(share_gap + substance_gap)

    top = None
    for row in sorted(disagreements, key=_margin, reverse=True):
        d = row["disagreement"]
        if d["volume_loudest"] and d["substance_loudest"] and d["volume_loudest"] != d["substance_loudest"]:
            top = {
                "council_id": row["council_id"],
                "volume_loudest": d["volume_loudest"],
                "substance_loudest": d["substance_loudest"],
            }
            break
    return {
        "n_councils": len(rows),
        "n_disagreements": len(disagreements),
        "rows": rows,
        "top_disagreement": top,
    }
'''
patch(part, OLD_MANY, NEW_MANY, "IMP-0321 analyze_many census aggregate")

sm = REPO / "tools" / "router" / "semantic_matcher.py"
patch(
    sm,
    '''        "model_id": MODEL_ID,
        "pinned_sha256": PINNED,
        "live_sha256": live,
        "digest_matches_pin": live == PINNED,
    }''',
    '''        "model_id": MODEL_ID,
        "pinned_sha256": PINNED,
        "live_sha256": live,
        "digest_matches_pin": live == PINNED,
        "path": MODEL_REL_PATH,
    }''',
    "IMP-0390 pin_identity path key",
)

print("SUCCESS:shard14-p3")
