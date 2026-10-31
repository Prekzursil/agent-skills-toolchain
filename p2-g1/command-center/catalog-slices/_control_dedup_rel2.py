"""Second, mechanically DIFFERENT near-duplicate signal for REL-1.json.

_control_dedup_rel.py proved the word-level Jaccard detector FIRES on an exact
rename (0.905) but is SILENT on a paraphrase (0.275) and a full rewrite (0.050).
A detector silent on the class you care about measures nothing for that class,
so this file adds a character 4-gram cosine over the same text, run against the
SAME planted mutants, and reports whether it covers the paraphrase class that
the word-level detector misses. Read-only.
"""
import json
import math
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

units = json.loads((Path(__file__).parent / "REL-1.json").read_text(encoding="utf-8"))
by_id = {u["id"]: u for u in units}


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def grams(t, n=4):
    s = norm(t)
    return Counter(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def cos(a, b):
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    common = set(ga) & set(gb)
    dot = sum(ga[g] * gb[g] for g in common)
    na = math.sqrt(sum(v * v for v in ga.values()))
    nb = math.sqrt(sum(v * v for v in gb.values()))
    return dot / (na * nb)


def text(u):
    return u["title"] + " " + u["question_or_target"]


m1 = ("Lifecycle integrity checker over the four operations "
      + by_id["REL-0008"]["question_or_target"])
m2 = ("Implementation target: demonstrate that the refresh step of the release genuinely clears "
      "the cache. Build the failing state on purpose by seeding a stale copy of the earlier package "
      "into every cache directory the client reads, install the candidate, and confirm the running "
      "client is executing the newer bytes. A cache invalidation check performed against an empty "
      "cache stays quiet in the broken state and the repaired state equally, so it measures nothing.")
m3 = ("Implementation target: stop anybody typing the shipping summary by hand. Derive every line of "
      "the version history document automatically from the ledger of proven assertions, allow a line "
      "only where its backing assertion is marked proven and its pointer resolves on disk, and break "
      "the build when somebody edits a sentence in by hand instead of regenerating it.")

THRESH = 0.55
print("SECOND SIGNAL: character 4-gram cosine (threshold %.2f)" % THRESH)
for name, tid, mut in [("exact-rename", "REL-0008", m1),
                       ("paraphrase", "REL-0020", m2),
                       ("full-rewrite", "REL-0016", m3)]:
    s = cos(text(by_id[tid]), mut)
    print("  %-13s vs %s : %.3f  -> %s" % (name, tid, s, "FIRES" if s >= THRESH else "SILENT"))

pairs = sorted(((cos(text(a), text(b)), a["id"], b["id"])
                for a, b in combinations(units, 2)), reverse=True)
print("\n  TOP 5 CLEAN PAIRS:")
for s, x, y in pairs[:5]:
    print("    %.3f  %s <-> %s  -> %s" % (s, x, y, "FIRES" if s >= THRESH else "SILENT"))
print("\n  clean corpus max = %.3f" % pairs[0][0])
# --- THIRD SURFACE: the tests, not the prose -----------------------------
# Two units that are the same mechanism reworded would still have to TEST the
# same thing, so the test list is a text surface an author cannot paraphrase
# away without also changing what the unit actually does.
def wtoks(t):
    return set(re.findall(r"[a-z0-9_.-]{4,}", t.lower()))


def tests_text(u):
    return " ".join(u["tests_required"]) + " " + u["evidence_requirement"]


tp = sorted(((len(wtoks(tests_text(a)) & wtoks(tests_text(b)))
              / max(1, len(wtoks(tests_text(a)) | wtoks(tests_text(b)))), a["id"], b["id"])
             for a, b in combinations(units, 2)), reverse=True)
print("\nTHIRD SURFACE: word Jaccard over tests_required + evidence_requirement")
for s, x, y in tp[:5]:
    print("    %.3f  %s <-> %s  -> %s" % (s, x, y, "FIRES" if s >= 0.55 else "SILENT"))
print("    clean corpus max = %.3f" % tp[0][0])

print("\nVERDICT SCOPE: the three surfaces AGREE only on the class where each fires. Whatever all "
      "three are silent on remains NOT-CHECKED and needs an embedding-cosine rescan with these same "
      "planted mutants as its control.")
