"""Detector control for the near-duplicate check in _verify_cc1.py.

Plants three mutant classes against real CC-1 units and reports whether the
lexical Jaccard detector FIRES (>=0.55). A detector that is silent on a planted
paraphrase measures nothing, so its 0.105 clean reading would be worthless.
Read-only: operates on an in-memory copy, writes nothing.
"""
import json
import re
from itertools import combinations
from pathlib import Path

units = json.loads((Path(__file__).parent / "CC-1.json").read_text(encoding="utf-8"))
STOP = set(("the a an and or of to in for that this with must be is are on by not "
            "it its as at from into then than which what when where must-be a-the "
            "unit units work spec target question implementation must").split())


def toks(t):
    return {w for w in re.findall(r"[a-z0-9_.-]{3,}", t.lower()) if w not in STOP}


def jac(a, b):
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / max(1, len(ta | tb))


def text(u):
    return u["title"] + " " + u["question_or_target"]


base = {u["id"]: text(u) for u in units}

# Mutant 1: EXACT RENAME of CC-0003 (title changed, body identical).
m1 = "A single shared done-check for all fan-in sites " + units[2]["question_or_target"]
# Mutant 2: PARAPHRASE of CC-0011 (same mechanism, reworded, some vocab kept).
m2 = ("Verify that no secret, token or private key has been copied into the program "
      "corpus, the command-center tree, or the rollback backups. Read-only scanning "
      "only: report the variable name, the scope, the byte length and whether a whoami "
      "probe still authenticates; never emit a value; never rotate or unset a credential.")
# Mutant 3: FULL REWRITE of CC-0013 (same mechanism, vocabulary deliberately swapped).
m3 = ("Stop the dashboard from being typed by hand. Compute every figure in the summary "
      "board automatically out of the ledger stream and the emitted proof files, brand it "
      "with the revision that produced it, and break the build if a human alters a number "
      "directly in the board.")

controls = [("exact-rename", "CC-0003", m1),
            ("paraphrase", "CC-0011", m2),
            ("full-rewrite", "CC-0013", m3)]

print("DETECTOR CONTROL (threshold 0.55, same tokenizer as _verify_cc1.py)")
for name, target, mutant in controls:
    score = jac(base[target], mutant)
    print("  %-13s vs %s : %.3f  -> %s"
          % (name, target, score, "FIRES" if score >= 0.55 else "SILENT"))

worst = max(jac(text(a), text(b)) for a, b in combinations(units, 2))
print("  clean corpus max                 : %.3f  -> %s"
      % (worst, "FIRES" if worst >= 0.55 else "SILENT (expected)"))
print("\nSCOPE: this detector is LEXICAL. Whatever class it is SILENT on above is a class"
      "\nthis slice's 0.105 clean reading does NOT rule out. That is the CC-0020 residual.")
