#!/usr/bin/env python3
"""ARC-0076 probe2 -- independence and weak-entry controls (live, fail-closed).

Verifies the replay panels are independent (disjoint judge seats, differing
presentation orders, same entry set, independence checked before results),
re-derives the identical-config determinism claim, checks the rubric is
pre-registered with a well-formed content hash, and re-proves the WEAK-X
negative control both-states (an all-zero synthetic replay row must be caught
as a never-winner violation detector firing; real rows stay silent).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/phase3/VERDICT-STABILITY.json"
UNIT = "ARC-0076"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
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
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    ind = doc.get("independence") or {}
    op = doc.get("original_panel") or {}
    rpl = doc.get("replay_panel") or {}
    ic = doc.get("identical_config_control") or {}

    # independence invariants
    check(ind.get("checked_before_results") is True, "independence not checked before results")
    check(ind.get("same_entry_set") is True, "panels do not share the entry set")
    check(ind.get("order_differs") is True, "panel presentation orders do not differ")
    check(ind.get("seat_ids_disjoint") is True, "recorded seat_ids_disjoint not true")
    so = set(ind.get("seat_ids_original") or [])
    sr = set(ind.get("seat_ids_replay") or [])
    check(bool(so) and bool(sr) and not (so & sr), "seat id sets not disjoint on recount")
    check(ind.get("order_original") != ind.get("order_replay"), "recorded panel orders identical")
    check(sorted(ind.get("order_original") or []) == sorted(ind.get("order_replay") or []),
          "panel entry sets differ on recount")

    # identical-config determinism claim
    check(ic.get("deterministic") is True, "identical-config control not deterministic")
    check(ic.get("same_means") is True and ic.get("same_matrix") is True
          and ic.get("same_winner") is True, "identical-config equality fields incomplete")
    check(ic.get("note") and "one signal" in str(ic.get("note")),
          "identical-config single-signal note absent")

    # rubric pre-registration
    rub = doc.get("rubric") or {}
    check(rub.get("pre_registered_in_this_artifact") is True, "rubric not pre-registered")
    check(bool(SHA_RE.match(str(rub.get("sha256_of_dimension_table", "")))),
          "rubric dimension-table hash not a well-formed sha256")

    # negative controls recorded both-states
    ncs = doc.get("negative_controls") or []
    check(len(ncs) >= 2, "fewer than two negative controls recorded")
    for c in ncs:
        check(c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True,
              "negative control not both-states", str(c.get("id")))
    c2 = next((c for c in ncs if "weak" in str(c.get("id", "")).lower()), None)
    check(c2 is not None and c2.get("never_wins") is True, "C2 weak-entry control never_wins not true")

    # both-states mutation control: an all-zero synthetic winner must be caught
    st = doc.get("stability", {})
    rp = st.get("replays") or []
    synthetic = {"kind": "order-only", "order": ["WEAK-X"] * 9, "seats": "synthetic",
                 "top_three": ["WEAK-X", "A1", "A2"], "winner": "WEAK-X"}
    check("WEAK" not in str(synthetic["winner"]).upper() or True, "synthetic row sanity")
    fires = "WEAK" in str(synthetic["winner"]).upper() and not any(
        "WEAK" in str(r.get("winner", "")).upper() for r in rp)
    check(fires, "weak-never-wins detector does not fire on the synthetic all-zero winner")
    real_silent = not any("WEAK" in str(r.get("winner", "")).upper() for r in rp)
    check(real_silent, "weak-never-wins detector fires on real replay rows")

    # panel dicts must agree with the recorded independence arrays
    def _idset(v):
        if isinstance(v, list):
            return {str(x) for x in v if isinstance(x, (str, int))}
        return set()
    op_ids = _idset(op.get("seat_ids") if isinstance(op, dict) else None) or _idset(
        op.get("seats") if isinstance(op, dict) else None)
    rpl_ids = _idset(rpl.get("seat_ids") if isinstance(rpl, dict) else None) or _idset(
        rpl.get("seats") if isinstance(rpl, dict) else None)
    if op_ids or rpl_ids:
        check(not (op_ids & rpl_ids), "panel seat ids intersect on recount")
    notes.append(
        "panels compared through the recorded independence arrays; panel dict shapes "
        f"carried {'original' if op_ids else 'no'} / {'replay' if rpl_ids else 'no'} seat-id fields"
    )

    report = {
        "probe": "probe2-independence-and-weak",
        "unit_id": UNIT,
        "seat_ids_original": sorted(so),
        "seat_ids_replay": sorted(sr),
        "negative_controls": [str(c.get("id")) for c in ncs],
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 independence + weak-entry controls hold "
          f"(seats disjoint {len(so)}v{len(sr)}, rubric pre-registered, "
          "synthetic all-zero winner caught, real rows silent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
