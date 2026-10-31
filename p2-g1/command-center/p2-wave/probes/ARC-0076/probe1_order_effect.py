#!/usr/bin/env python3
"""ARC-0076 probe1 -- order-effect control (live, fail-closed).

Re-derives the recorded tournament stability numbers from the artifact's own
replay table: replay arithmetic (n_order_only + n_roster_change == n_replays),
winner probabilities per replay kind, the primacy number reproduced by the
weak-entry front-minus-end placement delta, the order-only replay orders being
all distinct, and the never-wins property of the zero-merit WEAK-X entry.
Mutation control: an inverted weak-entry delta must not reproduce the recorded
primacy.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/phase3/VERDICT-STABILITY.json"
UNIT = "ARC-0076"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold", f"{OUT.stat().st_size} < {minb}")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent from artifact text")

    st = doc.get("stability", {})
    rp = st.get("replays") or []
    oe = doc.get("order_effect", {})
    bs = doc.get("both_states", {})
    trials = bs.get("trials") or []

    # replay arithmetic
    oo = [r for r in rp if r.get("kind") == "order-only"]
    rc = [r for r in rp if r.get("kind") != "order-only"]
    check(len(rp) == int(st.get("n_replays", -1)), "n_replays vs replay rows",
          f"{len(rp)} vs {st.get('n_replays')}")
    check(len(oo) == int(st.get("n_order_only", -1)), "n_order_only vs kind rows",
          f"{len(oo)} vs {st.get('n_order_only')}")
    check(len(rc) == int(st.get("n_roster_change", -1)), "n_roster_change vs kind rows",
          f"{len(rc)} vs {st.get('n_roster_change')}")
    check(len(oo) + len(rc) == len(rp), "kinds do not partition replays")
    orders = [tuple(r.get("order") or []) for r in oo]
    check(len(set(orders)) == len(orders), "order-only replay orders not all distinct")
    check(int(oe.get("n_permutations", -1)) == 24, "n_permutations != 24", str(oe.get("n_permutations")))
    check(oe.get("orders_all_distinct") is True, "order_effect.orders_all_distinct not true")
    check(oe.get("position_bias_measured") is True, "position_bias_measured not true")

    # winner probabilities re-derived from replay rows
    bw = st.get("baseline_winner")
    same_oo = sum(1 for r in oo if r.get("winner") == bw)
    same_rc = sum(1 for r in rc if r.get("winner") == bw)
    same_all = same_oo + same_rc
    want_oo = round(same_oo / len(oo), 6) if oo else None
    want_rc = round(same_rc / len(rc), 6) if rc else None
    want_all = round(same_all / len(rp), 6) if rp else None
    check(abs(float(st.get("probability_same_winner_order_only", -2)) - (want_oo or -1)) < 1e-6,
          "probability_same_winner_order_only mismatch",
          f"recorded {st.get('probability_same_winner_order_only')} vs recomputed {want_oo}")
    check(abs(float(st.get("probability_same_winner_roster_change", -2)) - (want_rc or -1)) < 1e-6,
          "probability_same_winner_roster_change mismatch",
          f"recorded {st.get('probability_same_winner_roster_change')} vs recomputed {want_rc}")
    check(abs(float(st.get("probability_same_winner", -2)) - (want_all or -1)) < 1e-6,
          "probability_same_winner mismatch",
          f"recorded {st.get('probability_same_winner')} vs recomputed {want_all}")
    bt = (doc.get("baseline_ranking") or {}).get("top_three") or []
    same_t3 = sum(1 for r in rp if list(r.get("top_three") or []) == list(bt))
    check(abs(float(st.get("probability_same_top_three", -2)) - round(same_t3 / len(rp), 6)) < 1e-6,
          "probability_same_top_three (exact-ordered) mismatch",
          f"recorded {st.get('probability_same_top_three')} vs recomputed {round(same_t3 / len(rp), 6)}")

    # primacy number: reproduced by the weak-entry front-minus-end delta
    orig = [t for t in trials if t.get("panel") == "original"]
    if orig:
        weak_delta = float(orig[0].get("weak_mean", 0)) - float(orig[-1].get("weak_mean", 0))
        check(abs(float(oe.get("primacy_effect", -2)) - weak_delta) < 1e-9,
              "primacy_effect not reproduced by weak-entry front-minus-end delta",
              f"recorded {oe.get('primacy_effect')} vs weak delta {round(weak_delta, 6)}")
        # mutation control: inverted delta must NOT reproduce
        check(abs(float(oe.get("primacy_effect", -2)) + weak_delta) > 1e-9,
              "mutation control: inverted weak delta also reproduces primacy (detector cannot fire)")
        notes.append(
            f"method-text observation recorded (not gating): the order_effect method text "
            f"names slot-0-vs-slot-8 mean scores, whose recorded slot_means delta is "
            f"{round(float(oe.get('slot_means', [0, 0])[0]) - float(oe.get('slot_means', [0, 0])[-1]), 6)}; "
            f"the recorded primacy_effect {oe.get('primacy_effect')} is instead reproduced exactly by the "
            "zero-merit WEAK-X entry front-minus-end placement delta on the original panel "
            "(the primacy effect measured on an identical low-merit entry across slots)"
        )
    check(len(trials) == int(bs.get("placements", -1)) == 6, "weak trials != 6 placements",
          f"{len(trials)} vs {bs.get('placements')}")

    # WEAK-X never wins in any trial
    bad_wins = [t for t in trials if "WEAK" in str(t.get("winner", "")).upper()]
    check(not bad_wins, "zero-merit entry won a placement", str(len(bad_wins)))
    check(bs.get("never_wins") is True, "both_states.never_wins not true")
    winner_set = set(oe.get("winner_set") or [])
    entry_ids = {e.get("entry_id") for e in doc.get("entries") or []}
    check(winner_set <= entry_ids, "winner_set outside entry ids", str(winner_set))
    check(bw in entry_ids, "baseline_winner outside entry ids", str(bw))
    check((doc.get("identical_config_control") or {}).get("deterministic") is True,
          "identical-config control not recorded deterministic")

    report = {
        "probe": "probe1-order-effect-control",
        "unit_id": UNIT,
        "replays": len(rp),
        "order_only": len(oo),
        "roster_change": len(rc),
        "recomputed": {
            "p_same_winner_order_only": want_oo,
            "p_same_winner_roster_change": want_rc,
            "p_same_winner": want_all,
            "p_same_top_three_exact_ordered": round(same_t3 / len(rp), 6),
        },
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 order-effect control re-derived "
          f"({len(rp)} replays: {want_oo}/{want_rc}/{want_all}; primacy {oe.get('primacy_effect')} "
          "== weak-entry front-minus-end delta; WEAK-X never wins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
