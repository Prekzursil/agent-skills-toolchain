"""Detector-control for the CROSS-slice scan in _verify_imp3.py.

The first run printed max=0.000 for every sibling. That number is produced only from
hits above the 0.45 threshold, so it cannot distinguish "no overlap" from "the extractor
read nothing". This probe proves the extractor is live before any absence is believed:
prints token-set sizes per sibling and the TRUE unthresholded max similarity.
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("the a an of to and or for in on with by that this is are be it its as at from "
           "does do can any every no not it's implement so plus into per over under "
           "falsifiable question rather than must not".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9_]+", s.lower()) if w not in STOP and len(w) > 2)


def jac(a, b):
    return len(a & b) / float(len(a | b)) if a and b else 0.0


mine = json.loads(io.open(os.path.join(HERE, "IMP-3.json"), encoding="utf-8").read())
mv = [(u["id"], u["title"], toks(u["title"] + " " + u["question_or_target"])) for u in mine]
print("MINE n=%d  mean_tokens=%.1f" % (len(mv), sum(len(t[2]) for t in mv) / float(len(mv))))

for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "IMP-3.json":
        continue
    other = json.loads(io.open(os.path.join(HERE, fn), encoding="utf-8").read())
    if isinstance(other, dict):
        other = other.get("items") or other.get("work_units") or []
    keys = sorted(other[0].keys()) if other and isinstance(other[0], dict) else []
    ov = []
    for o in other:
        if not isinstance(o, dict):
            continue
        t = o.get("title", "")
        q = o.get("question_or_target") or o.get("target") or ""
        ov.append((o.get("id"), o.get("phase"), t, toks(t + " " + q)))
    empt = sum(1 for x in ov if not x[3])
    meantok = sum(len(x[3]) for x in ov) / float(len(ov)) if ov else 0
    phases = {}
    for x in ov:
        phases[x[1]] = phases.get(x[1], 0) + 1
    best = (0.0, None, None, "", "")
    for mid, mt, m in mv:
        for oid, oph, ot, o in ov:
            s = jac(m, o)
            if s > best[0]:
                best = (s, mid, oid, mt, ot)
    print("%-14s n=%-4d empty_token_sets=%-3d mean_tokens=%5.1f phases=%s"
          % (fn, len(ov), empt, meantok, sorted(phases.items(), key=lambda z: str(z[0]))))
    print("               TRUE_MAX=%.3f  %s vs %s" % (best[0], best[1], best[2]))
    print("                 mine: %s" % best[3][:95])
    print("                 them: %s" % best[4][:95])
    if not ov or empt == len(ov):
        print("               !! EXTRACTOR DEAD for this file - absence verdict INVALID")
