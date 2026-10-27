"""IMP-0198 probe 2 (verifier, both-states): a development run that touches a
held-out case raises HeldOutTouchError and the access log records the
violation; development reads of visible cases are silent; evaluation may read
held-out; and a relabelled partition_cached convention cannot hide the touch.

Exit 0 iff the detector fires on the bad state, stays silent on good states,
and the convention cannot hide it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.evals.matched_corpus import (HELD_OUT, VISIBLE, AccessLog,  # noqa: E402
                                            HeldOutTouchError, load_corpus, partition_of)

RAW = HERE / "probe2-heldout-touch.raw.txt"

corpus = load_corpus()
cases = corpus["cases"]
held_id = next(c for c in cases if partition_of(c) == HELD_OUT)
visible_id = next(c for c in cases if partition_of(c) == VISIBLE)

# Bad state: development touches a held-out case.
log_bad = AccessLog()
fired = False
try:
    log_bad.read(held_id, mode="development")
except HeldOutTouchError:
    fired = True
assert fired, "development touch of held-out case was not detected"
access_log_recorded = bool(log_bad.violations) and log_bad.violations[-1]["case"] == held_id["id"]
assert access_log_recorded, "access log did not record the violation"

# Good states: visible development read is silent; evaluation may read held-out.
log_good = AccessLog()
log_good.read(visible_id, mode="development")
silent_on_visible = not log_good.violations
assert silent_on_visible, "detector fired on a visible development read"
log_eval = AccessLog()
log_eval.evaluation_read(held_id)
evaluation_ok = not log_eval.violations
assert evaluation_ok, "evaluation lane was blocked from the held-out slice"

# Convention mutation: relabel the case; the detector still fires.
relabelled = dict(held_id, partition_cached=VISIBLE)
log_mut = AccessLog()
fired_mut = False
try:
    log_mut.read(relabelled, mode="development")
except HeldOutTouchError:
    fired_mut = True
convention_cannot_hide = fired_mut and bool(log_mut.violations)
assert convention_cannot_hide, "relabelled convention hid the held-out touch"

lines = [json.dumps({"probe": "probe2-heldout-touch", "unit_id": "IMP-0198",
                     "held_out_ids_sampled": [held_id["id"]],
                     "visible_ids_sampled": [visible_id["id"]],
                     "fired_on_held_out_development": fired,
                     "access_log_recorded_violation": access_log_recorded,
                     "silent_on_visible_development": silent_on_visible,
                     "evaluation_may_read_held_out": evaluation_ok,
                     "convention_label_cannot_hide": convention_cannot_hide})]
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"fired_on_bad": fired, "silent_on_good": silent_on_visible,
                              "eval_held_out_ok": evaluation_ok,
                              "convention_cannot_hide": convention_cannot_hide,
                              "held_out_sampled": held_id["id"]}))
print("SUCCESS:IMP-0198-probe2 touching a held-out case during development is detected")
