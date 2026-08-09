"""Detector control for the near-duplicate check in _verify_rel1.py.

_verify_rel1.py reported a clean max pairwise Jaccard of 0.130. That number is
worthless unless the same detector FIRES on a planted near-duplicate, so this
file plants three mutant classes against real REL units and reports whether the
threshold (0.55) is crossed. Read-only: operates on an in-memory copy of
REL-1.json and writes nothing.
"""
import json
import re
from itertools import combinations
from pathlib import Path

units = json.loads((Path(__file__).parent / "REL-1.json").read_text(encoding="utf-8"))
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
by_id = {u["id"]: u for u in units}

# Mutant 1: EXACT RENAME of REL-0008 -- new title, body byte-identical.
m1 = ("Lifecycle integrity checker over the four operations "
      + by_id["REL-0008"]["question_or_target"])

# Mutant 2: PARAPHRASE of REL-0020 -- same mechanism, reworded, some vocab kept.
m2 = ("Implementation target: demonstrate that the refresh step of the release genuinely clears "
      "the cache. Build the failing state on purpose by seeding a stale copy of the earlier package "
      "into every cache directory the client reads, install the candidate, and confirm the running "
      "client is executing the newer bytes. A cache invalidation check performed against an empty "
      "cache stays quiet in the broken state and the repaired state equally, so it measures nothing.")

# Mutant 3: FULL REWRITE of REL-0016 -- same mechanism, vocabulary deliberately swapped.
m3 = ("Implementation target: stop anybody typing the shipping summary by hand. Derive every line of "
      "the version history document automatically from the ledger of proven assertions, allow a line "
      "only where its backing assertion is marked proven and its pointer resolves on disk, and break "
      "the build when somebody edits a sentence in by hand instead of regenerating it.")

controls = [("exact-rename", "REL-0008", m1),
            ("paraphrase", "REL-0020", m2),
            ("full-rewrite", "REL-0016", m3)]

print("DETECTOR CONTROL (threshold 0.55, same tokenizer as _verify_rel1.py)")
for name, target, mutant in controls:
    score = jac(base[target], mutant)
    print("  %-13s vs %s : %.3f  -> %s"
          % (name, target, score, "FIRES" if score >= 0.55 else "SILENT"))

worst = max(jac(text(a), text(b)) for a, b in combinations(units, 2))
print("  clean corpus max                  : %.3f  -> %s"
      % (worst, "FIRES" if worst >= 0.55 else "SILENT (expected)"))
print("\nSCOPE: this detector is LEXICAL. Any class it is SILENT on above is a class the clean "
      "0.130 reading does NOT cover; settle that class with an embedding-cosine rescan using the "
      "same planted mutants as the control.")
