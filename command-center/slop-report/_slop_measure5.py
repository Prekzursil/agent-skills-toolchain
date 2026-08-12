"""SLOP measurement 5: bucket-(c) regenerability proof, dual-write checker intent,
codex-* wrapper skills, platform/~ path-bug dir, NUL structure, big ignored surfaces."""

import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure5.out.json"
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


_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = [p for p in lines(o) if "/slop-report/" not in p]
_, o, _ = git("ls-files")
tracked = set(lines(o))
_, o, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = set(lines(o))
ondisk = tracked | ignored | set(untracked)

# ---- 1. BUCKET (c) PROOF: does a producing script exist for each output? ----
outputs = [
    p
    for p in untracked
    if re.search(r"\.(out|err)\.(json|txt)$", p)
    or p.endswith("_out.json")
    or p.endswith("_out.err")
    or p.endswith(".err.txt")
]
regen = {}
for p in outputs:
    d = os.path.dirname(p)
    b = os.path.basename(p)
    stem = re.sub(r"\.(out|err)\.(json|txt)$", "", b)
    stem = re.sub(r"_(out|err)$", "", stem)
    stem = re.sub(r"\.(json|txt|err)$", "", stem)
    cands = [f"{d}/{stem}.py" if d else f"{stem}.py"]
    found = [c for c in cands if c in ondisk]
    regen[p] = {
        "producer_candidates": cands,
        "producer_present": found,
        "producer_tracked": [c for c in found if c in tracked],
        "producer_ignored": [c for c in found if c in ignored],
        "producer_untracked": [c for c in found if c in set(untracked)],
        "bytes": os.path.getsize(os.path.join(REPO, p)),
    }
res["outputs_n"] = len(outputs)
res["outputs"] = regen
res["outputs_with_producer"] = sorted(
    k for k, v in regen.items() if v["producer_present"]
)
res["outputs_without_producer"] = sorted(
    k for k, v in regen.items() if not v["producer_present"]
)
res["outputs_with_producer_n"] = len(res["outputs_with_producer"])
res["outputs_without_producer_n"] = len(res["outputs_without_producer"])
res["outputs_producer_not_in_git"] = sorted(
    k for k, v in regen.items() if v["producer_present"] and not v["producer_tracked"]
)
res["outputs_producer_not_in_git_n"] = len(res["outputs_producer_not_in_git"])

# ---- 2. dual-write checker intent ----
res["dualwrite"] = {}
for f in [
    "ci/check_skill_deploy_drift.py",
    "ci/tests/test_check_skill_dual_write.py",
    "tools/d001-dual-write/README.md",
]:
    fp = os.path.join(REPO, f)
    if os.path.exists(fp):
        with open(fp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            body = fh.read()
        res["dualwrite"][f] = {
            "bytes": len(body),
            "head": body.replace("\r\n", "\n").split("\n")[:34],
        }
    else:
        res["dualwrite"][f] = "ABSENT"

# ---- 3. codex-* wrapper skills present only in .agents/skills ----
only_agents = [
    "claim-verify-gate",
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
    "qdx-rush",
]
res["only_agents_skills"] = {}
for s in only_agents:
    d = os.path.join(REPO, ".agents/skills", s)
    sk = os.path.join(d, "SKILL.md")
    e = {"exists": os.path.isdir(d)}
    if os.path.isdir(d):
        n = b = 0
        for dp, dn, fn in os.walk(d):
            for f in fn:
                n += 1
                b += os.path.getsize(os.path.join(dp, f))
        e.update(files=n, bytes=b)
        e["tracked"] = f".agents/skills/{s}/SKILL.md" in tracked
        if os.path.exists(sk):
            with open(sk, "r", encoding="utf-8", errors="replace", newline="") as fh:
                head = fh.read(1400).replace("\r\n", "\n")
            e["desc"] = head[:520]
            e["tombstone_marker"] = bool(
                re.search(
                    r"tombstone|MOVED|redirect|superseded|RETIRED|deprecat", head, re.I
                )
            )
    res["only_agents_skills"][s] = e

only_skills = [
    "harness-module-authoring",
    "patent-fto-search",
    "social-corpus-extraction",
]
res["only_skills_skills"] = {}
for s in only_skills:
    d = os.path.join(REPO, "skills", s)
    e = {"exists": os.path.isdir(d)}
    if os.path.isdir(d):
        n = b = 0
        for dp, dn, fn in os.walk(d):
            for f in fn:
                n += 1
                b += os.path.getsize(os.path.join(dp, f))
        e.update(files=n, bytes=b, tracked=f"skills/{s}/SKILL.md" in tracked)
    res["only_skills_skills"][s] = e

# ---- 4. platform/~ path-bug directory ----
tilde = os.path.join(REPO, "platform", "~")
res["tilde_dir"] = {"exists": os.path.isdir(tilde)}
if os.path.isdir(tilde):
    fl = []
    for dp, dn, fn in os.walk(tilde):
        for f in fn:
            fp = os.path.join(dp, f)
            fl.append(
                (os.path.relpath(fp, REPO).replace("\\", "/"), os.path.getsize(fp))
            )
    res["tilde_dir"]["files"] = sorted(fl)
    res["tilde_dir"]["n"] = len(fl)
    res["tilde_dir"]["bytes"] = sum(s for _, s in fl)
    res["tilde_dir"]["tracked_any"] = [p for p, _ in fl if p in tracked]
    res["tilde_dir"]["ignored_any"] = [p for p, _ in fl if p in ignored]
    rc, so, _ = git("check-ignore", "-v", "--", "platform/~/.adv0041-amp")
    res["tilde_dir"]["check_ignore"] = so.strip() or "(NOT IGNORED)"
# who wrote it? search tracked corpus for adv0041-amp
rc, so, _ = git("grep", "-rl", "adv0041-amp", "--", ".")
res["tilde_dir_refs"] = lines(so)[:12]

# ---- 5. NUL structure (classify, never print content verbatim) ----
res["NUL_struct"] = {}
try:
    with open("\\\\?\\" + REPO.replace("/", "\\") + "\\NUL", "rb") as fh:
        raw = fh.read()
    txt = raw.decode("utf-8", "replace")
    res["NUL_struct"] = {
        "bytes": len(raw),
        "lines": txt.count("\n") + 1,
        "crlf": txt.count("\r\n"),
        "looks_like": ("json" if txt.lstrip()[:1] in "{[" else "text"),
        "first_line_shape": re.sub(
            r"[A-Za-z]", "a", re.sub(r"\d", "9", txt.split("\n")[0])
        )[:120],
        "has_secret_shape": bool(
            re.search(r"(sk-|hf_|ghp_|BEGIN [A-Z ]*PRIVATE KEY)", txt)
        ),
    }
except OSError as ex:
    res["NUL_struct"]["err"] = str(ex)


# ---- 6. big ignored surfaces: what KIND ----
def kindsum(prefix):
    ext = {}
    n = b = 0
    for p in ignored:
        if not p.startswith(prefix):
            continue
        n += 1
        e = os.path.splitext(p)[1].lower() or "(noext)"
        k = ext.setdefault(e, {"n": 0, "b": 0})
        k["n"] += 1
        try:
            s = os.path.getsize(os.path.join(REPO, p))
        except OSError:
            s = 0
        k["b"] += s
        b += s
    return {
        "files": n,
        "bytes": b,
        "top_ext": dict(sorted(ext.items(), key=lambda kv: -kv[1]["b"])[:6]),
    }


res["ignored_kind"] = {
    p: kindsum(p)
    for p in [
        "tools/mcp/",
        "platform/lib/",
        "tools/monitorcore/",
        "command-center/catalog-slices/",
        "agent-self/harness/",
        ".agents/skills/",
        "skills/",
    ]
}
# sample paths for the two biggest
res["tools_mcp_sample"] = sorted(p for p in ignored if p.startswith("tools/mcp/"))[:12]
res["platform_lib_sample"] = sorted(
    p for p in ignored if p.startswith("platform/lib/")
)[:12]

# ---- 7. _advver_M14 outside the repo ----
adv = "C:/Users/Prekzursil/source/_advver_M14"
res["advver_ext"] = {"exists": os.path.isdir(adv)}
if os.path.isdir(adv):
    res["advver_ext"]["entries"] = sorted(os.listdir(adv))[:10]
    tot = 0
    cnt = 0
    for sub in os.listdir(adv):
        sp = os.path.join(adv, sub)
        if not os.path.isdir(sp):
            continue
        n = b = 0
        for dp, dn, fn in os.walk(sp):
            if ".git" in dp.split(os.sep):
                continue
            for f in fn:
                n += 1
                try:
                    b += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        res["advver_ext"][sub] = {"files": n, "bytes": b}
        tot += b
        cnt += n
    res["advver_ext"]["total"] = {"files": cnt, "bytes": tot}

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("=== BUCKET C proof ===")
print(
    " untracked outputs:",
    res["outputs_n"],
    "with producer on disk:",
    res["outputs_with_producer_n"],
    "WITHOUT producer:",
    res["outputs_without_producer_n"],
    "producer-present-but-not-in-git:",
    res["outputs_producer_not_in_git_n"],
)
print(" no-producer:", res["outputs_without_producer"])
print("=== dual-write ===")
for k, v in res["dualwrite"].items():
    if v == "ABSENT":
        print(" ", k, "ABSENT")
    else:
        print(" ", k, v["bytes"], "B")
        for ln in v["head"][:24]:
            print("     |", ln)
print("=== only-in-.agents skills ===")
for k, v in res["only_agents_skills"].items():
    print(
        f"  {k:22s} {v}"
        if not v.get("desc")
        else f"  {k:22s} files={v['files']} bytes={v['bytes']} tracked={v['tracked']} tomb={v['tombstone_marker']}"
    )
print("=== only-in-skills/ ===", res["only_skills_skills"])
print("=== platform/~ ===", {k: v for k, v in res["tilde_dir"].items() if k != "files"})
print("   refs:", res["tilde_dir_refs"])
print("=== NUL struct ===", res["NUL_struct"])
print("=== ignored kind ===")
for k, v in res["ignored_kind"].items():
    print(
        f"  {k:32s} {v['files']:6d} f {v['bytes']:11d} B  {list(v['top_ext'].items())[:3]}"
    )
print("  tools/mcp sample:", res["tools_mcp_sample"][:6])
print("  platform/lib sample:", res["platform_lib_sample"][:6])
print("=== _advver_M14 external ===", res["advver_ext"])
