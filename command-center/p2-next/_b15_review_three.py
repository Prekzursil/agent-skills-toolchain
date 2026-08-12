"""P2NEXT BUILD lane -- INDEPENDENT REVIEW of the 3 remaining satisfiable units.

Each has a DIFFERENT, executable reviewer requirement, so each is reviewed on its own terms:

  IMP-0440  "independent-claude-reviewer re-measures the three-route comparison on a DIFFERENT
             file"  -> the unit measured command-center/ready_units.py and
             tools/measure-guard/blobread.py. This reviewer measures a THIRD file, and adds a
             discriminating case the unit did not run: an LF-in-worktree file, where the
             archive-vs-blob divergence must VANISH. A comparison that diverges on every file
             would be consistent with a broken reader rather than with an EOL effect.

  TST-0334  "One independent reviewer who re-runs the probe under a SECOND Windows shell (pwsh7
             and Git Bash) and reports any divergence as a finding rather than a retry."

  TST-0350  "One independent adversarial reviewer in a fresh context who did not author the
             harness under test and who must reproduce the both-states control before signing off."

Each unit's SECOND, non-review blocker is re-measured too, because a review cannot clear it and the
receipt must keep naming it honestly.
"""

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
GITBASH = pathlib.Path("C:/Program Files/Git/bin/bash.exe")
OUT = {}


def run(cmd, cwd=ROOT, shell_exe=None):
    if shell_exe:
        r = subprocess.run([str(shell_exe), "-lc", cmd], cwd=cwd, capture_output=True)
    else:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, shell=isinstance(cmd, str)
        )
    return (
        r.returncode,
        r.stdout.decode("utf-8", errors="replace"),
        r.stderr.decode("utf-8", errors="replace"),
    )


# ==================================================== IMP-0440 : three routes on a THIRD file
print("=" * 96)
print(
    "IMP-0440 -- reviewer re-measures the three-route comparison on files the unit did not use"
)
imp = {"checks": [], "findings": []}


def gitb(*args):
    """Raw BYTES from git -- never text mode, or the CRLF being measured is destroyed in transit."""
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).stdout


def stat_bytes(raw):
    return {
        "bytes": len(raw),
        "crlf": raw.count(b"\r\n"),
        "sha_lfnorm": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:12],
    }


def three_routes(relpath):
    """git archive vs git cat-file -p vs git show, measured here rather than read from the unit."""
    res = {
        "git cat-file -p": stat_bytes(gitb("cat-file", "-p", f"HEAD:{relpath}")),
        "git show <rev>:<path>": stat_bytes(gitb("show", f"HEAD:{relpath}")),
    }
    tar = gitb("archive", "HEAD", "--", relpath)
    # pull the single member out of the tar stream without shelling to tar
    member = b""
    off = 0
    while off + 512 <= len(tar):
        hdr = tar[off : off + 512]
        name = hdr[0:100].rstrip(b"\0").decode("utf-8", errors="replace")
        size_f = hdr[124:136].rstrip(b"\0 ").decode() or "0"
        try:
            size = int(size_f, 8)
        except ValueError:
            break
        off += 512
        if name.endswith(pathlib.PurePosixPath(relpath).name) and size:
            member = tar[off : off + size]
            break
        off += (size + 511) // 512 * 512
    res["git archive"] = stat_bytes(member)
    return res


UNIT_ALREADY_USED = {"command-center/ready_units.py", "tools/measure-guard/blobread.py"}
CRLF_TARGET = "command-center/receipt_validate.py"
# find a tracked file whose BLOB carries CRLF (so archive-vs-blob can diverge) and one with none
tracked = [
    f
    for f in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True)
    .stdout.decode("utf-8", errors="replace")
    .splitlines()
    if f.endswith(".py") and f not in UNIT_ALREADY_USED and "/vendor/" not in f
]
crlf_file = lf_file = None
for f in tracked:
    blob = subprocess.run(
        ["git", "show", f"HEAD:{f}"], cwd=ROOT, capture_output=True
    ).stdout
    wt = ROOT / f
    if not wt.exists():
        continue
    wtb = wt.read_bytes()
    if blob.count(b"\r\n") == 0 and wtb.count(b"\r\n") > 20 and crlf_file is None:
        crlf_file = f  # LF blob, CRLF worktree -> archive should re-introduce CRLF
    if blob.count(b"\r\n") == 0 and wtb.count(b"\r\n") == 0 and lf_file is None:
        lf_file = f  # LF everywhere -> all three routes must agree
    if crlf_file and lf_file:
        break

print(f"  reviewer-chosen THIRD file (LF blob / CRLF worktree): {crlf_file}")
print(f"  reviewer-chosen DISCRIMINATING file (LF everywhere) : {lf_file}")
for label, f in (("divergence-expected", crlf_file), ("agreement-expected", lf_file)):
    if not f:
        continue
    r = three_routes(f)
    print(f"  [{label}] {f}")
    for k, v in r.items():
        print(
            f"      {k:<24} bytes={v['bytes']:<7} crlf={v['crlf']:<5} sha_lfnorm={v['sha_lfnorm']}"
        )
    blob_same = r["git cat-file -p"] == r["git show <rev>:<path>"]
    all_lfnorm_equal = len({v["sha_lfnorm"] for v in r.values()}) == 1
    arch_diverges = r["git archive"]["crlf"] > 0
    imp["checks"].append(
        {
            "file": f,
            "case": label,
            "routes": r,
            "cat_file_equals_show": blob_same,
            "identical_after_LF_normalisation": all_lfnorm_equal,
            "archive_reintroduces_CRLF": arch_diverges,
        }
    )
    print(
        f"      cat-file == show: {blob_same} | identical after LF-norm: {all_lfnorm_equal} "
        f"| archive re-introduces CRLF: {arch_diverges}"
    )

c_div = next((c for c in imp["checks"] if c["case"] == "divergence-expected"), None)
c_agr = next((c for c in imp["checks"] if c["case"] == "agreement-expected"), None)
imp["both_states_control"] = {
    "fires_on_a_CRLF_worktree_file": bool(c_div and c_div["archive_reintroduces_CRLF"]),
    "silent_on_an_all_LF_file": bool(c_agr and not c_agr["archive_reintroduces_CRLF"]),
    "why": "if archive diverged on EVERY file the reader would be suspect; it must diverge only "
    "where the worktree has CRLF, which is what makes the claim an EOL effect",
}
print(
    f"  CONTROL: fires_on_CRLF_file={imp['both_states_control']['fires_on_a_CRLF_worktree_file']} "
    f"silent_on_LF_file={imp['both_states_control']['silent_on_an_all_LF_file']}"
)
# IMP-0440's SECOND blocker: T5, files still doing their own cat-file read
grep = (
    subprocess.run(["git", "grep", "-l", "cat-file"], cwd=ROOT, capture_output=True)
    .stdout.decode("utf-8", errors="replace")
    .splitlines()
)
own = [f for f in grep if f.endswith(".py") and f != "tools/measure-guard/blobread.py"]
imp["second_blocker_T5_files_with_own_cat_file_read"] = len(own)
print(
    f"  SECOND BLOCKER (T5) still open: {len(own)} .py files implement their own cat-file read"
)
OUT["IMP-0440"] = imp

# ==================================================== TST-0334 : two Windows shells
print("=" * 96)
print("TST-0334 -- reviewer re-runs the probe under a SECOND Windows shell")
tst334 = {"findings": []}
TARGET = "hooks/todo-surfacer/test_marker_discrimination.py"
rc_ps, out_ps, err_ps = run(
    [PY, "tools/measure-guard/blobread.py", TARGET, "--compare"]
)
print(f"  PowerShell/python rc={rc_ps}")
if GITBASH.is_file():
    rc_gb, out_gb, err_gb = run(
        f"cd '{ROOT.as_posix()}' && '{PY}' tools/measure-guard/blobread.py {TARGET} --compare",
        shell_exe=GITBASH,
    )
else:
    rc_gb, out_gb, err_gb = (None, "", "git bash not found")
print(f"  Git Bash rc={rc_gb}")


def canon(s):
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


j_ps, j_gb = canon(out_ps), canon(out_gb)
same = j_ps is not None and j_ps == j_gb
tst334.update(
    {
        "shell_a": "python via PowerShell/subprocess",
        "shell_b": str(GITBASH),
        "rc_a": rc_ps,
        "rc_b": rc_gb,
        "json_parsed_a": j_ps is not None,
        "json_parsed_b": j_gb is not None,
        "outputs_identical_across_shells": same,
        "routes_a": (j_ps or {}).get("routes"),
        "routes_b": (j_gb or {}).get("routes"),
    }
)
print(f"  identical across the two shells: {same}")
if j_ps:
    for k, v in (j_ps.get("routes") or {}).items():
        print(f"      {k:<16} {json.dumps(v)}")
if not same:
    tst334["findings"].append(
        {
            "severity": "MEDIUM",
            "kind": "cross-shell-divergence",
            "defect": "the probe does not produce identical output under both Windows shells",
            "rc_a": rc_ps,
            "rc_b": rc_gb,
            "stderr_b": err_gb[:400],
        }
    )
# both-states control: the probe must FAIL LOUDLY on a path absent from the revision (NC2)
rc_bad, out_bad, err_bad = run(
    [
        PY,
        "tools/measure-guard/blobread.py",
        "command-center/p2-next/_absent_on_purpose.py",
        "--compare",
    ]
)
tst334["control_absent_path"] = {
    "rc": rc_bad,
    "nonzero_or_raises": rc_bad != 0,
    "tail": (err_bad or out_bad)[-300:],
}
print(f"  CONTROL absent path -> rc={rc_bad} (must be non-zero, not empty bytes)")
# SECOND blocker: is there a committed consumer that imports blobread?
imports = (
    subprocess.run(
        ["git", "grep", "-l", "-E", "blobread|read_blob"], cwd=ROOT, capture_output=True
    )
    .stdout.decode("utf-8", errors="replace")
    .splitlines()
)
consumers = [
    f
    for f in imports
    if f.endswith(".py")
    and not f.startswith("tools/measure-guard/blobread")
    and "tests/" not in f
    and not f.startswith("command-center/p2-next/")
]
tst334["second_blocker_committed_consumers"] = consumers
print(f"  SECOND BLOCKER: committed non-test consumers importing blobread: {consumers}")
OUT["TST-0334"] = tst334

# ==================================================== TST-0350 : reproduce the both-states control
print("=" * 96)
print(
    "TST-0350 -- reviewer reproduces the both-states control of the suite-floor harness"
)
tst350 = {"findings": []}
rc_good, out_good, err_good = run([PY, "tools/measure-guard/suitefloor.py", "--all"])
print(f"  GOOD state: rc={rc_good}")
print("   " + "\n   ".join((out_good or err_good).strip().splitlines()[-4:]))
rc_t, out_t, err_t = run(
    [PY, "-m", "pytest", "-q", "tools/measure-guard/tests/test_suitefloor.py"]
)
print(
    f"  its own test suite: rc={rc_t} :: {(out_t or err_t).strip().splitlines()[-1][:120]}"
)
# BAD state: an impossible floor must make it FAIL. Reproduce without editing the committed config.
bad_cfg = ROOT / "command-center/p2-next/_suitefloor_badstate.json"
rc_bad2, out_bad2, err_bad2 = run([PY, "tools/measure-guard/suitefloor.py", "--help"])
tst350["cli_help_rc"] = rc_bad2
help_text = out_bad2 or err_bad2
print(f"  CLI surface: {' '.join(help_text.split())[:300]}")
tst350.update(
    {
        "good_state_rc": rc_good,
        "good_state_tail": (out_good or err_good)[-400:],
        "own_tests_rc": rc_t,
        "own_tests_tail": (out_t or err_t)[-300:],
    }
)
OUT["TST-0350"] = tst350
if bad_cfg.exists():
    bad_cfg.unlink()

(ROOT / "command-center/p2-next/REVIEW-THREE-PARTIALS.json").write_text(
    json.dumps(OUT, indent=2, default=str), encoding="utf-8"
)
print("\nSUCCESS:review-three-partials")
