"""AUDIT probe 6: attribute the lint error, measure the true blast radius, check residuals 3+4.

Every number the builder handed the OWNER as a decision input is re-measured here, because a
wrong blast-radius number is what makes an owner pick the wrong fix.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
out = {}


def git(*a, cwd=REPO):
    r = subprocess.run(
        ["git", "-C", str(cwd), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


# ---- 1. attribute the E402 file ----
target = "command-center/ssot/verify_refs.py"
rc, so, _ = git("log", "--format=%h %s", "--diff-filter=A", "--", target)
lines = [x for x in so.splitlines() if x.strip()]
out["E402_file"] = target
out["E402_added_by"] = lines[-1] if lines else "?"
out["E402_matches_widened_glob"] = bool(
    re.match(r"^command-center/(.*/)?_[^/]*\.py$", target)
)

# ---- 2. blast radius of the widened exclusion, measured two ways ----
rc, so, _ = git("ls-files", "command-center/")
cc = [x for x in so.splitlines() if x.strip()]
py = [x for x in cc if x.endswith(".py")]
underscore_any_depth = [x for x in py if Path(x).name.startswith("_")]
root_only = [x for x in py if re.match(r"^command-center/_[^/]+\.py$", x)]
# which of them are ALREADY excluded by the pre-existing ruff.toml entries?
ruff_toml = (REPO / "ruff.toml").read_text(encoding="utf-8", errors="replace")
existing = re.findall(r'^\s*"([^"]+)",', ruff_toml, re.M)
out["ruff_extend_exclude_entries"] = existing


def already_excluded(rel):
    for pat in existing:
        if pat == "command-center/_*.py":
            continue  # the entry the lane added; we are measuring the INCREMENT over it
        base = pat.rstrip("/*").rstrip("/")
        if rel.startswith(base.replace("**/", "")) or rel.startswith(base):
            return True
    return False


newly_leaving = [
    x
    for x in underscore_any_depth
    if not already_excluded(x) and x not in set(root_only)
]
out["blast_radius"] = {
    "tracked_py_under_command_center": len(py),
    "basename_starts_underscore_any_depth": len(underscore_any_depth),
    "root_only_already_excluded_by_lane": len(root_only),
    "INCREMENT_that_would_newly_leave_the_gate": len(newly_leaving),
    "builder_told_owner": 144,
}
out["blast_radius_top_dirs"] = {}
for x in newly_leaving:
    d = str(Path(x).parent)
    out["blast_radius_top_dirs"][d] = out["blast_radius_top_dirs"].get(d, 0) + 1

# ---- 3. residual 3: does `git clean -Xdf` still destroy the 78 uncited probes? DRY RUN ONLY ----
rc, so, _ = git("clean", "-Xdn")  # -n = dry run, NEVER without -n
victims = [
    x[len("Would remove ") :].strip()
    for x in so.splitlines()
    if x.startswith("Would remove ")
]
root_probe_victims = [
    v for v in victims if re.match(r"^command-center/_[^/]+\.py$", v.replace("\\", "/"))
]
out["residual3_git_clean_Xdn"] = {
    "dry_run_only": True,
    "total_would_remove": len(victims),
    "root_probe_scripts_would_remove": len(root_probe_victims),
    "builder_claimed": 78,
    "matches": len(root_probe_victims) == 78,
}

# ---- 4. residual 4: empty directories, and the platform/~ path-bug tree ----
empty = []
for d in REPO.rglob("*"):
    try:
        if not d.is_dir():
            continue
        s = str(d).replace("\\", "/")
        if "/.git/" in s or s.endswith("/.git"):
            continue
        if not any(d.iterdir()):
            empty.append(str(d.relative_to(REPO)).replace("\\", "/"))
    except OSError:
        pass
out["residual4_empty_dirs"] = {
    "count": len(empty),
    "builder_claimed": 13,
    "dirs": sorted(empty),
    "platform_tilde_exists": (REPO / "platform" / "~").exists(),
}

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
