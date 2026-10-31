import hashlib, json, subprocess, sys, time
from pathlib import Path

REPO = Path.home() / "p2-g1"
IDS = ["IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442","IMP-0448","IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468","IMP-0470"]

def norm_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}
out = {}
for uid in IDS:
    art = REPO / units[uid]["output_path"]
    sha_pre = norm_sha(art)
    pdir = REPO / "command-center/p2-wave/probes" / uid
    probes = sorted(p for p in pdir.glob("probe*.py"))
    runs = []
    ok = True
    for p in probes:
        t0 = time.time()
        try:
            cp = subprocess.run([sys.executable, "-B", str(p)], cwd=str(pdir),
                                capture_output=True, text=True, timeout=900)
            rc, tail = cp.returncode, (cp.stdout + cp.stderr).strip().splitlines()[-3:]
        except subprocess.TimeoutExpired:
            rc, tail = "TIMEOUT", ["killed at 900s"]
        dur = round(time.time() - t0, 1)
        runs.append({"probe": p.name, "rc": rc, "secs": dur, "tail": [t[:160] for t in tail]})
        if rc != 0:
            ok = False
    sha_post = norm_sha(art)
    out[uid] = {"probes_ok": ok, "artifact_mutated": sha_pre != sha_post, "runs": runs}
    print(uid, "PROBES_OK" if ok and sha_pre == sha_post else "PROBE-FAIL",
          "| mutated:", sha_pre != sha_post,
          "|", ", ".join("%s rc=%s %ss" % (r["probe"], r["rc"], r["secs"]) for r in runs))
    for r in runs:
        if r["rc"] != 0:
            for t in r["tail"]: print("      >", t)
(REPO/"_p2shard14-w3-review/r2-probe-results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
