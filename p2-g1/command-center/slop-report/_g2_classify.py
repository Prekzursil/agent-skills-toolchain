"""GROUNDING R2: classify the UNMEASURED untracked surface (platform/, docs/) into buckets,
and detect UNsanctioned parallel directories mechanically.

Read-only. Imports the SHIPPED resolver from check_published_commands.py rather than writing a
second implementation (a second copy measures my copy of the rule, not the rule).

Corpus = `git grep --cached` = the INDEX, i.e. what a clone sees. Declared, not assumed.
Every detector carries a both-states control.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_published_commands as CPC  # noqa: E402

REPO = CPC.repo_root()


def git(*args, check=True):
    r = subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and r.returncode not in (0, 1):
        raise SystemExit(f"FAILED:g2 git {args} rc={r.returncode}: {r.stderr[:300]}")
    return r.stdout


def git_grep_patterns(patterns: list[str], fixed: bool = True) -> list[str]:
    """One process. Patterns via -f file, so the Windows 32k arg cap cannot bite."""
    if not patterns:
        return []
    fd, pf = tempfile.mkstemp(suffix=".pat", text=True)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(patterns) + "\n")
    try:
        args = ["grep", "-n", "-I", "--cached"]
        if fixed:
            args.append("-F")
        else:
            args.append("-E")
        args += ["-f", pf]
        return git(*args).splitlines()
    finally:
        os.unlink(pf)


out = {
    "repo": REPO,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "head": git("rev-parse", "HEAD").strip(),
    "shipped_resolver_imported_from": CPC.__file__,
    "corpus_scope": "git grep --cached (the index = what a clone sees)",
}

tracked = set(git("ls-files").splitlines())
untracked = [
    p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p
]

TARGET_PREFIXES = ("platform/", "docs/")
targets = [p for p in untracked if p.startswith(TARGET_PREFIXES)]
out["target_scope"] = list(TARGET_PREFIXES)
out["target_untracked_n"] = len(targets)

# ---------------------------------------------------------------- published-command citations
# The FIELD that is a dependency (INTEGRATE-R1 s2.1), not any mention of a name.
pub_lines = git_grep_patterns([r"python3?(\.exe)?[ \t]"], fixed=False)
pub_cite: dict[str, list[str]] = defaultdict(list)
pub_unresolved_all: list[dict] = []
for ln in pub_lines:
    parts = ln.split(":", 2)
    if len(parts) < 3:
        continue
    citer, lineno, text = parts[0], parts[1], parts[2]
    for m in CPC.CMD.finditer(text):
        target = m.group(1)
        ok, _ = CPC.resolve(target, citer, tracked)
        if ok:
            continue
        cands = {
            CPC.norm(target),
            CPC.norm(os.path.dirname(citer).replace(os.sep, "/") + "/" + target),
        }
        pub_unresolved_all.append(
            {"citer": citer, "line": int(lineno), "target": target}
        )
        for c in cands:
            pub_cite[c].append(citer)

out["published_command_lines_scanned"] = len(pub_lines)
out["published_commands_unresolved_repo_wide_n"] = len(pub_unresolved_all)

# ---------------------------------------------------------------- basename mentions (weak signal)
basenames = sorted({os.path.basename(p) for p in targets})
sentinel_absent = f"_zz_{uuid.uuid4().hex}.py"
mention_lines = git_grep_patterns(
    basenames + [sentinel_absent, "check_published_commands.py"]
)
mention: dict[str, list[str]] = defaultdict(list)
ctrl_pos_hits = 0
ctrl_neg_hits = 0
bn_set = set(basenames)
for ln in mention_lines:
    parts = ln.split(":", 2)
    if len(parts) < 3:
        continue
    citer, _lineno, text = parts
    if sentinel_absent in text:
        ctrl_neg_hits += 1
    if "check_published_commands.py" in text:
        ctrl_pos_hits += 1
    for bn in bn_set:
        if bn in text:
            mention[bn].append(citer)

ctrl = {
    "mention_positive_control_file": "check_published_commands.py",
    "mention_positive_control_hits": ctrl_pos_hits,
    "mention_negative_control_name": sentinel_absent,
    "mention_negative_control_hits": ctrl_neg_hits,
    "mention_detector_distinguishes": ctrl_pos_hits > 0 and ctrl_neg_hits == 0,
}
ok_ctrl, _ = CPC.resolve(
    "command-center/slop-report/check_published_commands.py", "docs/x.md", tracked
)
bad_ctrl, _ = CPC.resolve(f"command-center/{sentinel_absent}", "docs/x.md", tracked)
ctrl["resolve_positive_control"] = ok_ctrl
ctrl["resolve_negative_control"] = bad_ctrl
ctrl["resolve_detector_distinguishes"] = bool(ok_ctrl) and not bad_ctrl
out["controls"] = ctrl


# ---------------------------------------------------------------- producer pairing (bucket c)
def producer_of(path: str) -> str | None:
    d, b = os.path.split(path)
    for suf in (
        ".out.json",
        ".err.txt",
        ".out.txt",
        ".out.err",
        ".err",
        ".log",
        ".out",
    ):
        if b.endswith(suf):
            return f"{d}/{b[: -len(suf)]}.py"
    return None


# ---------------------------------------------------------------- classify
buckets: dict[str, list[str]] = {
    "b_cited_published_command": [],
    "b_mentioned_only": [],
    "c_reproducible_tracked_producer": [],
    "d_candidate_zero_reference": [],
}
detail = []
now = time.time()
for p in sorted(targets):
    bn = os.path.basename(p)
    fp = os.path.join(REPO, p.replace("/", os.sep))
    try:
        age_min = round((now - os.path.getmtime(fp)) / 60.0, 1)
        size = os.path.getsize(fp)
    except OSError:
        age_min, size = None, None
    prod = producer_of(p)
    prod_tracked = bool(prod and prod in tracked)
    prod_ondisk = bool(
        prod and os.path.exists(os.path.join(REPO, prod.replace("/", os.sep)))
    )
    pubs = sorted(set(pub_cite.get(p, [])))
    ments = sorted(set(mention.get(bn, [])))
    if pubs:
        bucket = "b_cited_published_command"
    elif prod_tracked:
        bucket = "c_reproducible_tracked_producer"
    elif ments:
        bucket = "b_mentioned_only"
    else:
        bucket = "d_candidate_zero_reference"
    buckets[bucket].append(p)
    detail.append(
        {
            "path": p,
            "bucket": bucket,
            "bytes": size,
            "age_min": age_min,
            "published_command_citers": pubs,
            "mention_citers_n": len(ments),
            "mention_citers": ments[:6],
            "producer": prod,
            "producer_tracked": prod_tracked,
            "producer_ondisk": prod_ondisk,
        }
    )

out["buckets_n"] = {k: len(v) for k, v in buckets.items()}
out["buckets"] = buckets
out["detail"] = detail
out["bucket_b_bytes"] = sum(
    d["bytes"] or 0 for d in detail if d["bucket"].startswith("b_")
)
out["bucket_d_bytes"] = sum(
    d["bytes"] or 0 for d in detail if d["bucket"].startswith("d_")
)

# ---------------------------------------------------------------- parallel-directory detection
allfiles = sorted(tracked | set(untracked))
children: dict[str, set[str]] = defaultdict(set)
for p in allfiles:
    children[os.path.dirname(p)].add(os.path.basename(p))

groups: dict[tuple, list[str]] = defaultdict(list)
for d, names in children.items():
    if len(names) >= 3:
        groups[tuple(sorted(names))].append(d)

dupe_groups = []
for key, dirs in groups.items():
    if len(dirs) >= 2:
        dupe_groups.append(
            {"n_files": len(key), "dirs": sorted(dirs), "sample": list(key)[:5]}
        )
dupe_groups.sort(key=lambda g: -g["n_files"])


def sanctioned(dirs: list[str]) -> bool:
    """skills/ <-> .agents/skills/ is a documented dual-write (ci/check_skill_dual_write.py)."""
    norm = set()
    for d in dirs:
        if d.startswith(".agents/skills/"):
            norm.add("SK/" + d[len(".agents/skills/") :])
        elif d.startswith("skills/"):
            norm.add("SK/" + d[len("skills/") :])
        else:
            norm.add(d)
    return len(norm) == 1


out["parallel_dir_groups_total"] = len(dupe_groups)
unsanctioned = [g for g in dupe_groups if not sanctioned(g["dirs"])]
out["parallel_dir_groups_unsanctioned_n"] = len(unsanctioned)
out["parallel_dir_groups_unsanctioned"] = unsanctioned[:40]
sanctioned_groups = [g for g in dupe_groups if sanctioned(g["dirs"])]
out["controls_parallel"] = {
    "sanctioned_groups_found": len(sanctioned_groups),
    "detector_sees_known_dual_write": len(sanctioned_groups) > 0,
    "sanctioned_sample": sanctioned_groups[0]["dirs"] if sanctioned_groups else None,
}

json.dump(out, sys.stdout, indent=1)
