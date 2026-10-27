def compare_default(q: dict) -> dict:
    c = curve(q)
    default_n = int(q.get("default_n") or DEFAULT_SEAT_COUNT)
    at_default = None
    for row in c["rows"]:
        if row["n"] == default_n:
            at_default = row["decision"]
    above = at_default == c["stable_decision"]
    out = {
        "question_id": c["question_id"],
        "default_n": default_n,
        "stabilisation_point": c["stabilisation_point"],
        "stable_decision": c["stable_decision"],
        "decision_at_default": at_default,
        "default_above_stable": bool(above),
        "n_sensitive_question": c["is_n_sensitive"],
    }
    return out


def tune_until_stable(q: dict) -> dict:
    """The documented BAD practice: search for an N that hides the flips.

    Exists only so the negative control can show it collapsing an N-sensitive
    curve into a stable-looking single N. Production publishes the flips.
    """
    c = curve(q)
    stable = c["stabilisation_point"]
    chosen = stable if stable is not None else 1
    return {
        "question_id": c["question_id"],
        "chosen_n": chosen,
        "decision": c["stable_decision"],
        "flips_collapsed": c["flip_count"],
        "collapsed": c["flip_count"] > 0,
    }


def protocol_is_n_sensitive(c: dict) -> bool:
    return bool(c.get("is_n_sensitive"))


def public_row(c: dict) -> dict:
    return {
        "question_id": c["question_id"],
        "kind": c["kind"],
        "n_star": c["stabilisation_point"],
        "stable_decision": c["stable_decision"],
        "flip_count": c["flip_count"],
        "is_n_sensitive": c["is_n_sensitive"],
        "published": c["published"],
    }


__all__ = [
    "AGG_MAJORITY", "AGG_N_MODULATED", "DEFAULT_SEAT_COUNT", "LOW_N_MAX",
    "Result", "compare_default", "curve", "evaluate_question",
    "load_question", "protocol_is_n_sensitive", "public_row",
    "tune_until_stable",
]
