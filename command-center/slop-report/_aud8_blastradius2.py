"""AUDIT probe 8: settle the 144-file blast radius, after probe 7 failed its own control.

Probe 7 used `--extend-exclude` on the CLI and the widened run considered MORE files
(2432 > 2258) -- impossible for an added exclusion, so the CLI flag REPLACES the ruff.toml
`extend-exclude` list instead of adding to it. Self-contradicting output = detector failure,
not a finding. Probe 7's "0 files leave the gate" is therefore discarded, not reported.

This does it the only way that cannot lie: inside an ISOLATED clone (no sibling can see the
edit), mutate ruff.toml itself exactly as the owner would, and diff `ruff check --show-files`.

Controls:
  K1 the UNMODIFIED clone reading must equal the unmodified worktree-tracked reading (2135)
     -- proves the clone measures the same gate
  K2 widened set must be a STRICT SUBSET of narrow (an exclusion can only remove)
  K3 every removed path must be a command-center file whose basename starts with '_'
  K4 the removed set must contain all 14 currently-red files (that is the point of the fix)
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = "C:/Users/Prekzursil/source/ast-integrate"
RUFF = ["uvx", "ruff@0.15.17"]
out = {"controls": {}}


def run(args, cwd, timeout=1800):
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr


tmp = Path(tempfile.mkdtemp(prefix="aud8_"))
clone = tmp / "repo"
rc, _, se = run(
    [
        "git",
        "clone",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
        "--no-hardlinks",
        REPO,
        str(clone),
    ],
    str(tmp),
)
out["clone_rc"] = rc
run(["git", "checkout", "--force", "ebe02d62"], str(clone))
rc, so, _ = run(["git", "ls-files"], str(clone))
tracked = set(so.splitlines())


def show_files():
    rc, so, se = run([*RUFF, "check", "--show-files", "--no-cache", "."], str(clone))
    files = set()
    for ln in so.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        p = Path(ln)
        try:
            files.add(str(p.relative_to(clone)).replace("\\", "/"))
        except ValueError:
            files.add(ln.replace("\\", "/"))
    return rc, files


rt = clone / "ruff.toml"
orig = rt.read_bytes()

rc_n, narrow = show_files()
narrow_t = narrow & tracked

txt = orig.decode("utf-8")
widened = txt.replace('"command-center/_*.py",', '"command-center/**/_*.py",')
out["substitution_applied"] = widened != txt
rt.write_bytes(widened.encode("utf-8"))
rc_w, wide = show_files()
wide_t = wide & tracked
rt.write_bytes(orig)

removed = sorted(narrow_t - wide_t)
added = sorted(wide_t - narrow_t)
out["tracked_files_in_gate"] = {"narrow": len(narrow_t), "widened": len(wide_t)}
out["ANSWER_tracked_files_leaving_the_gate"] = len(removed)
out["builder_told_owner"] = 144
out["builder_number_correct"] = len(removed) == 144

by_dir = {}
for r_ in removed:
    d = str(Path(r_).parent).replace("\\", "/")
    by_dir[d] = by_dir.get(d, 0) + 1
out["removed_by_dir"] = dict(sorted(by_dir.items(), key=lambda kv: -kv[1]))

red = [
    f"command-center/grounding/_s2_{n}.py"
    for n in [
        "appendonly_and_negcase",
        "apply_negcase",
        "budget_refit",
        "bytestable",
        "render_probe",
        "restore_negcase",
        "vault_gap",
        "wa_union",
    ]
] + [
    f"command-center/ssot/{n}.py"
    for n in [
        "_grounding_content",
        "_grounding_direction",
        "_grounding_stranded",
        "_grounding_stranded2",
        "_grounding_verify",
        "_secret_preflight",
    ]
]
out["controls"]["K1_clone_matches_worktree_reading"] = {
    "clone": len(narrow_t),
    "worktree_probe7": 2135,
    "pass": len(narrow_t) == 2135,
}
out["controls"]["K2_strict_subset"] = {
    "n_added_by_widening": len(added),
    "pass": len(added) == 0 and len(removed) > 0,
}
out["controls"]["K3_removed_shape"] = {
    "n_violating": len(
        [
            r_
            for r_ in removed
            if not (r_.startswith("command-center/") and Path(r_).name.startswith("_"))
        ]
    ),
    "pass": all(
        r_.startswith("command-center/") and Path(r_).name.startswith("_")
        for r_ in removed
    ),
}
out["controls"]["K4_covers_the_14_red"] = {
    "uncovered": sorted(set(red) - set(removed)),
    "pass": sorted(set(red) - set(removed)) == [],
}
out["controls"]["all_pass"] = all(
    v["pass"] for v in out["controls"].values() if isinstance(v, dict)
)
out["E402_file_still_in_gate_after_widening"] = (
    "command-center/ssot/verify_refs.py" in wide_t
)

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
shutil.rmtree(tmp, ignore_errors=True)
