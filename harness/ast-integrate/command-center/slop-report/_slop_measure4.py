"""SLOP measurement 4: provenance-chain break (ignored scripts cited by committed
receipts), liveness of zero-ref files, the 77-files/735KB claim, empty dirs,
ignored-surface breakdown, NUL via \\?\\, skills parity test search."""

import json
import os
import re
import subprocess
import time

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure4.out.json"
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
tracked = sorted(set(lines(o)))
_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = lines(o)
_, o, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = lines(o)

text_ext = (
    ".md",
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".ps1",
    ".sh",
    ".mjs",
    ".toml",
)
corpus = []
for p in tracked:
    if not p.endswith(text_ext):
        continue
    fp = os.path.join(REPO, p)
    try:
        if os.path.getsize(fp) > 8_000_000:
            continue
        with open(fp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            corpus.append((p, fh.read()))
    except OSError:
        pass
res["corpus_n"] = len(corpus)

# ---- 1. PROVENANCE BREAK: ignored files cited by COMMITTED artifacts ----
cc = REPO + "/command-center"
ign_scripts = [
    f
    for f in ignored
    if f.startswith("command-center/")
    and f.count("/") == 1
    and os.path.basename(f).startswith("_")
    and f.endswith(".py")
]
prov = {}
for p in ign_scripts:
    b = os.path.basename(p)
    hits = [q for q, body in corpus if b in body]
    prov[p] = hits
res["ignored_scripts_n"] = len(ign_scripts)
res["ignored_scripts_cited"] = {k: v[:6] for k, v in prov.items() if v}
res["ignored_scripts_cited_n"] = sum(1 for v in prov.values() if v)
res["ignored_scripts_uncited"] = sorted(k for k, v in prov.items() if not v)
res["ignored_scripts_uncited_n"] = len(res["ignored_scripts_uncited"])
res["ignored_scripts_cited_bytes"] = sum(
    os.path.getsize(os.path.join(REPO, k)) for k, v in prov.items() if v
)
res["ignored_scripts_top_cited"] = sorted(
    ((len(v), k) for k, v in prov.items() if v), reverse=True
)[:12]

# ---- 2. LIVENESS of the zero-ref set (are they sibling lanes writing NOW?) ----
zero = [
    "command-center/grounding/SKILLS2-GROUNDING.md",
    "command-center/hook-audit/H1-INVENTORY.json",
    "command-center/hook-audit/_h1_inventory.py",
    "command-center/p2-next/P2NEXT-GROUNDING.md",
    "command-center/ssot/clone-measurements.json",
    "command-center/ssot/measure_clones.py",
    "command-center/ssot/measure_unique_depth.py",
    "docs/_LANE-DOCS-GROUNDING.md",
    "docs/_lane_docs_detector.py",
    "docs/mcp-audit/MCP-FLEET-AUDIT.md",
    "docs/rule-audit/RULERESEARCH-GROUNDING.md",
    "docs/rule-audit/_probe_rule_inventory.py",
    "docs/rule-audit/_probe_summarize.py",
    "docs/rule-audit/_rule-inventory.json",
    "docs/ssot/SSOT-CLONE-INVENTORY.md",
    "command-center/_synthrev_commitmsg.txt",
    "command-center/p2-wave/_i3_blobfmt.out.json",
]
now = time.time()
res["liveness"] = {}
for p in zero:
    fp = os.path.join(REPO, p)
    if os.path.exists(fp):
        st = os.stat(fp)
        res["liveness"][p] = {
            "bytes": st.st_size,
            "age_min": round((now - st.st_mtime) / 60, 1),
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }
    else:
        res["liveness"][p] = {"exists": False}
# CONTROL for the mtime probe: a long-committed file must read OLD
for ctl in ["README.md", "QUALITY-CHARTER.md"]:
    fp = os.path.join(REPO, ctl)
    st = os.stat(fp)
    res["liveness"]["CONTROL_" + ctl] = {
        "bytes": st.st_size,
        "age_min": round((now - st.st_mtime) / 60, 1),
    }

# ---- 3. the 77-files / 735 KB commit ----
rc, so, _ = git("show", "--stat", "--format=%H%n%an%n%ad%n%s%n%b", "18798852")
res["commit_18798852"] = lines(so)[:40]
rc, so, _ = git("show", "--name-only", "--format=", "18798852")
res["commit_18798852_files"] = lines(so)[:25]

# ---- 4. empty directories ----
empty = []
for dp, dn, fn in os.walk(REPO):
    parts = dp.replace("\\", "/").split("/")
    if ".git" in parts or "node_modules" in parts:
        dn[:] = [d for d in dn if d not in (".git", "node_modules")]
        continue
    if not fn and not dn:
        empty.append(os.path.relpath(dp, REPO).replace("\\", "/"))
res["empty_dirs"] = sorted(empty)
res["empty_dirs_n"] = len(empty)

# ---- 5. ignored surface by top-2 dir ----
agg = {}
for p in ignored:
    key = "/".join(p.split("/")[:2]) if "/" in p else "(root)"
    a = agg.setdefault(key, {"n": 0, "b": 0})
    a["n"] += 1
    try:
        a["b"] += os.path.getsize(os.path.join(REPO, p))
    except OSError:
        pass
res["ignored_by_dir"] = dict(sorted(agg.items(), key=lambda kv: -kv[1]["b"])[:22])

# ---- 6. NUL via extended-length path (2nd independent signal) ----
res["NUL2"] = {}
try:
    res["NUL2"]["extended_isfile"] = os.path.isfile(
        "\\\\?\\" + REPO.replace("/", "\\") + "\\NUL"
    )
    res["NUL2"]["extended_size"] = os.path.getsize(
        "\\\\?\\" + REPO.replace("/", "\\") + "\\NUL"
    )
except OSError as ex:
    res["NUL2"]["err"] = str(ex)
r = subprocess.run(
    ["cmd", "/c", "dir", "/a", "/b", REPO.replace("/", "\\") + "\\NUL"],
    capture_output=True,
    text=True,
)
res["NUL2"]["cmd_dir_rc"] = r.returncode
res["NUL2"]["cmd_dir_out"] = (r.stdout or r.stderr).strip()[:200]

# ---- 7. skills-parity test search ----
pat = re.compile(r"\.agents/skills", re.I)
hits = []
for p, body in corpus:
    if not (p.endswith(".py") or p.endswith(".ps1") or p.endswith(".yml")):
        continue
    if pat.search(body) and ("skills/" in body):
        if "test" in p.lower() or "parity" in p.lower() or "drift" in p.lower():
            hits.append(p)
res["skills_parity_tests"] = sorted(set(hits))[:20]


# and the divergence: real content files only (drop pycache)
def nameset(rel):
    fp = os.path.join(REPO, rel)
    out = set()
    for dp, dn, fn in os.walk(fp):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith((".pyc", ".pyo")):
                continue
            out.add(os.path.relpath(os.path.join(dp, f), fp).replace("\\", "/"))
    return out


a, b = nameset("skills"), nameset(".agents/skills")
res["skills_parity_clean"] = {
    "skills": len(a),
    "agents": len(b),
    "shared": len(a & b),
    "only_skills": sorted(a - b)[:25],
    "only_skills_n": len(a - b),
    "only_agents_n": len(b - a),
}
# top-level skill dirs present in one root only
ta = {x.split("/")[0] for x in a}
tb = {x.split("/")[0] for x in b}
res["skills_toplevel_only_skills"] = sorted(ta - tb)
res["skills_toplevel_only_agents"] = sorted(tb - ta)

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("corpus:", res["corpus_n"])
print("=== PROVENANCE BREAK ===")
print(
    " ignored cc root scripts:",
    res["ignored_scripts_n"],
    "CITED by committed:",
    res["ignored_scripts_cited_n"],
    f"({res['ignored_scripts_cited_bytes']} B)",
    "uncited:",
    res["ignored_scripts_uncited_n"],
)
print(" top cited:", res["ignored_scripts_top_cited"][:8])
print("=== LIVENESS ===")
for k, v in res["liveness"].items():
    print(f"  {k:52s} {v}")
print("=== commit 18798852 ===")
for ln in res["commit_18798852"][:14]:
    print("  ", ln)
print("  files:", res["commit_18798852_files"][:8])
print("=== empty dirs ===", res["empty_dirs_n"], res["empty_dirs"])
print("=== ignored by dir ===")
for k, v in res["ignored_by_dir"].items():
    print(f"  {k:42s} {v['n']:6d} files {v['b']:11d} B")
print("=== NUL2 ===", res["NUL2"])
print("=== skills parity tests ===", res["skills_parity_tests"])
print(
    "=== skills parity clean ===",
    {k: v for k, v in res["skills_parity_clean"].items() if not isinstance(v, list)},
)
print("  only_skills sample:", res["skills_parity_clean"]["only_skills"][:10])
print("  toplevel only in skills/:", res["skills_toplevel_only_skills"])
print("  toplevel only in .agents/skills/:", res["skills_toplevel_only_agents"])
