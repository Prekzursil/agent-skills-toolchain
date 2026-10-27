import json, hashlib
from pathlib import Path
REPO = Path.home() / "p2-g1"
ids = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468','IMP-0470']
def digest(p):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
print(f"{'unit':9} {'state':8} {'verdict':7} {'ind':5} {'reviewer':30} {'sha-match':9} gated")
results = {}
for i in ids:
    rp = REPO / f"command-center/receipts/{i}.json"
    r = json.loads(rp.read_text(encoding="utf-8"))
    man = json.loads((REPO / f"command-center/p2-wave/probes/{i}/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    rev = r.get("reviewer") or {}
    live_sha = digest(rp)
    out_rel = f"command-center/receipts/{i}.json"
    mrow = [a for a in man.get("artifacts", []) if a.get("unit_id") == i]
    sha_ok = any(str(a.get("path")).replace("\\", "/") == out_rel and a.get("sha256") == live_sha and a.get("present") is True for a in mrow)
    blob = json.dumps(r).lower()
    gated = "owner_gate" in r or "gate_reason" in r
    reviewer = str(rev.get("reviewer") or rev.get("identity") or rev.get("model") or "?")
    print(f"{i:9} {str(r.get('state')):8} {str(rev.get('verdict')):7} {str(rev.get('independent')):5} {reviewer:30} {str(sha_ok):9} {gated}")
    results[i] = {"state": r.get("state"), "verdict": rev.get("verdict"), "independent": rev.get("independent"),
                  "reviewer": reviewer, "sha_match": sha_ok, "owner_gated": gated,
                  "receipt_sha": live_sha}
out = REPO / "_p2shard14-w3" / "verify-results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
print("wrote", out)
