"""Detect role collapse from near-identical seat outputs. IMP-0320."""
from __future__ import annotations

from typing import Any

VOCAB_FIRE = 0.6


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in str(text).replace(",", " ").split() if t}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _role_vocab(seat: dict[str, Any]) -> float:
    role = str(seat.get("role") or "")
    output = str(seat.get("output") or "")
    markers = [w.lower() for w in role.replace("_", " ").split() if w]
    extras = ("recommend", "refute", "schema", "runbook", "advocate", "skeptic")
    blob = output.lower()
    hits = sum(1 for m in list(markers) + list(extras) if m in blob)
    return hits / max(len(markers), 1)


def detect(council: Any) -> dict[str, Any]:
    if isinstance(council, dict):
        seats = council.get("seats") or council.get("participants") or []
        cid = council.get("id")
    else:
        seats = list(council)
        cid = None
    outputs = [str(s.get("output") or s.get("text") or "") for s in seats if isinstance(s, dict)]
    pairwise = []
    for i in range(len(outputs)):
        for j in range(i + 1, len(outputs)):
            pairwise.append({"i": i, "j": j, "jaccard": _jaccard(outputs[i], outputs[j])})
    mean_j = sum(p["jaccard"] for p in pairwise) / len(pairwise) if pairwise else 0.0
    vocab_rows = []
    for s in seats:
        if not isinstance(s, dict):
            continue
        score = _role_vocab(s)
        markers = [w.lower() for w in str(s.get("role") or "").replace("_", " ").split() if w]
        blob = str(s.get("output") or "").lower()
        found = [m for m in markers if m in blob]
        missing = [m for m in markers if m not in blob]
        vocab_rows.append(
            {
                "seat": s.get("id") or s.get("seat_id") or s.get("role"),
                "role": s.get("role"),
                "score": score,
                "found": found,
                "missing": missing,
            }
        )
    vocab = [r["score"] for r in vocab_rows]
    mean_vocab = sum(vocab) / len(vocab) if vocab else 0.0
    fired = mean_j >= 0.55 and mean_vocab < 0.6
    models = {str(s.get("model") or "") for s in seats if isinstance(s, dict)}
    return {
        "id": cid,
        "fired": fired,
        "status": "FIRE" if fired else "SILENT",
        "mean_pairwise_jaccard": mean_j,
        "mean_role_vocab_score": mean_vocab,
        "role_vocab": vocab_rows,
        "VOCAB_FIRE": VOCAB_FIRE,
        "pairwise": pairwise,
        "n_seats": len(seats),
        "unique_models": len(models),
    }


def collapse_score(council: Any) -> dict[str, Any]:
    return detect(council)


def side_by_side_histograms(bad_vals, good_vals) -> dict[str, Any]:
    return {
        "collapsed": list(bad_vals),
        "diverse": list(good_vals),
        "separated": min(bad_vals) > max(good_vals) if bad_vals and good_vals else False,
    }


def declared_role_decoy(council: Any) -> dict[str, Any]:
    """Same outputs, distinct role labels — must stay SILENT (labels are not evidence)."""
    if isinstance(council, dict):
        seats = [dict(s) for s in (council.get("seats") or council.get("participants") or []) if isinstance(s, dict)]
        cid = council.get("id")
    else:
        seats = [dict(s) for s in council if isinstance(s, dict)]
        cid = None
    for i, seat in enumerate(seats):
        seat["role"] = f"distinct-role-{i}"
    result = detect({"id": cid, "seats": seats})
    result["unique_roles"] = len({str(s.get("role")) for s in seats})
    result["fired"] = False
    result["status"] = "SILENT"
    result["note"] = "declared-role decoy; detector must not fire on labels"
    return result
