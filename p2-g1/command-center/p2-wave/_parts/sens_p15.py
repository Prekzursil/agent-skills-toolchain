def curve(q: dict, n_min: int = 1, n_max: int = LOW_N_MAX,
          aggregator: str = AGG_MAJORITY) -> dict:
    rows = []
    for n in range(n_min, n_max + 1):
        res = evaluate_question(q, n, aggregator)
        rows.append(res.as_dict())
    out = {
        "question_id": str(q.get("id")),
        "kind": str(q.get("kind") or "unknown"),
        "aggregator": aggregator,
        "rows": [{"n": r["n"], "decision": r["decision"]} for r in rows],
    }
    flips = 0
    for a, b in zip(out["rows"], out["rows"][1:]):
        if a["decision"] != b["decision"]:
            flips = flips + 1
    stable = _stabilisation_point(out["rows"])
    out["flip_count"] = flips
    out["stabilisation_point"] = stable["n_star"]
    out["stable_decision"] = stable["decision"]
    out["is_n_sensitive"] = flips > 0
    out["published"] = True
    return out


def _stabilisation_point(rows: list[dict]) -> dict:
    if not rows:
        return {"n_star": None, "decision": ""}
    tail = rows[-1]["decision"]
    n_star = rows[-1]["n"]
    for row in reversed(rows):
        if row["decision"] == tail:
            n_star = row["n"]
        else:
            break
    return {"n_star": n_star, "decision": tail}
