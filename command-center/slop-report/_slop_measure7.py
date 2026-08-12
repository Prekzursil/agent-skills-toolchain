"""SLOP measurement 7: prior-art gate contents, root strays, clean ruff attribution."""

import hashlib
import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure7.out.json"
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


def read(p):
    fp = os.path.join(REPO, p)
    if not os.path.exists(fp):
        return None
    with open(fp, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


_, o, _ = git("ls-files")
tracked = set(lines(o))

# ---- 1. prior-art gate: no-runtime-junk.yml ----
y = read(".github/workflows/no-runtime-junk.yml")
res["no_runtime_junk_yml"] = y.split("\n") if y else "ABSENT"
res["no_runtime_junk_bytes"] = len(y) if y else 0

# ---- 2. prior art: P13 orphan plan ----
op = read("command-center/P13-ORPHAN-PLAN.json")
res["p13_orphan_plan"] = json.loads(op) if op else "ABSENT"
ops = read("command-center/p13_orphan_plan.py")
res["p13_orphan_plan_py_head"] = ops.split("\n")[:26] if ops else "ABSENT"


# ---- 3. root strays: duplicates of a skill-owned file? ----
def sha(p):
    fp = os.path.join(REPO, p)
    if not os.path.exists(fp):
        return None
    with open(fp, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:20]


def shalf(p):
    fp = os.path.join(REPO, p)
    if not os.path.exists(fp):
        return None
    with open(fp, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:20]


trio = [
    "clean_markdown.py",
    "skills/consensus-tooluniverse-research/scripts/clean_markdown.py",
    ".agents/skills/consensus-tooluniverse-research/scripts/clean_markdown.py",
]
res["clean_markdown"] = {
    p: {
        "sha": sha(p),
        "sha_lf": shalf(p),
        "tracked": p in tracked,
        "bytes": os.path.getsize(os.path.join(REPO, p))
        if os.path.exists(os.path.join(REPO, p))
        else None,
    }
    for p in trio
}
# does anything reference the ROOT copy specifically?
rc, so, _ = git("grep", "-rn", "clean_markdown", "--", ".")
res["clean_markdown_refs"] = lines(so)[:20]

# root-level file census
rootfiles = [f for f in os.listdir(REPO) if os.path.isfile(os.path.join(REPO, f))]
res["root_files"] = {}
for f in sorted(rootfiles):
    try:
        sz = os.path.getsize(os.path.join(REPO, f))
    except OSError:
        sz = -1
    rc, so, _ = git("log", "-1", "--format=%h %ad %s", "--date=short", "--", f)
    res["root_files"][f] = {
        "bytes": sz,
        "tracked": f in tracked,
        "last_commit": (lines(so)[:1] or ["(never committed)"])[0][:90],
    }

# ---- 4. clean ruff attribution (exclude slop-report) ----
_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = [p for p in lines(o) if "/slop-report/" not in p]
upy = [p for p in untracked if p.endswith(".py")]
res["untracked_py_excl_mine"] = len(upy)
r = subprocess.run(
    ["uvx", "ruff@0.15.17", "format", "--check"] + upy,
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
fmt = sorted(
    ln.split("Would reformat: ", 1)[1].strip()
    for ln in lines(r.stdout)
    if ln.startswith("Would reformat:")
)
res["ruff_fmt_fail"] = fmt
res["ruff_fmt_fail_n"] = len(fmt)
r = subprocess.run(
    ["uvx", "ruff@0.15.17", "check", "--output-format", "concise"] + upy,
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
viol = [ln for ln in lines(r.stdout) if re.match(r"^[^\s].*:\d+:\d+: ", ln)]
res["ruff_lint_violations"] = viol
res["ruff_lint_files"] = sorted({v.split(":")[0] for v in viol})
res["ruff_lint_n"] = len(viol)

# would committing them turn CI red? what does quality.yml lint?
q = read(".github/workflows/quality.yml")
if q:
    res["quality_ruff_steps"] = [
        ln.strip() for ln in q.split("\n") if "ruff" in ln.lower()
    ][:14]
    res["quality_step_count"] = q.count("- name:")

# ---- 5. adversarial ADV-0041 mention of platform/~ ----
a = read("command-center/adversarial/ADV-0041-path-and-identity-disclosure.json")
if a:
    idx = a.find("adv0041-amp")
    res["adv0041_excerpt"] = a[max(0, idx - 700) : idx + 500]

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("=== no-runtime-junk.yml (", res["no_runtime_junk_bytes"], "B ) ===")
for ln in (res["no_runtime_junk_yml"] or [])[:60]:
    print("  ", ln)
print("=== P13 orphan plan ===")
print(json.dumps(res["p13_orphan_plan"], indent=1)[:1400])
print("=== clean_markdown ===")
for k, v in res["clean_markdown"].items():
    print(f"  {k:62s} {v}")
print("  refs:", res["clean_markdown_refs"][:10])
print("=== root files ===")
for k, v in res["root_files"].items():
    print(f"  {k:34s} {v['bytes']:9d} trk={str(v['tracked']):5s} {v['last_commit']}")
print("=== ruff (excl. slop-report) on", res["untracked_py_excl_mine"], "files ===")
print("  format-fail:", res["ruff_fmt_fail_n"], res["ruff_fmt_fail"][:20])
print("  lint:", res["ruff_lint_n"], "in", res["ruff_lint_files"])
for v in res["ruff_lint_violations"][:12]:
    print("    ", v)
print("=== quality.yml ruff steps ===", res.get("quality_ruff_steps"))
print("  quality step count:", res.get("quality_step_count"))
print("=== ADV-0041 excerpt ===")
print(res.get("adv0041_excerpt", "")[:1100])
