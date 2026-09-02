"""SLOP measurement 2: ruff status of untracked py, reference detector WITH CONTROL,
tracked-vs-ignored split of command-center scratch, harvest/ + _advver_M14 + frozen dirs."""

import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure2.out.json"
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
_, o, _ = git("ls-files", "--others", "--exclude-standard")
untracked = lines(o)
_, o, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = set(lines(o))

# ---------- A. ruff on untracked .py ----------
upy = [p for p in untracked if p.endswith(".py")]
res["untracked_py_count"] = len(upy)


def ruff(args, files):
    if not files:
        return 0, "", ""
    r = subprocess.run(
        ["uvx", "ruff@0.15.17"] + args + files,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


rc, so, se = ruff(["format", "--check"], upy)
fmt_fail = [
    ln.split("Would reformat: ", 1)[1].strip()
    for ln in lines(so)
    if ln.startswith("Would reformat:")
]
res["ruff_format_rc"] = rc
res["ruff_format_would_reformat_count"] = len(fmt_fail)
res["ruff_format_would_reformat"] = sorted(fmt_fail)
res["ruff_format_tail"] = lines(so)[-2:] + lines(se)[-2:]

rc, so, se = ruff(["check", "--output-format", "concise"], upy)
lint_hits = [ln for ln in lines(so) if re.match(r"^[^\s].*:\d+:\d+: ", ln)]
lint_files = sorted({ln.split(":")[0] for ln in lint_hits})
res["ruff_check_rc"] = rc
res["ruff_check_violation_count"] = len(lint_hits)
res["ruff_check_failing_files_count"] = len(lint_files)
res["ruff_check_failing_files"] = lint_files
res["ruff_check_tail"] = lines(so)[-3:] + lines(se)[-2:]

# CONTROL (both-states): ruff must FIRE on a deliberately-broken file and stay
# silent on a known-clean tracked file.
ctrl_dir = REPO + "/command-center/slop-report"
broken = ctrl_dir + "/_ctrl_broken.py"
clean = ctrl_dir + "/_ctrl_clean.py"
with open(broken, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("import os,sys\nx  =   1\ndef  f( a ):\n  return a\n")
with open(clean, "w", encoding="utf-8", newline="\n") as fh:
    fh.write('"""Clean."""\n\n\ndef f(a):\n    """Doc."""\n    return a\n')
rc_b, so_b, _ = ruff(["format", "--check"], [broken])
rc_c, so_c, _ = ruff(["format", "--check"], [clean])
rc_bl, so_bl, _ = ruff(["check", "--output-format", "concise"], [broken])
rc_cl, so_cl, _ = ruff(["check", "--output-format", "concise"], [clean])
res["CONTROL_ruff"] = {
    "format_broken_rc": rc_b,
    "format_broken_fires": rc_b != 0,
    "format_clean_rc": rc_c,
    "format_clean_silent": rc_c == 0,
    "lint_broken_rc": rc_bl,
    "lint_broken_fires": rc_bl != 0,
    "lint_clean_rc": rc_cl,
    "lint_clean_silent": rc_cl == 0,
    "lint_broken_out": lines(so_bl)[:4],
}
os.remove(broken)
os.remove(clean)

# ---------- B. command-center scratch: tracked vs ignored ----------
cc_root_files = [
    f
    for f in os.listdir(REPO + "/command-center")
    if os.path.isfile(os.path.join(REPO, "command-center", f))
]
scratch = [f for f in cc_root_files if f.startswith("_")]
res["cc_root_underscore_total"] = len(scratch)
res["cc_root_underscore_tracked"] = sorted(
    f for f in scratch if "command-center/" + f in tracked
)
res["cc_root_underscore_ignored"] = sorted(
    f for f in scratch if "command-center/" + f in ignored
)
res["cc_root_underscore_untracked_unignored"] = sorted(
    f for f in scratch if "command-center/" + f in set(untracked)
)
res["cc_root_underscore_tracked_n"] = len(res["cc_root_underscore_tracked"])
res["cc_root_underscore_ignored_n"] = len(res["cc_root_underscore_ignored"])

# ---------- C. reference detector, WITH CONTROL ----------
# Search only TRACKED text files for a basename mention.
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
    ".cfg",
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
res["reference_corpus_files"] = len(corpus)


def refs(basename, exclude_self=True):
    hits = []
    for p, body in corpus:
        if exclude_self and p.endswith("/" + basename):
            continue
        if basename in body:
            hits.append(p)
    return hits


# CONTROL positive: a file the ground truth says IS referenced by a tracked test.
ctrl_pos = "_gen_schema_substrate.py"
ctrl_pos_hits = refs(ctrl_pos)
# CONTROL negative: a basename that cannot exist anywhere.
ctrl_neg = "_zzz_no_such_file_qx7.py"
ctrl_neg_hits = refs(ctrl_neg)
res["CONTROL_refdetector"] = {
    "positive_basename": ctrl_pos,
    "positive_hits": len(ctrl_pos_hits),
    "positive_fires": len(ctrl_pos_hits) > 0,
    "positive_sample": ctrl_pos_hits[:4],
    "negative_basename": ctrl_neg,
    "negative_hits": len(ctrl_neg_hits),
    "negative_silent": len(ctrl_neg_hits) == 0,
}

ref_map = {}
for p in untracked:
    b = os.path.basename(p)
    if b.startswith("_ctrl_") or b.startswith("_slop_"):
        continue
    h = refs(b)
    ref_map[p] = h
res["untracked_referenced"] = {k: v for k, v in ref_map.items() if v}
res["untracked_unreferenced"] = sorted(k for k, v in ref_map.items() if not v)
res["untracked_referenced_n"] = len(res["untracked_referenced"])
res["untracked_unreferenced_n"] = len(res["untracked_unreferenced"])

# ---------- D. _advver_M14 ----------
adv = []
for dp, dn, fn in os.walk(REPO):
    if ".git" in dp or "node_modules" in dp:
        continue
    for f in fn + dn:
        if "advver" in f.lower() or "_M14" in f:
            adv.append(os.path.relpath(os.path.join(dp, f), REPO).replace("\\", "/"))
res["advver_M14_paths"] = sorted(set(adv))[:60]
res["advver_M14_count"] = len(set(adv))
res["advver_mentions_in_tracked"] = [p for p, b in corpus if "_advver" in b][:10]

# ---------- E. harvest/ ----------
h = REPO + "/command-center/harvest"
res["harvest"] = {}
if os.path.isdir(h):
    for f in sorted(os.listdir(h)):
        rel = "command-center/harvest/" + f
        res["harvest"][f] = {
            "bytes": os.path.getsize(os.path.join(h, f)),
            "tracked": rel in tracked,
            "ignored": rel in ignored,
            "referenced_by": refs(f)[:6],
        }

# ---------- F. frozen evidence dirs: untouched proof ----------
frozen = ["command-center/casualty/probes"]
p2 = REPO + "/command-center/p2-wave/probes"
if os.path.isdir(p2):
    for d in sorted(os.listdir(p2)):
        c = f"command-center/p2-wave/probes/{d}/control"
        if os.path.isdir(os.path.join(REPO, c)):
            frozen.append(c)
res["frozen_dirs"] = {}
for fd in frozen:
    _, so, _ = git("status", "--porcelain", "--", fd)
    n = 0
    for dp, dn, fn in os.walk(os.path.join(REPO, fd)):
        n += len(fn)
    res["frozen_dirs"][fd] = {"files": n, "git_status_lines": lines(so)}

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)

print("=== RUFF on", res["untracked_py_count"], "untracked .py ===")
print(
    "format would-reformat:",
    res["ruff_format_would_reformat_count"],
    "rc",
    res["ruff_format_rc"],
)
print(
    "lint violations:",
    res["ruff_check_violation_count"],
    "across",
    res["ruff_check_failing_files_count"],
    "files, rc",
    res["ruff_check_rc"],
)
print("CONTROL ruff:", json.dumps(res["CONTROL_ruff"], indent=1)[:600])
print("=== cc root underscore scratch ===")
print(
    " total",
    res["cc_root_underscore_total"],
    "tracked",
    res["cc_root_underscore_tracked_n"],
    "ignored",
    res["cc_root_underscore_ignored_n"],
    "untracked-unignored",
    len(res["cc_root_underscore_untracked_unignored"]),
)
print("=== reference detector ===")
print("CONTROL:", json.dumps(res["CONTROL_refdetector"], indent=1))
print(
    "referenced:",
    res["untracked_referenced_n"],
    "unreferenced:",
    res["untracked_unreferenced_n"],
)
print("=== advver/M14 ===", res["advver_M14_count"], res["advver_M14_paths"][:10])
print("=== harvest ===")
for k, v in res["harvest"].items():
    print(
        f"  {k:45s} {v['bytes']:9d} B tracked={v['tracked']} ignored={v['ignored']} refs={len(v['referenced_by'])}"
    )
print("=== frozen ===")
for k, v in res["frozen_dirs"].items():
    print(f"  {k:55s} files={v['files']:4d} dirty={len(v['git_status_lines'])}")
