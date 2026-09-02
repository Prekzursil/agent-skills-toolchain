"""SLOP measurement 3: reference KIND (use vs mention), the .gitignore
intent-vs-behaviour gap on probe scripts, parallel-folder census, NUL, advver."""

import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
MAIN = "C:/Users/Prekzursil/source/agent-skills-toolchain"
OUT = REPO + "/command-center/slop-report/_slop_measure3.out.json"
res = {}


def git(*a, cwd=REPO):
    r = subprocess.run(
        ["git", "-C", cwd] + list(a),
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
_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = [p for p in lines(o) if "/slop-report/" not in p]
_, o, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = set(lines(o))

# ---------- A. which .gitignore RULE ignores a probe script ----------
samples = [
    "command-center/_wfa5_build.py",
    "command-center/_a3_probe.py",
    "command-center/_baseline_probe.py",
    "platform/lib/_d3_measure_before.py",
]
res["check_ignore"] = {}
for s in samples:
    rc, so, se = git("check-ignore", "-v", "--", s)
    res["check_ignore"][s] = {"rc": rc, "rule": so.strip() or "(NOT IGNORED)"}

cc = REPO + "/command-center"
root_scripts = [
    f
    for f in os.listdir(cc)
    if f.startswith("_") and f.endswith(".py") and os.path.isfile(os.path.join(cc, f))
]
res["cc_root_probe_scripts_total"] = len(root_scripts)
res["cc_root_probe_scripts_tracked"] = sorted(
    f for f in root_scripts if "command-center/" + f in tracked
)
res["cc_root_probe_scripts_ignored"] = sorted(
    f for f in root_scripts if "command-center/" + f in ignored
)
res["cc_root_probe_scripts_tracked_n"] = len(res["cc_root_probe_scripts_tracked"])
res["cc_root_probe_scripts_ignored_n"] = len(res["cc_root_probe_scripts_ignored"])
res["cc_root_probe_scripts_ignored_bytes"] = sum(
    os.path.getsize(os.path.join(cc, f)) for f in res["cc_root_probe_scripts_ignored"]
)
# how did the 25 get tracked? check the .gitignore rule still matches them
rc, so, _ = git(
    "check-ignore",
    "-v",
    "--no-index",
    "--",
    *["command-center/" + f for f in res["cc_root_probe_scripts_tracked"][:5]],
)
res["tracked_scripts_still_match_rule"] = lines(so)

# ---------- B. reference KIND ----------
text_ext = (
    ".md",
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".ps1",
    ".sh",
    ".js",
    ".mjs",
    ".toml",
)
corpus = []
for p in sorted(tracked):
    if not p.endswith(text_ext):
        continue
    fp = os.path.join(REPO, p)
    try:
        if os.path.getsize(fp) > 6_000_000:
            continue
        with open(fp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            corpus.append((p, fh.read()))
    except OSError:
        pass

EXEC_PAT = re.compile(
    r'(subprocess\.[a-z_]+\([^)]*|python\s+|py\s+|import\s+|from\s+|"\s*|\'\s*)$'
)


def classify(basename):
    stem = basename[:-3] if basename.endswith(".py") else basename
    execs, cites = [], []
    for p, body in corpus:
        if p.endswith("/" + basename):
            continue
        if basename not in body:
            continue
        is_exec = False
        for m in re.finditer(re.escape(basename), body):
            pre = body[max(0, m.start() - 60) : m.start()]
            if re.search(
                r"(subprocess|python |run\(|\[\"python\"|check_call|"
                r"Popen|import |from )",
                pre,
            ):
                is_exec = True
                break
        if is_exec and p.endswith((".py", ".ps1", ".sh", ".yml", ".yaml")):
            execs.append(p)
        else:
            cites.append(p)
    return execs, cites, stem


# CONTROL: positive must show EXEC for the generator a tracked test runs
e, c, _ = classify("_gen_schema_substrate.py")
res["CONTROL_kind_positive"] = {
    "exec_hits": len(e),
    "cite_hits": len(c),
    "exec_sample": e[:5],
    "fires_exec": len(e) > 0,
}
e2, c2, _ = classify("_zzz_no_such_file_qx7.py")
res["CONTROL_kind_negative"] = {
    "exec_hits": len(e2),
    "cite_hits": len(c2),
    "silent": len(e2) + len(c2) == 0,
}

kind = {}
for p in untracked:
    b = os.path.basename(p)
    e, c, _ = classify(b)
    kind[p] = {"exec": e[:5], "exec_n": len(e), "cite": c[:5], "cite_n": len(c)}
res["untracked_kind"] = kind
res["untracked_executed_by_tracked"] = sorted(k for k, v in kind.items() if v["exec_n"])
res["untracked_cited_only"] = sorted(
    k for k, v in kind.items() if not v["exec_n"] and v["cite_n"]
)
res["untracked_zero_refs"] = sorted(
    k for k, v in kind.items() if not v["exec_n"] and not v["cite_n"]
)
res["n_exec"] = len(res["untracked_executed_by_tracked"])
res["n_cite"] = len(res["untracked_cited_only"])
res["n_zero"] = len(res["untracked_zero_refs"])


# ---------- C. parallel-folder census ----------
def tree_stat(rel):
    fp = os.path.join(REPO, rel)
    if not os.path.isdir(fp):
        return None
    n = b = 0
    tops = []
    for dp, dn, fn in os.walk(fp):
        if ".git" in dp:
            continue
        for f in fn:
            n += 1
            try:
                b += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    try:
        tops = sorted(os.listdir(fp))
    except OSError:
        pass
    return {"files": n, "bytes": b, "entries": len(tops), "sample": tops[:8]}


cand = [
    "skills",
    ".agents/skills",
    "skills-claude-only",
    "agents",
    ".agents",
    "commands",
    ".claude",
    ".claude-plugin",
    "harness-sota-2026-07-18-corpus",
    "apktool_mcp_server_workspace",
    "agent-self",
    "workflows",
    "agent-self/config/workflows",
    ".claude/workflows",
    "hooks",
    "rules",
    "platform",
    "tools",
    "docs",
    "guides",
    "ci",
    "release",
    "userscripts",
    "scripts",
    "command-center/harvest",
    "node_modules",
    ".provenance",
    ".quality",
    ".pytest_cache",
    ".ruff_cache",
    "command-center/__pycache__",
]
res["dirs"] = {c: tree_stat(c) for c in cand}
for c, v in res["dirs"].items():
    if v is None:
        continue
    rc, so, _ = git("ls-files", "--", c)
    v["tracked_files"] = len(lines(so))
    rc, so, _ = git("ls-files", "--others", "--exclude-standard", "--", c)
    v["untracked_files"] = len(lines(so))


# skills vs .agents/skills parity: is it byte-identical (sanctioned dual write)?
def name_set(rel):
    fp = os.path.join(REPO, rel)
    if not os.path.isdir(fp):
        return set()
    out = set()
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            out.add(os.path.relpath(os.path.join(dp, f), fp).replace("\\", "/"))
    return out


a = name_set("skills")
bset = name_set(".agents/skills")
res["skills_parity"] = {
    "skills_files": len(a),
    ".agents/skills_files": len(bset),
    "only_in_skills": sorted(a - bset)[:20],
    "only_in_skills_n": len(a - bset),
    "only_in_agents": sorted(bset - a)[:20],
    "only_in_agents_n": len(bset - a),
    "shared_n": len(a & bset),
}
# is there a committed parity test?
par = [
    p
    for p, b in corpus
    if "parity" in p.lower() and ("skills" in p.lower() or "dual" in b.lower())
]
res["parity_test_candidates"] = par[:12]

# ---------- D. NUL + advver in sibling worktree + git history ----------
res["NUL"] = {}
nul = os.path.join(REPO, "NUL")
res["NUL"]["exists_isfile"] = os.path.isfile(nul)
try:
    res["NUL"]["bytes"] = os.path.getsize(nul)
except OSError as ex:
    res["NUL"]["bytes"] = str(ex)
rc, so, _ = git("check-ignore", "-v", "--", "NUL")
res["NUL"]["ignored_by"] = so.strip()

rc, so, se = git("log", "--all", "--oneline", "-S", "_advver", "--", ".")
res["advver_in_history"] = lines(so)[:10]
res["advver_history_rc"] = rc
res["main_worktree_advver"] = []
if os.path.isdir(MAIN):
    for dp, dn, fn in os.walk(MAIN):
        if ".git" in dp or "node_modules" in dp:
            continue
        for f in fn + dn:
            if "advver" in f.lower():
                res["main_worktree_advver"].append(
                    os.path.relpath(os.path.join(dp, f), MAIN).replace("\\", "/")
                )
res["main_worktree_advver_n"] = len(res["main_worktree_advver"])
res["main_worktree_exists"] = os.path.isdir(MAIN)

# p2-wave probes control dirs (frozen)
p2 = REPO + "/command-center/p2-wave/probes"
res["p2wave_probe_dirs"] = sorted(os.listdir(p2)) if os.path.isdir(p2) else []

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("=== check-ignore ===")
for k, v in res["check_ignore"].items():
    print(f"  {k:45s} -> {v['rule']}")
print(
    "cc root probe scripts:",
    res["cc_root_probe_scripts_total"],
    "tracked",
    res["cc_root_probe_scripts_tracked_n"],
    "IGNORED",
    res["cc_root_probe_scripts_ignored_n"],
    f"({res['cc_root_probe_scripts_ignored_bytes']} B)",
)
print("=== ref KIND ===")
print(" CONTROL pos:", res["CONTROL_kind_positive"])
print(" CONTROL neg:", res["CONTROL_kind_negative"])
print(" exec:", res["n_exec"], " cite-only:", res["n_cite"], " zero:", res["n_zero"])
print(" zero-ref files:", res["untracked_zero_refs"])
print("=== dirs ===")
for k, v in res["dirs"].items():
    if v:
        print(
            f"  {k:38s} f={v['files']:6d} b={v['bytes']:11d} trk={v['tracked_files']:6d} unt={v['untracked_files']:4d}"
        )
print(
    "=== skills parity ===",
    json.dumps(
        {k: v for k, v in res["skills_parity"].items() if not isinstance(v, list)}
    ),
)
print("  only_in_skills:", res["skills_parity"]["only_in_skills"][:6])
print("  only_in_agents:", res["skills_parity"]["only_in_agents"][:6])
print("  parity tests:", res["parity_test_candidates"])
print("=== NUL ===", res["NUL"])
print(
    "=== advver history ===",
    res["advver_in_history"],
    "main worktree hits:",
    res["main_worktree_advver_n"],
    "main exists:",
    res["main_worktree_exists"],
)
print("=== p2-wave probe dirs ===", res["p2wave_probe_dirs"])
