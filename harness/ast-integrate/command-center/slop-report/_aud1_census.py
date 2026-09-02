"""AUDIT probe 1: independently re-derive the 123 / 0->45 / 78 split and the citation detector.

Independent of the builder: I re-scan the disk and re-run the citation search myself,
with my own control (a known-referenced file must fire, a nonexistent name must not).
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CC = REPO / "command-center"


def git(*args):
    r = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


out = {}

# --- 1. on-disk root probe scripts (direct children of command-center/, _*.py) ---
on_disk = sorted(p.name for p in CC.glob("_*.py") if p.is_file())
out["on_disk_count"] = len(on_disk)
out["on_disk_bytes"] = sum((CC / n).stat().st_size for n in on_disk)

# --- 2. tracked ones, via git ls-files (mechanically different from a glob) ---
rc, so, _ = git("ls-files", "command-center/")
tracked_all = [line for line in so.splitlines() if line.strip()]
pat = re.compile(r"^command-center/_[A-Za-z0-9_]+\.py$")
tracked_probes = sorted(Path(line).name for line in tracked_all if pat.match(line))
out["tracked_probe_count"] = len(tracked_probes)
out["tracked_probe_bytes"] = sum(
    (CC / n).stat().st_size for n in tracked_probes if (CC / n).exists()
)
out["untracked_probe_count"] = len([n for n in on_disk if n not in set(tracked_probes)])

# --- 3. check-ignore: which are still ignored, and by which rule ---
untracked_probes = [n for n in on_disk if n not in set(tracked_probes)]
ign_tracked_still = []
ign_untracked = []
rule_samples = {}
for n in on_disk:
    rc, so, _ = git("check-ignore", "-v", f"command-center/{n}")
    ignored = rc == 0 and so.strip() != ""
    if n in set(tracked_probes):
        if ignored:
            ign_tracked_still.append(n)
    else:
        if ignored:
            ign_untracked.append(n)
            if len(rule_samples) < 2:
                rule_samples[n] = so.strip()
        else:
            rule_samples.setdefault("UNIGNORED_" + n, "(no ignore rule)")
out["cited_tracked_still_ignored_want_0"] = len(ign_tracked_still)
out["untracked_still_ignored"] = len(ign_untracked)
out["untracked_total"] = len(untracked_probes)
out["check_ignore_samples"] = rule_samples

# --- 4. citation detector, re-implemented + controlled ---
# Search all TRACKED text under command-center/ for each probe basename.
text_exts = {".md", ".json", ".txt", ".yml", ".yaml", ".py"}
corpus = []
for rel in tracked_all:
    p = REPO / rel
    if p.suffix.lower() in text_exts and p.exists():
        try:
            corpus.append((rel, p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
out["corpus_files"] = len(corpus)


def citers(name, exclude_self=True):
    hits = []
    for rel, body in corpus:
        if exclude_self and Path(rel).name == name:
            continue
        # skip the lane's own report + its producers, so a citation must be
        # INDEPENDENT of the slop lane itself
        if name in body:
            hits.append(rel)
    return hits


def citers_outside_sloplane(name):
    return [r for r in citers(name) if not r.startswith("command-center/slop-report/")]


cited, uncited = [], []
for n in on_disk:
    if citers_outside_sloplane(n):
        cited.append(n)
    else:
        uncited.append(n)
out["cited_count"] = len(cited)
out["cited_bytes"] = sum((CC / n).stat().st_size for n in cited)
out["uncited_count"] = len(uncited)

# CONTROL: known-referenced file must fire, nonexistent name must not.
ctrl_pos_name = "_gen_schema_substrate.py"
ctrl_pos = citers(ctrl_pos_name, exclude_self=True)
ctrl_neg = citers("_zzz_definitely_not_a_real_probe_name_9182.py")
out["control"] = {
    "positive_target": ctrl_pos_name,
    "positive_hits": len(ctrl_pos),
    "positive_expected_citer_present": any(
        "test_schema_resolver" in h for h in ctrl_pos
    ),
    "negative_hits": len(ctrl_neg),
    "states_distinguishable": len(ctrl_pos) > 0 and len(ctrl_neg) == 0,
}

# --- 5. is every one of the 45 tracked ones actually cited? ---
tracked_set = set(tracked_probes)
cited_set = set(cited)
out["tracked_but_uncited"] = sorted(tracked_set - cited_set)
out["cited_but_untracked"] = sorted(cited_set - tracked_set)

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
