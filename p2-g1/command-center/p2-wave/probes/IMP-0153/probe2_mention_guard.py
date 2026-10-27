"""IMP-0153 probe 2 (verifier, both-states control): mention-only doc yields zero
USE candidates; stripping the criticism markers (mutation) makes candidates appear,
proving the mention guard is load-bearing rather than inert.

Re-run: python command-center/p2-wave/probes/IMP-0153/probe2_mention_guard.py
Exit 0 iff: guard silent on the clean mention-only control, and fires (candidates
surface) on the mutated copy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "workflow-foundry"))
import wf_usemention as UM  # noqa: E402

FIX = W / "tools" / "workflow-foundry" / "fixtures" / "IMP-0153"
RAW = Path(__file__).resolve().parent / "probe2-mention-guard.raw.txt"
CONTROL = FIX / "mention-only-control.md"

lines = []
text = CONTROL.read_text(encoding="utf-8")

# Good state: the criticism-only document must produce zero USE candidates.
res = UM.classify_document(text)
use_clean = res["use_candidates"]
lines.append("clean mention-only control: use_candidates={} doc_class={}".format(
    len(use_clean), res["doc_class"]))
assert len(use_clean) == 0, (
    "mention-only control produced {} USE candidates: {}".format(
        len(use_clean), [c["sentence"] for c in use_clean]))
silent_on_good = len(use_clean) == 0

# Bad state (planted mutation): remove the criticism markers; the same workflow
# text now reads as endorsement, and the extractor MUST surface candidates.
mutated = text
# shard8 fix 2026-10-24: _FORBID_RE also treats the "post-mortem" title
# token as forbidding evidence; the mutation must strip it too or the
# mutated copy stays doc-guarded and the control cannot fire.
mutated = mutated.replace("Post-mortem:", "Runbook:")
for m in ["Do not adopt this pipeline.", "anti-pattern", "avoids it",
          "disaster", "silently overwrote", "Beware"]:
    mutated = mutated.replace(m, "")
for m in ["was a ", "meant ", "used ", "and the emitted index ", " worth naming so the next reader ",
          ". Its every step is", " to criticize", "in practice it "]:
    mutated = mutated.replace(m, " ")
mutated = mutated.replace("The nightly pipeline looked impeccable on paper:", "Nightly pipeline steps:")
res_bad = UM.classify_document(mutated)
use_bad = res_bad["use_candidates"]
lines.append("mutated copy: use_candidates={}".format(len(use_bad)))
for c in use_bad:
    lines.append("  surfaced: " + c["sentence"][:120])
fired_on_bad = len(use_bad) > 0
assert fired_on_bad, "mutation removed the guard's evidence but no candidates surfaced; guard is inert"

lines.append("PASS: mention guard silent on good state, fires on mutated state")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "use_candidates_clean": len(use_clean),
    "use_candidates_mutated": len(use_bad),
    "silent_on_good_state": silent_on_good,
    "fired_on_bad_state": fired_on_bad,
}))
print("PASS")
