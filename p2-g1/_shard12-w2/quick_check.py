import json, hashlib, os
ids = ["IMP-0165","IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0218","IMP-0219","IMP-0221","IMP-0222","IMP-0224","IMP-0228"]
root = os.path.join(os.path.expanduser("~"), "p2-g1")
ND = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
for uid in ids:
    reldir = os.path.join("command-center","p2-wave","probes",uid)
    pd = os.path.join(root, reldir)
    out_rel = "command-center/receipts/%s.json" % uid
    out = os.path.join(root, out_rel.replace("/","\\"))
    sha = None; size = 0
    if os.path.isfile(out):
        raw = open(out,"rb").read().replace(b"\r\n", b"\n")
        sha = hashlib.sha256(raw).hexdigest(); size = len(raw)
    ret = os.path.join(pd, "SUBAGENT-RETURN.json")
    man = os.path.join(pd, "UNIT-ARTIFACT-MANIFEST.json")
    ret_status = None; man_rows = []
    if os.path.isfile(ret):
        try:
            r = json.load(open(ret, encoding="utf-8"))
            ret_status = r.get("status") or r.get("state")
        except Exception as e:
            ret_status = "UNPARSEABLE:" + type(e).__name__
    if os.path.isfile(man):
        try:
            m = json.load(open(man, encoding="utf-8"))
            for a in (m.get("artifacts") or []):
                if a.get("unit_id") == uid:
                    man_rows.append((str(a.get("path","")).replace("\\","/"), a.get("sha256"), a.get("present")))
        except Exception:
            man_rows = [("UNPARSEABLE","","")]
    match = any(p_ == out_rel and s_ == sha and present is True for (p_, s_, present) in man_rows) if sha else False
    print(uid, "sha=" + (sha[:12] if sha else "NONE"), "bytes=%d" % size,
          "ret=" + str(ret_status),
          "manifest_rows=" + str(len(man_rows)),
          "SHA_MATCH=" + str(match))
