"""SYNTHESIS-REVIEW pass 2: gate-name reachability, READY-UNITS shape, py pins."""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = {}


def run(args, cwd=ROOT):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


# ---- A: where do the named gate ids actually live? --------------------------
wfdir = os.path.join(ROOT, ".github", "workflows")
names = ["gate-p2-delivery", "gate-skill-deploy-hop", "cs-wiring", "cs_wiring_check",
         "casualty_guard", "launchpath", "wf_gate", "wf-timeout", "deploy_skills_daily",
         "test_deploy_skills_daily", "gate-secrets", "gitleaks", "suitefloor",
         "charter_check", "p13_emit_receipt"]
hits = {n: [] for n in names}
for fn in sorted(os.listdir(wfdir)):
    if not fn.endswith((".yml", ".yaml")):
        continue
    with open(os.path.join(wfdir, fn), encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    for i, ln in enumerate(lines, 1):
        for n in names:
            if n in ln:
                hits[n].append(f"{fn}:{i}: {ln.strip()[:150]}")
out["gate_name_hits"] = {k: v[:6] for k, v in hits.items()}
out["gate_name_counts"] = {k: len(v) for k, v in hits.items()}
out["workflow_files"] = sorted(f for f in os.listdir(wfdir) if f.endswith((".yml", ".yaml")))

# ---- B: p13_emit_receipt.py anywhere? ---------------------------------------
rc, so, _ = run(["git", "ls-files", "*p13*"])
out["p13_tracked"] = so.splitlines()
found = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
    for f in filenames:
        if "p13" in f:
            found.append(os.path.relpath(os.path.join(dirpath, f), ROOT).replace("\\", "/"))
out["p13_ondisk"] = found[:20]

# ---- C: READY-UNITS.json shape ----------------------------------------------
p = os.path.join(ROOT, "command-center", "READY-UNITS.json")
with open(p, encoding="utf-8", errors="replace") as fh:
    ru = json.load(fh)
out["ready_units_keys"] = list(ru.keys()) if isinstance(ru, dict) else None
out["ready_units_head"] = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} len={len(v)}>")
                           for k, v in list(ru.items())[:30]} if isinstance(ru, dict) else None
# also check the git blob (working copy is dirty per sibling)
rc, so, _ = run(["git", "show", "HEAD:command-center/READY-UNITS.json"])
try:
    ru_blob = json.loads(so)
    out["ready_units_blob_keys"] = list(ru_blob.keys()) if isinstance(ru_blob, dict) else None
    out["ready_units_blob_head"] = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} len={len(v)}>")
                                    for k, v in list(ru_blob.items())[:30]} if isinstance(ru_blob, dict) else None
except Exception as e:  # noqa: BLE001
    out["ready_units_blob_keys"] = f"ERR {e!r}"

# ---- D: python-version pins per job -----------------------------------------
q = open(os.path.join(wfdir, "quality.yml"), encoding="utf-8", errors="replace").read()
pins = []
cur = None
for i, ln in enumerate(q.splitlines(), 1):
    m = re.match(r"^  ([a-zA-Z0-9][a-zA-Z0-9_-]*):\s*$", ln)
    if m:
        cur = m.group(1)
    m2 = re.search(r"python-version:\s*['\"]?([0-9.x]+)", ln)
    if m2:
        pins.append({"job": cur, "line": i, "ver": m2.group(1)})
out["py_pins"] = pins

# ---- E: charter file ---------------------------------------------------------
cc = open(os.path.join(ROOT, ".quality", "charter_check.sh"), encoding="utf-8", errors="replace").read()
out["charter_check_sh"] = cc
qd = os.path.join(ROOT, ".quality")
out["quality_dir"] = sorted(os.listdir(qd)) if os.path.isdir(qd) else None

# ---- F: blobread tests exist? -------------------------------------------------
rc, so, _ = run(["git", "ls-files", "tools/measure-guard"])
out["measure_guard_files"] = so.splitlines()

print(json.dumps(out, indent=1))
