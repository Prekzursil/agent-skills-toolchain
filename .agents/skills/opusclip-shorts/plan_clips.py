#!/usr/bin/env python
"""plan_clips.py — plan shorts clips from a merged words.json, audit them against an
existing OpusClip set, and emit the chronological renumber map.

Usage:
  python plan_clips.py clips <WORDS_JSON> <CLIPS_OUT_JSON> "id1|slug|start phrase|end phrase" ...
      -> resolves each anchor pair to word indices + padded times; guards neighbor overlap.
  python plan_clips.py locate <WORDS_JSON> <OPUS_TRANSCRIPT_DIR> <RANGES_OUT_JSON> [opus_files.json]
      -> fuzzy-locates every existing short (tr_*.json, word-level) on the master timeline;
         range = first-window match start .. start + real file duration.
  python plan_clips.py audit <CLIPS_JSON> <RANGES_JSON>
      -> prints clip-vs-opus and opus-vs-opus overlaps; marks clips to DROP (>30% covered).
  python plan_clips.py renumber <RANGES_JSON> <MINE_JSON>
      -> chronological old->new number map for ALL shorts (tie at equal start: earlier end first).

Matching normalizes by stripping Romanian diacritics + punctuation; first/last-8-word
sliding window, threshold conf>=0.5; middle-window fallback estimates start - dur/2.
"""
import json, re, sys, os, glob

def norm(s):
    s = s.lower().strip(".,!?;:\"'()[]")
    for a,b in (("ș","s"),("ț","t"),("ă","a"),("â","a"),("î","i")): s = s.replace(a,b)
    return re.sub(r"[^a-z0-9]","",s)

def load_words(p):
    W = json.load(open(p, encoding="utf-8")); mt = [norm(w["w"]) or "@" for w in W]; return W, mt

def best_match(mt, M, query, lo=0.0):
    q = [x for x in (norm(t) for t in query) if x]; n = len(q); best = (0.0,-1)
    for i in range(len(mt)-n):
        if M[i]["t"] < lo: continue
        sc = sum(1 for j in range(n) if mt[i+j]==q[j]) / n
        if sc > best[0]: best = (sc,i)
    return best

def cmd_clips(words_p, out_p, specs):
    W, mt = load_words(words_p); low = [w["w"].lower().strip(".,!?;:") for w in W]
    def find(phrase, after=0.0):
        toks = phrase.lower().split()
        for i in range(len(W)-len(toks)):
            if W[i]["t"] < after: continue
            if all(low[i+j]==toks[j] for j in range(len(toks))): return i, i+len(toks)
        return None, None
    clips = []
    for sp in specs:
        cid, name, s, e = sp.split("|")
        si,_ = find(s); ei,ej = find(e, W[si]["t"])
        start = max(0.0, W[si]["t"]-0.45); end = W[ej-1]["e"]+0.55
        if si>0 and start < W[si-1]["e"]: start = W[si-1]["e"]+0.08
        clips.append(dict(id=cid,name=name,start=round(start,2),end=round(end,2),w0=si,w1=ej-1))
        print(f"{cid} {name}: {start:.1f} -> {end:.1f} ({end-start:.1f}s)")
    json.dump(clips, open(out_p,"w",encoding="utf-8"), ensure_ascii=False, indent=1)

def cmd_locate(words_p, tdir, out_p, files_p=None):
    W, mt = load_words(words_p)
    durs = {}
    if files_p:
        for m in json.load(open(files_p, encoding="utf-8")):
            durs[m["file"].split()[0].lstrip("#")] = m["dur"]
    out = []
    for f in sorted(glob.glob(os.path.join(tdir,"tr_*.json"))):
        oid = os.path.basename(f)[3:5].lstrip("0") or "1"
        d = json.load(open(f, encoding="utf-8"))
        words = [w for s in d.get("segments",[]) for w in s.get("words",[])]
        texts = [w["text"] for w in words]; dur = durs.get(oid) or 0
        s1,i1 = best_match(mt, W, texts[:8])
        if s1 < 0.5:
            s2,i2 = best_match(mt, W, texts[len(texts)//2-4:len(texts)//2+4])
            if s2 >= 0.5:
                st = max(0.0, W[i2]["t"]-dur/2); out.append({"id":oid,"start":st,"end":st+dur,"conf":round(s2,2)}); continue
            out.append({"id":oid,"start":None,"end":None,"conf":round(s1,2)}); continue
        st = W[i1]["t"]; out.append({"id":oid,"start":st,"end":st+dur,"conf":round(s1,2)})
    out.sort(key=lambda x:(x["start"] is None, x["start"] or 0))
    json.dump(out, open(out_p,"w"), indent=1)
    for o in out: print(f"#{o['id']}: {o['start']} -> {o['end']} conf {o['conf']}")

def cmd_audit(clips_p, ranges_p):
    clips = json.load(open(clips_p, encoding="utf-8"))
    opus = json.load(open(ranges_p, encoding="utf-8"))
    for c in clips:
        for o in opus:
            if o["start"] is None: continue
            ov = min(o["end"],c["end"]) - max(o["start"],c["start"])
            if ov > 0:
                pct = ov/(c["end"]-c["start"])*100
                verdict = "DROP-dup" if pct > 30 else "trim?"
                print(f'clip {c["id"]} vs opus#{o["id"]}: {ov:.0f}s ({pct:.0f}%) -> {verdict}')
    for a in range(len(opus)):
        for b in range(a+1,len(opus)):
            A,B = opus[a],opus[b]
            if None in (A["start"],A["end"],B["start"],B["end"]): continue
            ov = min(A["end"],B["end"]) - max(A["start"],B["start"])
            if ov > 4: print(f'opus#{A["id"]} vs opus#{B["id"]}: {ov:.0f}s')

def cmd_renumber(ranges_p, mine_p):
    mine = json.load(open(mine_p, encoding="utf-8"))
    rows = [(o["start"],o["end"],int(o["id"]),"opusclip") for o in json.load(open(ranges_p,encoding="utf-8")) if o["start"] is not None]
    rows += [(c["start"],c["end"],int(c["id"]),"new") for c in mine]
    rows.sort(key=lambda r:(r[0],r[1]))
    for new,r in enumerate(rows,1): print(f"#{r[2]} -> #{new} ({r[3]})")

if __name__ == "__main__":
    a = sys.argv
    need = {"clips": 5, "locate": 5, "audit": 4, "renumber": 4}
    if len(a) < 2 or a[1] not in need or len(a) < need[a[1]]:
        print(__doc__); sys.exit(2)
    if a[1] == "clips": cmd_clips(a[2], a[3], a[4:])
    elif a[1] == "locate": cmd_locate(a[2], a[3], a[4])
    elif a[1] == "audit": cmd_audit(a[2], a[3])
    elif a[1] == "renumber": cmd_renumber(a[2], a[3])
