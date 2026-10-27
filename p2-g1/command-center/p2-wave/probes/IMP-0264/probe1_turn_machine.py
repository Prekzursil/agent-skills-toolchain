"""IMP-0264 probe 1: kernel round scheduler and turn state machine.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0264/probe1_turn_machine.py
Exit 0 iff, on the live tools/council/kernel.py: a 2-round x 3-seat council
runs alice,bob,cara twice with turns_recorded == turns_executed == 6 (the
event-count invariant); a timed-out turn is still RECORDED; a missing
obligation is recorded obligation_breach; an over-long output is truncated and
recorded length_exceeded; a turn outside a round is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council"))
from kernel import ExecutionPlan, Kernel, KernelError, ScriptedAdapter, TurnResponse, TurnSpec  # noqa: E402

checks = {}
rows = []

kernel = Kernel("c-imp0264")
plan = ExecutionPlan(council_id="c-imp0264", roster=["alice", "bob", "cara"], n_rounds=2)
resp = TurnResponse(text="position", fields={"summary": "s"})
res = kernel.run(plan, None, {pid: ScriptedAdapter(resp) for pid in ("alice", "bob", "cara")})
expected = ("alice", "bob", "cara", "alice", "bob", "cara")
rows.append({
    "id": "full-council-invariant",
    "turn_order": list(res.turn_order),
    "turns_executed": res.turns_executed,
    "turns_recorded": res.turns_recorded,
    "all_ok": res.turn_order == expected and res.turns_executed == res.turns_recorded == 6,
})
checks["full_council_6_of_6"] = rows[-1]["all_ok"]
checks["event_kinds_are_turn"] = all(e.kind == "TURN" for e in res.events)
checks["obligations_recorded_on_event"] = all(
    tuple(e.obligations) == () for e in res.events
)
checks["event_round_index_recorded"] = [e.round_index for e in res.events] == [0] * 6

k2 = Kernel("c-t")
plan2 = ExecutionPlan(council_id="c-t", roster=["alice", "bob"], n_rounds=1)
adapters = {
    "alice": ScriptedAdapter(TurnResponse(text="ok")),
    "bob": ScriptedAdapter(TurnResponse(text="", timed_out=True)),
}
res2 = k2.run(plan2, None, adapters)
bob_ev = next(e for e in res2.events if e.participant_id == "bob")
checks["timeout_recorded"] = bob_ev.status == "timeout"
checks["timeout_invariant_holds"] = res2.turns_executed == res2.turns_recorded == 2

k3 = Kernel("c-o")
plan3 = ExecutionPlan(council_id="c-o", roster=["alice"], n_rounds=1, obligations=["summary"])
res3 = k3.run(plan3, None, {"alice": ScriptedAdapter(TurnResponse(text="no fields"))})
checks["obligation_breach_recorded"] = res3.events[0].status == "obligation_breach"
checks["breach_names_missing"] = res3.events[0].obligations_missing == ("summary",)

k4 = Kernel("c-l")
plan4 = ExecutionPlan(council_id="c-l", roster=["alice"], n_rounds=1, max_chars=5)
res4 = k4.run(plan4, None, {"alice": ScriptedAdapter(TurnResponse(text="0123456789"))})
checks["length_exceeded_recorded"] = res4.events[0].status == "length_exceeded"
checks["output_truncated"] = res4.events[0].output == "01234"

k5 = Kernel("c-b")
try:
    k5.execute_turn(TurnSpec(participant_id="alice"))
    checks["outside_round_refused"] = False
except KernelError:
    checks["outside_round_refused"] = True

ok = all(checks.values()) and all(r["all_ok"] for r in rows)
out = {"probe": "probe1-turn-machine", "unit_id": "IMP-0264",
       "rows": rows, "checks": checks, "all_invariants": ok, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-turn-machine.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0264-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0264-probe1 event-count invariant holds; timeout/breach/length all recorded")
