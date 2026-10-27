#!/usr/bin/env python3
"""Independent reviewer w4 shard17 r2 - live probe re-run battery.
Re-runs ALL named_probes from each unit's SUBAGENT-RETURN.json, exit 0 required.
Mutation guard: sha256 (raw + CRLF->LF) of receipt artifacts and probe scripts
snapshotted before and after all runs; equality required.
Writes probe_rerun.json.
"""
import hashlib, json, os, re, subprocess, time
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["TST-0032","TST-0057","TST-0060","TST-0066","TST-0067","TST-0068",
         "TST-0070","TST-0081","TST-0085","TST-0088","TST-0090","TST-0091"]
TIMEOUT_S = 240

def sha_raw(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def sha_lf(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def snapshot():
    files = []
    for uid in UNITS:
        files.append(REPO / ("command-center/receipts/%s.json" % uid))
        pd = REPO / ("command-center/p2-wave/probes/" + uid)
        if pd.is_dir():
            files.extend(sorted(x for x in pd.iterdir() if x.is_file()))
    return {str(f.relative_to(REPO)).replace("\\", "/"): {"raw": sha_raw(f), "lf": sha_lf(f)}
            for f in files if f.is_file()}

cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

ENV_RX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

def run_one(cmd):
    tokens = cmd.split()
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = []
    for i, t in enumerate(tokens):
        m = ENV_RX.match(t)
        if m and not argv:
            env[m.group(1)] = m.group(2)
            continue
        argv = tokens[i:]
        break
    if not argv:
        return {"ok": False, "reason": "no-argv", "cmd": cmd}
    exe = argv[0]
    if exe in ("python3", "python"):
        argv[0] = sys_exec
    t0 = time.time()
    try:
        cp = subprocess.run(argv, cwd=str(REPO), env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        dt = time.time() - t0
        out = (cp.stdout or "") + (cp.stderr or "")
        marker = "SUCCESS" if re.search(r"SUCCESS[:\b]", out) else ("FAILED" if re.search(r"FAILED[:\b]", out) else "NONE")
        return {"ok": cp.returncode == 0, "exit": cp.returncode, "dur_s": round(dt, 1),
                "marker": marker, "tail": out[-400:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": "TIMEOUT", "dur_s": TIMEOUT_S, "marker": "TIMEOUT",
                "tail": "killed after %ss" % TIMEOUT_S}
    except Exception as e:
        return {"ok": False, "exit": "ERROR", "reason": str(e)[:150], "cmd": cmd}

import sys
sys_exec = sys.executable

before = snapshot()
results = {}
total = passes = 0
for uid in UNITS:
    ret_p = REPO / ("command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid)
    ret = json.loads(ret_p.read_text(encoding="utf-8"))
    nps = ret.get("named_probes") or []
    results[uid] = {}
    for np in nps:
        pid = str(np.get("id") or "probe")
        cmd = str(np.get("command") or "")
        total += 1
        r = run_one(cmd)
        if r.get("ok"):
            passes += 1
        results[uid][pid] = {"cmd": cmd, **r}
        print("%s %s: %s exit=%s marker=%s dur=%s" % (
            uid, pid, "PASS" if r.get("ok") else "FAIL", r.get("exit"), r.get("marker"), r.get("dur_s")),
            flush=True)

after = snapshot()
mutated = [k for k in before if k in after and before[k] != after[k]]
added = [k for k in after if k not in before]
removed = [k for k in before if k not in after]

out = {"_meta": {"utc": datetime.now(timezone.utc).isoformat(),
                 "probe_total": total, "probe_pass": passes,
                 "mutated": mutated, "added": added, "removed": removed},
       "units": results}
(REPO/"_reviewer-w4-shard17-r2"/"probe_rerun.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print("TOTAL %d/%d pass; mutated=%d added=%d removed=%d" % (
    passes, total, len(mutated), len(added), len(removed)))
