"""AUDIT probe 7: the EXACT number of tracked files the widened exclusion removes from the gate.

My probe 6 used a hand-rolled "already excluded by another entry" heuristic and got 188 against
the builder's 144. A heuristic is not evidence for an owner-facing number, so this asks ruff
itself: `ruff check --show-files` prints exactly the file set ruff would check, honoring every
exclusion. Run it twice -- once as the repo is, once with the widened pattern added via
--extend-exclude (NO edit to the shared ruff.toml, which a sibling lane may be reading) -- and
intersect both sets with `git ls-files` so untracked scratch cannot inflate either side.

Control: the widened run's file set must be a strict SUBSET of the narrow run's, and the removed
set must contain ONLY paths whose basename starts with '_' under command-center/. If either fails,
the measurement is measuring the wrong thing.
"""

import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
RUFF = ["uvx", "ruff@0.15.17"]
out = {}


def show_files(extra_exclude=None):
    args = [*RUFF, "check", "--show-files", "--no-cache"]
    if extra_exclude:
        args += ["--extend-exclude", extra_exclude]
    args += ["."]
    r = subprocess.run(
        args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    files = set()
    for ln in r.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        p = Path(ln)
        try:
            files.add(str(p.relative_to(REPO)).replace("\\", "/"))
        except ValueError:
            files.add(ln.replace("\\", "/"))
    return r.returncode, files


rc, so, _ = (
    subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ),
    None,
    None,
)
tracked = set(rc.stdout.splitlines())

rc_n, narrow = show_files(None)
rc_w, wide = show_files("command-center/**/_*.py")
out["ruff_rc"] = {"narrow": rc_n, "widened": rc_w}
out["all_files_considered"] = {"narrow": len(narrow), "widened": len(wide)}

narrow_t = narrow & tracked
wide_t = wide & tracked
removed = sorted(narrow_t - wide_t)
out["tracked_files_in_gate"] = {"narrow": len(narrow_t), "widened": len(wide_t)}
out["ANSWER_tracked_files_leaving_the_gate"] = len(removed)
out["builder_told_owner"] = 144
out["builder_number_correct"] = len(removed) == 144

by_dir = {}
for r_ in removed:
    d = str(Path(r_).parent).replace("\\", "/")
    by_dir[d] = by_dir.get(d, 0) + 1
out["removed_by_dir"] = dict(sorted(by_dir.items(), key=lambda kv: -kv[1]))

# ---- controls ----
out["controls"] = {
    "widened_is_strict_subset": wide_t < narrow_t,
    "all_removed_are_underscore_under_command_center": all(
        r_.startswith("command-center/") and Path(r_).name.startswith("_")
        for r_ in removed
    ),
    "nothing_added_by_widening": len(wide_t - narrow_t) == 0,
    "detector_nonempty": len(narrow_t) > 100,
}
out["controls"]["pass"] = all(out["controls"].values())

# the 8 + 6 currently-red files: are they all inside the removed set?
red = [
    "command-center/grounding/_s2_appendonly_and_negcase.py",
    "command-center/grounding/_s2_apply_negcase.py",
    "command-center/grounding/_s2_budget_refit.py",
    "command-center/grounding/_s2_bytestable.py",
    "command-center/grounding/_s2_render_probe.py",
    "command-center/grounding/_s2_restore_negcase.py",
    "command-center/grounding/_s2_vault_gap.py",
    "command-center/grounding/_s2_wa_union.py",
    "command-center/ssot/_grounding_content.py",
    "command-center/ssot/_grounding_direction.py",
    "command-center/ssot/_grounding_stranded.py",
    "command-center/ssot/_grounding_stranded2.py",
    "command-center/ssot/_grounding_verify.py",
    "command-center/ssot/_secret_preflight.py",
]
out["all_14_red_files_covered_by_widening"] = sorted(set(red) - set(removed)) == []
out["E402_file_covered_by_widening"] = "command-center/ssot/verify_refs.py" in set(
    removed
)

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
