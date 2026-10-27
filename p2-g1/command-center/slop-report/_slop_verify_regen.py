"""Bucket-(c) regenerability PROOF by execution, plus full frozen-fixture layout.

Blast radius is one throwaway cache dir created under the slop-report folder; the
repo's own caches are only MEASURED, never removed.
"""

import hashlib
import json
import os
import shutil
import subprocess
import time

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SB = REPO + "/command-center/slop-report/_regen_sandbox"
OUT = REPO + "/command-center/slop-report/_slop_verify_regen.out.json"
res = {}


def lines(s):
    return [x for x in s.replace("\r\n", "\n").split("\n") if x.strip()]


# ---------- PROOF 1: __pycache__ regenerates from source ----------
shutil.rmtree(SB, ignore_errors=True)
os.makedirs(SB + "/pkg", exist_ok=True)
with open(SB + "/pkg/mod.py", "w", encoding="utf-8", newline="\n") as fh:
    fh.write('"""Sandbox module."""\n\n\ndef f():\n    """Doc."""\n    return 1\n')
pyc_dir = SB + "/pkg/__pycache__"
res["pycache_before"] = os.path.isdir(pyc_dir)  # expect False
r = subprocess.run(
    ["python", "-c", "import mod"], cwd=SB + "/pkg", capture_output=True, text=True
)
res["pycache_import_rc"] = r.returncode
res["pycache_after"] = os.path.isdir(pyc_dir)  # expect True
res["pycache_files"] = sorted(os.listdir(pyc_dir)) if os.path.isdir(pyc_dir) else []
# delete and regenerate -> byte-identical?
h1 = None
if res["pycache_files"]:
    with open(os.path.join(pyc_dir, res["pycache_files"][0]), "rb") as fh:
        h1 = hashlib.sha256(fh.read()).hexdigest()[:16]
shutil.rmtree(pyc_dir, ignore_errors=True)
res["pycache_deleted"] = not os.path.isdir(pyc_dir)  # expect True
subprocess.run(
    ["python", "-c", "import mod"], cwd=SB + "/pkg", capture_output=True, text=True
)
h2 = None
if os.path.isdir(pyc_dir):
    fl = sorted(os.listdir(pyc_dir))
    if fl:
        with open(os.path.join(pyc_dir, fl[0]), "rb") as fh:
            h2 = hashlib.sha256(fh.read()).hexdigest()[:16]
res["pycache_regen_sha_before"] = h1
res["pycache_regen_sha_after"] = h2
res["pycache_regen_identical"] = h1 is not None and h1 == h2
res["PROOF_pycache"] = (
    res["pycache_before"] is False
    and res["pycache_after"] is True
    and res["pycache_deleted"] is True
    and res["pycache_regen_identical"] is True
)

# ---------- PROOF 2: .ruff_cache regenerates ----------
rc_dir = SB + "/.ruff_cache"
shutil.rmtree(rc_dir, ignore_errors=True)
res["ruffcache_before"] = os.path.isdir(rc_dir)  # expect False
r = subprocess.run(
    ["uvx", "ruff@0.15.17", "check", "--cache-dir", rc_dir, "pkg/mod.py"],
    cwd=SB,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
res["ruffcache_rc"] = r.returncode
res["ruffcache_after"] = os.path.isdir(rc_dir)  # expect True
n = 0
for dp, dn, fn in os.walk(rc_dir):
    n += len(fn)
res["ruffcache_files"] = n
res["PROOF_ruffcache"] = (
    res["ruffcache_before"] is False and res["ruffcache_after"] is True and n > 0
)

# ---------- PROOF 3: .pytest_cache regenerates ----------
pt_dir = SB + "/.pytest_cache"
with open(SB + "/test_sb.py", "w", encoding="utf-8", newline="\n") as fh:
    fh.write('"""T."""\n\n\ndef test_ok():\n    """T."""\n    assert True\n')
shutil.rmtree(pt_dir, ignore_errors=True)
res["pytestcache_before"] = os.path.isdir(pt_dir)
r = subprocess.run(
    ["python", "-m", "pytest", "-q", "test_sb.py", "-p", "no:cacheprovider"],
    cwd=SB,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
res["pytest_nocache_rc"] = r.returncode
res["pytestcache_after_nocache"] = os.path.isdir(pt_dir)  # expect False (control)
r = subprocess.run(
    ["python", "-m", "pytest", "-q", "test_sb.py"],
    cwd=SB,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
res["pytest_rc"] = r.returncode
res["pytestcache_after"] = os.path.isdir(pt_dir)  # expect True
res["PROOF_pytestcache"] = (
    res["pytestcache_before"] is False and res["pytestcache_after"] is True
)

shutil.rmtree(SB, ignore_errors=True)
res["sandbox_removed"] = not os.path.isdir(SB)

# ---------- full p2-wave frozen-fixture layout ----------
p2 = REPO + "/command-center/p2-wave/probes"
layout = {}
for d in sorted(os.listdir(p2)):
    dd = os.path.join(p2, d)
    ents = []
    for x in sorted(os.listdir(dd)):
        xp = os.path.join(dd, x)
        ents.append(
            {
                "name": x,
                "dir": os.path.isdir(xp),
                "bytes": (0 if os.path.isdir(xp) else os.path.getsize(xp)),
            }
        )
    layout[d] = ents
res["p2wave_layout"] = layout
res["control_named_entries"] = sorted(
    f"command-center/p2-wave/probes/{d}/{e['name']}"
    for d, es in layout.items()
    for e in es
    if e["name"].lower().startswith(("control", "fixture"))
)
res["control_dirs_only"] = sorted(
    f"command-center/p2-wave/probes/{d}/{e['name']}"
    for d, es in layout.items()
    for e in es
    if e["dir"] and e["name"].lower().startswith("control")
)


# ---------- live cache footprint restated (measured, NOT deleted) ----------
def walkcount(pred):
    n = b = 0
    for dp, dn, fn in os.walk(REPO):
        parts = dp.replace("\\", "/").split("/")
        if ".git" in parts:
            dn[:] = []
            continue
        if not pred(parts):
            continue
        for f in fn:
            try:
                b += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return {"files": n, "bytes": b}


res["measured_caches"] = {
    "__pycache__": walkcount(lambda p: "__pycache__" in p),
    ".pytest_cache": walkcount(lambda p: ".pytest_cache" in p),
    ".ruff_cache": walkcount(lambda p: ".ruff_cache" in p),
}
# is any cache inside a frozen-evidence dir? (must be zero before any sweep)
frozen_pref = ["command-center/casualty/probes", "command-center/p2-wave/probes"]
bad = []
for dp, dn, fn in os.walk(REPO):
    rel = os.path.relpath(dp, REPO).replace("\\", "/")
    if any(rel.startswith(f) for f in frozen_pref) and (
        "__pycache__" in rel or ".pytest_cache" in rel or ".ruff_cache" in rel
    ):
        bad.append(rel)
res["caches_inside_frozen"] = bad

# .ruff_cache mtime -- my own ruff runs should have just refreshed it (live evidence)
rp = os.path.join(REPO, ".ruff_cache")
if os.path.isdir(rp):
    res["repo_ruff_cache_age_min"] = round((time.time() - os.stat(rp).st_mtime) / 60, 1)

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

for k in ["PROOF_pycache", "PROOF_ruffcache", "PROOF_pytestcache"]:
    print(k, "=", res[k])
print(
    "pycache:",
    res["pycache_before"],
    "->",
    res["pycache_after"],
    "del",
    res["pycache_deleted"],
    "regen-identical",
    res["pycache_regen_identical"],
    res["pycache_regen_sha_before"],
    res["pycache_regen_sha_after"],
)
print(
    "ruffcache:",
    res["ruffcache_before"],
    "->",
    res["ruffcache_after"],
    res["ruffcache_files"],
    "files",
)
print(
    "pytestcache: control(no:cacheprovider)=",
    res["pytestcache_after_nocache"],
    " normal=",
    res["pytestcache_after"],
    " rc",
    res["pytest_rc"],
)
print("sandbox removed:", res["sandbox_removed"])
print("measured caches:", json.dumps(res["measured_caches"]))
print("caches inside frozen dirs (must be []):", res["caches_inside_frozen"])
print("repo .ruff_cache age min:", res.get("repo_ruff_cache_age_min"))
print("control-named frozen entries:")
for c in res["control_named_entries"]:
    print("   ", c)
print("control DIRS only (what a */control/ glob protects):", res["control_dirs_only"])
