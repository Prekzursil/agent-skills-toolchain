"""SLOP measurement 6: PRIOR ART search, NUL growth + writer, dual-write guard state,
cache footprint, codex-* stub content, frozen-dir hashes, ruff attribution."""

import hashlib
import json
import os
import re
import subprocess
import time

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure6.out.json"
res = {}


def git(*a):
    r = subprocess.run(
        ["git", "-C", REPO] + list(a),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


def lines(s):
    return [x for x in s.replace("\r\n", "\n").split("\n") if x.strip()]


_, o, _ = git("ls-files")
tracked = set(lines(o))

# ---- 1. PRIOR ART: existing scratch/slop/cleanup tooling ----
pats = ["scratch", "slop", "cleanup", "clean_", "prune", "orphan", "stale", "junk"]
hits = {}
for p in sorted(tracked):
    if not p.endswith((".py", ".ps1", ".sh", ".md", ".yml", ".yaml", ".mjs", ".js")):
        continue
    base = os.path.basename(p).lower()
    for pat in pats:
        if pat in base:
            hits.setdefault(pat, []).append(p)
res["prior_art_by_name"] = hits
# no-runtime-junk gate (mentioned in memory)
rc, so, _ = git("grep", "-rln", "no-runtime-junk", "--", ".")
res["no_runtime_junk_refs"] = lines(so)[:15]
rc, so, _ = git("grep", "-rln", "scratch", "--", ".github", "ci", "scripts")
res["scratch_refs_in_gates"] = lines(so)[:20]
# the memory line: "Scratch-rule deleted 9 deliverables"
rc, so, _ = git("log", "--all", "--oneline", "--grep", "scratch", "-i")
res["scratch_commits"] = lines(so)[:20]

# ---- 2. NUL growth + writer ----
nulp = "\\\\?\\" + REPO.replace("/", "\\") + "\\NUL"
r1 = os.path.getsize(nulp)
time.sleep(2)
r2 = os.path.getsize(nulp)
st = os.stat(nulp)
with open(nulp, "r", encoding="utf-8", errors="replace", newline="") as fh:
    body = fh.read()
keys = sorted(set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]{0,24})"\s*:', body)))
res["NUL_growth"] = {
    "size_a": r1,
    "size_b": r2,
    "grew_in_2s": r2 > r1,
    "mtime_age_min": round((time.time() - st.st_mtime) / 60, 2),
    "json_keys": keys[:30],
    "n_records": body.count("\n"),
}
rc, so, _ = git(
    "grep", "-rn", "> *NUL", "--", "scripts", "ci", "hooks", "tools", "platform"
)
res["NUL_writers_grep"] = lines(so)[:15]
rc, so, _ = git("grep", "-rln", "NUL", "--", ".gitignore", "docs", "command-center")
res["NUL_mentions"] = lines(so)[:12]

# ---- 3. dual-write guard: run it read-only ----
res["dualwrite_run"] = {}
for guard in ["ci/check_skill_dual_write.py", "ci/check_skill_deploy_drift.py"]:
    gp = os.path.join(REPO, guard)
    if not os.path.exists(gp):
        res["dualwrite_run"][guard] = "ABSENT"
        continue
    r = subprocess.run(
        ["python", guard],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    res["dualwrite_run"][guard] = {
        "rc": r.returncode,
        "stdout_tail": lines(r.stdout)[-12:],
        "stderr_tail": lines(r.stderr)[-6:],
    }

# ---- 4. cache footprint repo-wide ----
cache = {
    "__pycache__": [0, 0],
    ".pytest_cache": [0, 0],
    ".ruff_cache": [0, 0],
    "other_pyc": [0, 0],
    "egg_info": [0, 0],
}
for dp, dn, fn in os.walk(REPO):
    parts = dp.replace("\\", "/").split("/")
    if ".git" in parts:
        dn[:] = []
        continue
    key = None
    if "__pycache__" in parts:
        key = "__pycache__"
    elif ".pytest_cache" in parts:
        key = ".pytest_cache"
    elif ".ruff_cache" in parts:
        key = ".ruff_cache"
    elif any(x.endswith(".egg-info") for x in parts):
        key = "egg_info"
    for f in fn:
        try:
            s = os.path.getsize(os.path.join(dp, f))
        except OSError:
            continue
        k = key
        if k is None and f.endswith(".pyc"):
            k = "other_pyc"
        if k:
            cache[k][0] += 1
            cache[k][1] += s
res["cache_footprint"] = {k: {"files": v[0], "bytes": v[1]} for k, v in cache.items()}
res["cache_total"] = {
    "files": sum(v[0] for v in cache.values()),
    "bytes": sum(v[1] for v in cache.values()),
}

# ---- 5. codex-* stub content ----
res["codex_stubs"] = {}
for s in ["codex-audit", "codex-review", "codex-triage"]:
    fp = os.path.join(REPO, ".agents/skills", s, "SKILL.md")
    if os.path.exists(fp):
        with open(fp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            res["codex_stubs"][s] = fh.read().replace("\r\n", "\n")
# is codex-orchestrate present in both roots?
for root in ["skills", ".agents/skills"]:
    res.setdefault("codex_orchestrate", {})[root] = os.path.isdir(
        os.path.join(REPO, root, "codex-orchestrate")
    )

# ---- 6. frozen dirs: hash manifest (proof of untouched) ----
frozen = ["command-center/casualty/probes"]
p2 = REPO + "/command-center/p2-wave/probes"
for d in sorted(os.listdir(p2)):
    c = f"command-center/p2-wave/probes/{d}/control"
    if os.path.isdir(os.path.join(REPO, c)):
        frozen.append(c)
res["frozen_manifest"] = {}
for fd in frozen:
    man = {}
    for dp, dn, fn in os.walk(os.path.join(REPO, fd)):
        for f in sorted(fn):
            fp = os.path.join(dp, f)
            with open(fp, "rb") as fh:
                man[os.path.relpath(fp, os.path.join(REPO, fd)).replace("\\", "/")] = (
                    hashlib.sha256(fh.read()).hexdigest()[:16]
                )
    rc, so, _ = git("status", "--porcelain", "--", fd)
    res["frozen_manifest"][fd] = {"n": len(man), "sha16": man, "dirty": lines(so)}
# also list ALL p2-wave probe subdirs (control dirs may not exist for each)
res["p2wave_probe_layout"] = {
    d: sorted(os.listdir(os.path.join(p2, d))) for d in sorted(os.listdir(p2))
}

# ---- 7. which output has a TRACKED producer ----
_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = [p for p in lines(o) if "/slop-report/" not in p]
_, o, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = set(lines(o))
ondisk = tracked | ignored | set(untracked)
tracked_producer = []
for p in untracked:
    if not re.search(r"\.(out|err)\.(json|txt)$", p):
        continue
    d, b = os.path.dirname(p), os.path.basename(p)
    stem = re.sub(r"\.(out|err)\.(json|txt)$", "", b)
    cand = f"{d}/{stem}.py" if d else f"{stem}.py"
    if cand in tracked:
        tracked_producer.append((p, cand))
res["outputs_with_TRACKED_producer"] = tracked_producer

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("=== PRIOR ART ===")
for k, v in res["prior_art_by_name"].items():
    print(f"  {k:10s} {len(v):3d}  {v[:6]}")
print(" no-runtime-junk:", res["no_runtime_junk_refs"][:8])
print(" scratch in gates:", res["scratch_refs_in_gates"][:10])
print(" scratch commits:", res["scratch_commits"][:8])
print("=== NUL ===", {k: v for k, v in res["NUL_growth"].items() if k != "json_keys"})
print("  keys:", res["NUL_growth"]["json_keys"])
print("  writers:", res["NUL_writers_grep"][:6])
print("=== dual-write run ===")
for k, v in res["dualwrite_run"].items():
    print(" ", k, v if isinstance(v, str) else f"rc={v['rc']}")
    if not isinstance(v, str):
        for ln in v["stdout_tail"][-8:]:
            print("     |", ln)
        for ln in v["stderr_tail"][-3:]:
            print("     !", ln)
print("=== cache ===", res["cache_footprint"], res["cache_total"])
print("=== codex stubs ===")
for k, v in res["codex_stubs"].items():
    print(f"  --- {k} ---")
    print("   ", v.replace("\n", " | ")[:300])
print("  codex-orchestrate present:", res["codex_orchestrate"])
print("=== frozen ===")
for k, v in res["frozen_manifest"].items():
    print(f"  {k:52s} n={v['n']:3d} dirty={len(v['dirty'])}")
print("=== p2wave layout ===", json.dumps(res["p2wave_probe_layout"])[:400])
print("=== outputs w/ TRACKED producer ===", res["outputs_with_TRACKED_producer"])
