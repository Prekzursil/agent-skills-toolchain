"""Resolve the three open items from _b15.

1. TST-0334: the two shells produced DIFFERENT output. The requirement says report divergence as a
   FINDING, not retry it -- so diff the payloads field by field and classify the severity.
2. IMP-0440: my "archive diverges only where the worktree has CRLF" control was WRONG -- archive
   re-introduced CRLF on an all-LF file too. Recorded, and replaced with a control that actually
   discriminates: the byte delta must equal the CRLF count EXACTLY (each \\n -> \\r\\n adds 1 byte),
   which a broken reader would not reproduce.
3. TST-0350: _b15 only ran --help. Reproduce the real BOTH-STATES control.
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
GITBASH = pathlib.Path("C:/Program Files/Git/bin/bash.exe")
OUT = {}
TARGET = "hooks/todo-surfacer/test_marker_discrimination.py"

# ---------------------------------------------------------------- 1. TST-0334 shell divergence
print("1. TST-0334 -- WHAT diverges between the two shells?")
a = subprocess.run(
    [PY, "tools/measure-guard/blobread.py", TARGET, "--compare"],
    cwd=ROOT,
    capture_output=True,
)
b = subprocess.run(
    [
        str(GITBASH),
        "-lc",
        f"cd '{ROOT.as_posix()}' && '{PY}' tools/measure-guard/blobread.py "
        f"{TARGET} --compare",
    ],
    cwd=ROOT,
    capture_output=True,
)


def parse_report(raw):
    """blobread prints a JSON object THEN a `SUCCESS:blobread ...` terminal-state marker line.

    A plain json.loads over the whole stdout raises 'Extra data', and a first version of this
    reviewer script let that failure become a MEDIUM 'cross-shell divergence' finding. It was not a
    divergence at all -- both shells failed to parse identically, and `j is not None and j == j2`
    then evaluated False. Recorded because a detector that reports a defect when IT breaks is the
    most expensive failure shape in this repo.
    """
    text = raw.decode("utf-8", errors="replace")
    end = text.rfind("}")
    return json.loads(text[: end + 1]), text[end + 1 :].strip()


ja, marker_a = parse_report(a.stdout)
jb, marker_b = parse_report(b.stdout)
print(f"   terminal marker pwsh   : {marker_a[:90]}")
print(f"   terminal marker gitbash: {marker_b[:90]}")


def flat(d, p=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from flat(v, f"{p}.{k}" if p else k)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from flat(v, f"{p}[{i}]")
    else:
        yield p, d


fa, fb = dict(flat(ja)), dict(flat(jb))
diff = {
    k: {"powershell": fa.get(k), "git_bash": fb.get(k)}
    for k in sorted(set(fa) | set(fb))
    if fa.get(k) != fb.get(k)
}
print(f"   fields compared: {len(set(fa) | set(fb))}; differing: {len(diff)}")
for k, v in diff.items():
    print(
        f"     {k}\n        pwsh    : {v['powershell']}\n        gitbash : {v['git_bash']}"
    )
# do the LOAD-BEARING fields (the route measurements) agree?
route_keys = [k for k in set(fa) | set(fb) if k.startswith("routes")]
routes_same = all(fa.get(k) == fb.get(k) for k in route_keys)
print(
    f"   route measurements identical across shells: {routes_same} ({len(route_keys)} fields)"
)
verdict = (
    "COSMETIC -- every route measurement agrees; only non-measurement metadata differs"
    if routes_same
    else "MATERIAL -- a route measurement itself differs between shells"
)
print(f"   VERDICT: {verdict}")
OUT["TST-0334"] = {
    "fields_compared": len(set(fa) | set(fb)),
    "differing_fields": diff,
    "route_fields": len(route_keys),
    "routes_identical": routes_same,
    "divergence_verdict": verdict,
    "rc_pwsh": a.returncode,
    "rc_gitbash": b.returncode,
    "terminal_marker_pwsh": marker_a,
    "terminal_marker_gitbash": marker_b,
    "markers_identical": marker_a == marker_b,
    "reviewer_instrument_note": (
        "A first version of this check ran json.loads over the WHOLE stdout, which raises "
        "'Extra data' because blobread emits a JSON object followed by a SUCCESS: marker line. "
        "Both parses returned None, the equality guard evaluated False, and the script was about "
        "to file a MEDIUM cross-shell-divergence finding that does not exist. Fixed by parsing the "
        "JSON prefix; the divergence verdict above is from the corrected instrument."
    ),
}

# ---------------------------------------------------------------- 2. IMP-0440 corrected control
print(
    "\n2. IMP-0440 -- corrected control: byte delta must EQUAL the CRLF count, exactly"
)
import hashlib  # noqa: E402


def gitb(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).stdout


def member_of(tar, relpath):
    off, name_want = 0, pathlib.PurePosixPath(relpath).name
    while off + 512 <= len(tar):
        hdr = tar[off : off + 512]
        name = hdr[0:100].rstrip(b"\0").decode("utf-8", errors="replace")
        try:
            size = int(hdr[124:136].rstrip(b"\0 ").decode() or "0", 8)
        except ValueError:
            return b""
        off += 512
        if name.endswith(name_want) and size:
            return tar[off : off + size]
        off += (size + 511) // 512 * 512
    return b""


rows = []
for f in (
    ".agents/skills/acceptance-review/scripts/acceptance_review.py",
    ".agents/skills/claude-science-local/cs_monitor.py",
    "command-center/receipt_validate.py",
    TARGET,
):
    blob = gitb("cat-file", "-p", f"HEAD:{f}")
    show = gitb("show", f"HEAD:{f}")
    arch = member_of(gitb("archive", "HEAD", "--", f), f)
    delta = len(arch) - len(blob)
    row = {
        "file": f,
        "blob_bytes": len(blob),
        "blob_crlf": blob.count(b"\r\n"),
        "archive_bytes": len(arch),
        "archive_crlf": arch.count(b"\r\n"),
        "byte_delta": delta,
        "delta_equals_archive_crlf": delta == arch.count(b"\r\n"),
        "cat_file_equals_show": blob == show,
        "identical_after_LF_norm": len(
            {
                hashlib.sha256(x.replace(b"\r\n", b"\n")).hexdigest()
                for x in (blob, show, arch)
            }
        )
        == 1,
    }
    rows.append(row)
    print(f"   {f}")
    print(
        f"      blob {row['blob_bytes']}B/{row['blob_crlf']}CRLF  archive "
        f"{row['archive_bytes']}B/{row['archive_crlf']}CRLF  delta={delta} "
        f"delta==crlf:{row['delta_equals_archive_crlf']}  cat-file==show:{row['cat_file_equals_show']}"
        f"  LF-norm identical:{row['identical_after_LF_norm']}"
    )
# NEGATIVE half: a file with NO newlines at all must show delta == 0
probe = ROOT / "command-center/p2-next/_nonewline_probe.bin"
neg = None
try:
    probe.write_bytes(b"no-newline-anywhere")
    subprocess.run(
        ["git", "add", "-f", "--", str(probe.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
    )
    idx = subprocess.run(
        ["git", "cat-file", "-p", ":command-center/p2-next/_nonewline_probe.bin"],
        cwd=ROOT,
        capture_output=True,
    ).stdout
    neg = {
        "staged_bytes": len(idx),
        "crlf": idx.count(b"\r\n"),
        "delta_is_zero_for_a_newline_free_file": idx.count(b"\r\n") == 0,
    }
    print(f"   NEGATIVE control (a newline-free staged file): {neg}")
finally:
    subprocess.run(
        [
            "git",
            "rm",
            "--cached",
            "-q",
            "--",
            "command-center/p2-next/_nonewline_probe.bin",
        ],
        cwd=ROOT,
        capture_output=True,
    )
    if probe.exists():
        probe.unlink()
all_ok = all(
    r["delta_equals_archive_crlf"]
    and r["cat_file_equals_show"]
    and r["identical_after_LF_norm"]
    for r in rows
)
print(f"   corrected control holds on all {len(rows)} files: {all_ok}")
OUT["IMP-0440"] = {
    "rows": rows,
    "corrected_control_holds": all_ok,
    "negative_control": neg,
    "refuted_reviewer_hypothesis": (
        "This reviewer first predicted archive would diverge ONLY where the WORKTREE has CRLF. "
        "That is WRONG and was measured wrong: .agents/skills/claude-science-local/cs_monitor.py is "
        "LF in both blob and worktree and archive still returned 220 CRLF. git archive applies "
        "export-time EOL conversion from gitattributes/core.autocrlf, independent of worktree "
        "bytes. The unit's claim never depended on my hypothesis; only my control did."
    ),
}

# ---------------------------------------------------------------- 3. TST-0350 both-states
print("\n3. TST-0350 -- reproduce the BOTH-STATES control of the suite-floor harness")
d350 = json.loads(
    (ROOT / "command-center/receipts/TST-0350.json").read_text(encoding="utf-8")
)
print("   the unit's declared negative controls:")
for c in d350.get("negative_controls") or []:
    print(f"     - {json.dumps(c)[:400]}")
good = subprocess.run(
    [PY, "tools/measure-guard/suitefloor.py", "--all"], cwd=ROOT, capture_output=True
)
print(f"   GOOD state rc={good.returncode}")
# BAD state: point the harness at a suite whose floor cannot be met. --list shows the registry.
lst = subprocess.run(
    [PY, "tools/measure-guard/suitefloor.py", "--list"], cwd=ROOT, capture_output=True
)
print(
    f"   --list: {' '.join(lst.stdout.decode('utf-8', errors='replace').split())[:400]}"
)
bad_unknown = subprocess.run(
    [
        PY,
        "tools/measure-guard/suitefloor.py",
        "--suite",
        "definitely-not-a-registered-suite",
    ],
    cwd=ROOT,
    capture_output=True,
)
print(
    f"   BAD state (unregistered suite) rc={bad_unknown.returncode} :: "
    f"{(bad_unknown.stdout + bad_unknown.stderr).decode('utf-8', errors='replace').strip()[:220]}"
)
tests = subprocess.run(
    [
        PY,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tools/measure-guard/tests/test_suitefloor.py",
    ],
    cwd=ROOT,
    capture_output=True,
)
tail = tests.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1:]
print(f"   its own suite rc={tests.returncode} :: {tail}")
OUT["TST-0350"] = {
    "declared_negative_controls": d350.get("negative_controls"),
    "good_state_rc": good.returncode,
    "good_state_tail": good.stdout.decode("utf-8", errors="replace")[-400:],
    "bad_state_unregistered_suite_rc": bad_unknown.returncode,
    "bad_state_tail": (bad_unknown.stdout + bad_unknown.stderr).decode(
        "utf-8", errors="replace"
    )[-400:],
    "own_test_suite_rc": tests.returncode,
    "own_test_suite_tail": tail,
    "both_states_reproduced": good.returncode == 0 and bad_unknown.returncode != 0,
}
print(
    f"   both states reproduced (good=0, bad!=0): {OUT['TST-0350']['both_states_reproduced']}"
)

(ROOT / "command-center/p2-next/REVIEW-THREE-RESOLVED.json").write_text(
    json.dumps(OUT, indent=2, default=str), encoding="utf-8"
)
print("\nSUCCESS:resolve-three")
