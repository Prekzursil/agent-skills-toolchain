"""IMP-0273 probe 2: an agreeing refuter is flagged (negative control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0273/probe2_agreeing_refuter.py
Exit 0 iff, on the live select_adversarial module: agree_mode="none" first
rounds are SILENT under flag_agreeing_refuters; agree_mode="full" and
"position-only" rounds FIRE agreeing-refuter on every pair (prose such as
"I refute" cannot mask position agreement); the agree-mode spread on the
question axis is strictly lower than the opposed-mode spread (the spread
metric itself flags the agreeing refuter); and agreeing_refuter_control
agrees (its own both-states verdict passes).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_adversarial import (  # noqa: E402
    default_pool,
    default_questions,
    emit_first_round,
    flag_agreeing_refuters,
    polarity_spread,
    select_adversarial,
    agreeing_refuter_control,
)

pool = default_pool()
question = default_questions()[0]
sel = select_adversarial(pool, n_proposers=3)
n_pairs = len(sel.pairs())

none_turns = emit_first_round(sel, question, agree_mode="none")
full_turns = emit_first_round(sel, question, agree_mode="full")
pos_only_turns = emit_first_round(sel, question, agree_mode="position-only")

flags_none = flag_agreeing_refuters(none_turns, sel)
flags_full = flag_agreeing_refuters(full_turns, sel)
flags_pos = flag_agreeing_refuters(pos_only_turns, sel)

axis = question.axis
spread_none = polarity_spread([t.text for t in none_turns], axis)
spread_full = polarity_spread([t.text for t in full_turns], axis)
spread_pos = polarity_spread([t.text for t in pos_only_turns], axis)

control = agreeing_refuter_control(pool, question, n_proposers=3)

checks = {
    "none_mode_silent": len(flags_none) == 0,
    "full_mode_fires_on_all_pairs": len(flags_full) == n_pairs,
    "position_only_fires_on_all_pairs": len(flags_pos) == n_pairs,
    "flags_carry_code": all(f["code"] == "agreeing-refuter" for f in flags_full),
    "spread_metric_lower_for_agreeing": spread_full < spread_none and spread_pos < spread_none,
    "control_passes": control["pass"] is True,
}
ok = all(checks.values())
out = {"probe": "probe2-agreeing-refuter", "unit_id": "IMP-0273",
       "n_pairs": n_pairs,
       "flags_none": len(flags_none),
       "flags_full": len(flags_full),
       "flags_position_only": len(flags_pos),
       "spread_none": round(spread_none, 4),
       "spread_full_agree": round(spread_full, 4),
       "spread_position_only": round(spread_pos, 4),
       "control": control,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-agreeing-refuter.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0273-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0273-probe2 agreeing refuters flagged on every pair; spread metric concurs; honest rounds silent")
