"""GROUNDING R2: turn the name-collision groups into a CONTENT-backed duplicate list.

The name-set detector in _g2_classify.py cannot distinguish two hypotheses:
  H1 the dirs are true duplicates (same names AND same bytes)
  H2 the dirs are parallel STRUCTURE (same names, different bytes) -- e.g. rules/cpp vs rules/java
A PASS looks identical under both, so the name-set signal alone is not a control.
This probe adds the discriminator: per-file sha256 over LF-normalised bytes.

Read-only.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
).stdout.strip()


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def sha_lf(path: str) -> str | None:
    """Hash LF-normalised bytes: a CRLF/LF difference is not a content difference."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()[:16]


out = {
    "repo": REPO,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "head": git("rev-parse", "HEAD").strip(),
    "method": "sha256-16 over LF-normalised bytes; identical_frac = identical files / shared names",
}

tracked = set(git("ls-files").splitlines())
untracked = {
    p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p
}
allfiles = sorted(tracked | untracked)

children: dict[str, set[str]] = defaultdict(set)
for p in allfiles:
    children[os.path.dirname(p)].add(os.path.basename(p))

groups: dict[tuple, list[str]] = defaultdict(list)
for d, names in children.items():
    if len(names) >= 3:
        groups[tuple(sorted(names))].append(d)


def sanctioned_pair(a: str, b: str) -> bool:
    def n(d: str) -> str:
        for pre in (".agents/skills/", "skills/"):
            if d.startswith(pre):
                return "SK/" + d[len(pre) :]
        return d

    return n(a) == n(b)


# ---- DETECTOR CONTROL (both states), on a known pair from the sanctioned dual-write.
ctrl: dict = {}
probe_a = ".agents/skills/code-security/rules"
probe_b = "skills/code-security/rules"
if os.path.isdir(os.path.join(REPO, probe_a)) and os.path.isdir(
    os.path.join(REPO, probe_b)
):
    names = sorted(children[probe_a] & children[probe_b])
    same = sum(
        1
        for n_ in names
        if sha_lf(os.path.join(REPO, probe_a, n_))
        == sha_lf(os.path.join(REPO, probe_b, n_))
    )
    ctrl["known_dual_write_pair"] = [probe_a, probe_b]
    ctrl["known_dual_write_identical"] = f"{same}/{len(names)}"
    ctrl["hasher_positive"] = same > 0
# negative control: the hasher must NOT report two genuinely different files as equal
h1 = sha_lf(os.path.join(REPO, "README.md"))
h2 = sha_lf(os.path.join(REPO, "AGENTS.md"))
ctrl["hasher_negative_readme_vs_agents_differ"] = bool(h1 and h2 and h1 != h2)
# stability: re-hash the same file twice
ctrl["hasher_stable"] = sha_lf(os.path.join(REPO, "README.md")) == h1
ctrl["hasher_distinguishes"] = (
    bool(ctrl.get("hasher_positive"))
    and ctrl["hasher_negative_readme_vs_agents_differ"]
)
out["controls"] = ctrl

results = []
for key, dirs in groups.items():
    if len(dirs) < 2:
        continue
    for a, b in itertools.combinations(sorted(dirs), 2):
        names = sorted(set(key))
        ident = 0
        differ = 0
        missing = 0
        diff_names = []
        for n_ in names:
            ha = sha_lf(os.path.join(REPO, a.replace("/", os.sep), n_))
            hb = sha_lf(os.path.join(REPO, b.replace("/", os.sep), n_))
            if ha is None or hb is None:
                missing += 1
            elif ha == hb:
                ident += 1
            else:
                differ += 1
                diff_names.append(n_)
        total = ident + differ
        if total == 0:
            continue
        results.append(
            {
                "a": a,
                "b": b,
                "shared_names": len(names),
                "identical": ident,
                "differing": differ,
                "missing": missing,
                "identical_frac": round(ident / total, 3),
                "sanctioned_dual_write": sanctioned_pair(a, b),
                "differing_sample": diff_names[:4],
                "a_tracked": sum(1 for n_ in names if f"{a}/{n_}" in tracked),
                "b_tracked": sum(1 for n_ in names if f"{b}/{n_}" in tracked),
            }
        )

results.sort(key=lambda r: (-r["identical"], -r["identical_frac"]))
out["pairs_examined"] = len(results)

TRUE_DUP = [
    r for r in results if r["identical_frac"] >= 0.8 and not r["sanctioned_dual_write"]
]
STRUCT_ONLY = [r for r in results if r["identical_frac"] < 0.2]
out["true_duplicate_unsanctioned_n"] = len(TRUE_DUP)
out["true_duplicate_unsanctioned"] = TRUE_DUP[:40]
out["name_collision_only_n"] = len(STRUCT_ONLY)
out["name_collision_only_sample"] = [
    {"a": r["a"], "b": r["b"], "identical_frac": r["identical_frac"]}
    for r in STRUCT_ONLY[:10]
]
out["sanctioned_pairs_n"] = sum(1 for r in results if r["sanctioned_dual_write"])
sanc = [r for r in results if r["sanctioned_dual_write"]]
out["sanctioned_pairs_identical_frac_mean"] = (
    round(sum(r["identical_frac"] for r in sanc) / len(sanc), 3) if sanc else None
)
out["sanctioned_pairs_with_drift"] = [
    {
        "a": r["a"],
        "b": r["b"],
        "identical_frac": r["identical_frac"],
        "differing": r["differing"],
    }
    for r in sanc
    if r["identical_frac"] < 1.0
][:20]

json.dump(out, sys.stdout, indent=1)
