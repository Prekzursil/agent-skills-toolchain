import json, hashlib, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
MINE = ['CNF-0149','CNF-0152','CNF-0164','CNF-0167','CNF-0169','CNF-0171','CNF-0172','CNF-0177','CNF-0184','CNF-0188','CNF-0191','CNL-0078']
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}

def digest_file(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def norm(p):
    return str(p).replace("\\", "/")

with open(REPO/"command-center"/"WORK-UNIT-CATALOG.json", encoding="utf-8") as f:
    cat = json.load(f)
units = {u["id"]: u for u in cat["work_units"] if u["id"] in MINE}

report = {}
for uid in MINE:
    u = units[uid]
    out_rel = norm(u["output_path"])
    out = REPO / out_rel
    issues = []
    if not out.is_file() or out.stat().st_size <= 0:
        issues.append("ARTIFACT-MISSING")
    else:
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
            st = str(doc.get("state") or "").upper()
            if st in NOT_DELIVERING:
                issues.append("self-declared:" + st)
            sentinel = u.get("completion_sentinel","")
            if sentinel and sentinel not in text:
                issues.append("sentinel-absent")
        except Exception as e:
            issues.append("unparseable:" + type(e).__name__)
        live_sha, live_bytes = digest_file(out)
        man_p = REPO / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = [a for a in man.get("artifacts",[]) if isinstance(a,dict) and a.get("unit_id")==uid]
            match = [a for a in rows if norm(a.get("path",""))==out_rel and str(a.get("sha256",""))==live_sha and a.get("present") is True]
            if not match:
                issues.append("MANIFEST-SHA-MISMATCH live_sha=" + live_sha[:12] + " bytes=" + str(live_bytes) + " rows=" + str(len(rows)))
        except FileNotFoundError:
            issues.append("MANIFEST-MISSING")
        ret_p = REPO / ("command-center/p2-wave/probes/" + uid + "/SUBAGENT-RETURN.json")
        try:
            ret = json.loads(ret_p.read_text(encoding="utf-8"))
            st_ret = str(ret.get("status") or ret.get("state") or "").upper()
            if st_ret in NOT_DELIVERING:
                issues.append("return:" + st_ret)
            nprobes = ret.get("named_probes")
            if not nprobes:
                issues.append("no-named-probes-in-return")
        except FileNotFoundError:
            issues.append("SUBAGENT-RETURN-MISSING")
    rev = None
    rp = REPO / ("command-center/receipts/" + uid + ".json")
    if rp.is_file():
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
            rv = r.get("reviewer")
            if isinstance(rv, dict):
                rev = {"verdict": rv.get("verdict"), "independent": rv.get("independent")}
            else:
                rev = {"raw": str(rv)[:60]}
        except Exception as e:
            rev = {"err": type(e).__name__}
    report[uid] = {"output_path": out_rel, "issues": issues, "reviewer": rev}
    ok = "GREEN" if not issues else "BAD  "
    print(uid, ok, "rev=", rev, "issues=", issues if issues else "none")
with open(Path(__file__).parent / "static-check.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
