# -*- coding: utf-8 -*-
"""Detector control for the ADV-1 cross-slice near-duplicate sweep (V6).

A zero-result is only credible if the detector demonstrably FIRES on a known-present match and
stays silent on a known-distinct one. This also proves the sibling corpus was actually traversed
(comparison count > 0) rather than skipped by a bad glob.
"""
import json
import os
import re
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("""the a an and or of to in on for with that this it is are be by as at from into over under not no
which what when where does do can any every each all their its they them we you your our than then so such
must may should would could will shall if else per via using use used unit units work program spec probe
probes record records result results report reports run runs ran test tests testing check checks checked
against between across without within before after during while whether against""".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 4 and w not in STOP)


def jac(a, b):
    return len(a & b) / float(len(a | b)) if a and b else 0.0


mine = json.load(open(os.path.join(HERE, "ADV-1.json"), encoding="utf-8"))
sigs = [toks(u["title"] + " " + u["question_or_target"] + " " + u["mechanism"]) for u in mine]
df = collections.Counter()
for s in sigs:
    for t in s:
        df[t] += 1
cut = max(2, int(0.30 * len(mine)))
pruned = [set(t for t in s if df[t] <= cut) for s in sigs]

files, sib_units, comparisons = [], 0, 0
best_real = (0.0, None, None)
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "ADV-1.json":
        continue
    try:
        sib = json.load(open(os.path.join(HERE, fn), encoding="utf-8"))
    except Exception as e:
        print("  SKIP %s (%s)" % (fn, type(e).__name__))
        continue
    if not isinstance(sib, list):
        continue
    files.append((fn, len(sib)))
    for su in sib:
        sib_units += 1
        st = set(t for t in toks(str(su.get("title", "")) + " " + str(su.get("question_or_target", "")))
                 if df[t] <= cut)
        for i in range(len(mine)):
            comparisons += 1
            s = jac(pruned[i], st)
            if s > best_real[0]:
                best_real = (s, mine[i]["id"], "%s:%s" % (fn, su.get("id")))

# --- CONTROL A (known-present): inject a verbatim copy of one of my units as a "sibling" entry.
victim = mine[41]
inj = set(t for t in toks(victim["title"] + " " + victim["question_or_target"]) if df[t] <= cut)
ctrl_present = max(jac(pruned[i], inj) for i in range(len(mine)))
# --- CONTROL B (known-present, paraphrased): same unit, reworded surface.
para = victim["title"].replace("Erasure test:", "Deletion probe:").replace("actually", "really") + " " + \
       victim["question_or_target"].replace("Given a request to delete", "When asked to remove")
inj2 = set(t for t in toks(para) if df[t] <= cut)
ctrl_para = max(jac(pruned[i], inj2) for i in range(len(mine)))
# --- CONTROL C (known-distinct): unrelated text.
inj3 = set(t for t in toks("bake a sourdough loaf using a stiff levain and a cast iron dutch oven")
           if df[t] <= cut)
ctrl_distinct = max(jac(pruned[i], inj3) for i in range(len(mine)))

print("sibling files scanned : %d" % len(files))
for fn, n in files:
    print("    %-14s %4d units" % (fn, n))
print("sibling units         : %d" % sib_units)
print("comparisons performed : %d" % comparisons)
print("-" * 70)
print("CONTROL A known-present (verbatim %s)  max sim = %.3f  -> %s"
      % (victim["id"], ctrl_present, "FIRES" if ctrl_present >= 0.45 else "SILENT (DETECTOR BROKEN)"))
print("CONTROL B known-present (paraphrase)      max sim = %.3f  -> %s"
      % (ctrl_para, "FIRES" if ctrl_para >= 0.45 else "SILENT"))
print("CONTROL C known-distinct (off-topic)      max sim = %.3f  -> %s"
      % (ctrl_distinct, "correctly silent" if ctrl_distinct < 0.45 else "FALSE POSITIVE"))
print("-" * 70)
print("HIGHEST REAL cross-slice similarity: %.3f  %s vs %s" % best_real)
ok = ctrl_present >= 0.45 and ctrl_distinct < 0.45 and comparisons > 0
print("SUCCESS:adv-dedup-detector-control" if ok else "FAILED:adv-dedup-detector-control")
