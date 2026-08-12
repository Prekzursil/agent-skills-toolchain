r"""ROUND-2 both-states controls for every defect the adversarial audit CONFIRMED.

A fix is not a fix until the probe that certifies it has been shown to FIRE against the
known-BROKEN state. For each defect this script:
  1. materialises the PRE-FIX code from the git blob at HEAD (`git show HEAD:<path>` -- the
     stored blob, LF, which is what CI checks out; `git archive` would hand back CRLF here),
  2. exercises it and asserts the defect IS present,
  3. exercises the FIXED working-tree code and asserts the defect is GONE,
  4. asserts the fixed tool still does its job (a tightened matcher that is merely inert is
     the failure mode a naive tightening hides).

Terminal state per AGENTS.md 4:  SUCCESS:r2-defect-controls  /  FAILED:r2-defect-controls <n>
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
CAS = ROOT / "command-center" / "casualty"
RESULTS: list[dict] = []

# The broken state must stay reachable AFTER round 2 is committed, so the baseline is PINNED to
# the last round-1 lane commit rather than to HEAD. Pinning to HEAD would have made every
# control silently compare the fixed code against itself the moment I committed -- a probe that
# passes because it stopped measuring. Each control still asserts the defect REPRODUCES at this
# baseline, so a wrong pin fails loudly instead of passing vacuously.
BASELINE = "4afce4e1"


def sh(args, cwd=ROOT, text=True):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=text)


def blob_at_head(rel: str) -> str:
    """PRE-FIX source, read from the stored blob at the pinned round-1 baseline.

    `git show <rev>:<path>` is the correct recipe here: it returns the stored blob (LF), which is
    what CI checks out. `git archive` would apply export-time EOL conversion and hand back CRLF
    on Windows -- verified in this repo's own windows-shell rule.
    """
    r = subprocess.run(["git", "show", f"{BASELINE}:{rel}"], cwd=str(ROOT),
                       capture_output=True, text=True)
    assert r.returncode == 0, f"git show failed for {rel}@{BASELINE}: {r.stderr[:300]}"
    return r.stdout


def record(did: str, name: str, broken_ok: bool, fixed_ok: bool, still_works: bool | None,
           detail: str) -> None:
    ok = broken_ok and fixed_ok and (still_works is not False)
    RESULTS.append({"defect": did, "control": name, "fires_in_broken_state": broken_ok,
                    "silent_in_fixed_state": fixed_ok, "fixed_tool_still_works": still_works,
                    "PASS": ok, "detail": detail})
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {did} {name}")
    print(f"       broken-state fires={broken_ok}  fixed-state clean={fixed_ok}  "
          f"still-works={still_works}")
    for line in detail.splitlines():
        print(f"       {line}")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- D1
def control_d1(script_rel: str, out_name: str, did: str, extra_inputs: list[str]) -> None:
    """A superseded GENERATOR silently overwrites the file that records why it is superseded."""
    canonical = CAS / out_name
    before = sha(canonical) if canonical.is_file() else None
    banner_before = "_DO_NOT_CITE" in canonical.read_text(encoding="utf-8") if canonical.is_file() else False

    tmp = Path(tempfile.mkdtemp(prefix="r2_d1_"))
    try:
        out = tmp / "out"
        out.mkdir()
        for name in extra_inputs:
            shutil.copy2(CAS / name, out / name)
        # Plant a banner-stamped target so an overwrite is visible as data loss.
        (out / out_name).write_text(
            json.dumps({"_DO_NOT_CITE": "banner planted by the round-2 control",
                        "rows": [], "tally": {}}, indent=1), encoding="utf-8")

        src = blob_at_head(script_rel)
        old_line = 'OUT = REPO / "command-center" / "casualty"'
        assert old_line in src, "OUT constant not found in the pre-fix blob"
        patched = src.replace(old_line, f'OUT = Path(r"{out}")')
        p = tmp / Path(script_rel).name
        p.write_text(patched, encoding="utf-8", newline="\n")

        r = sh([sys.executable, str(p)])
        planted_survived = "_DO_NOT_CITE" in (out / out_name).read_text(encoding="utf-8")
        broken_fires = (r.returncode == 0) and not planted_survived
        broken_detail = (f"PRE-FIX {script_rel} rc={r.returncode}; planted _DO_NOT_CITE banner "
                         f"survived={planted_survived} -> the generator ERASED it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    r2 = sh([sys.executable, str(CAS / Path(script_rel).name)])
    after = sha(canonical) if canonical.is_file() else None
    fixed_ok = (r2.returncode == 2 and "SUPERSEDED" in r2.stdout and before == after)

    # still-works: the guarded escape hatch must still be able to run into an explicit dir
    tmp2 = Path(tempfile.mkdtemp(prefix="r2_d1_ok_"))
    try:
        for name in extra_inputs:
            shutil.copy2(CAS / name, tmp2 / name)
        r3 = sh([sys.executable, str(CAS / Path(script_rel).name),
                 "--i-know-this-is-superseded", "--out", str(tmp2)])
        still = (tmp2 / out_name).is_file() and r3.returncode == 0
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    record(did, f"{Path(script_rel).name} cannot silently overwrite {out_name}",
           broken_fires, fixed_ok, still,
           broken_detail + "\n"
           + f"POST-FIX rc={r2.returncode} marker={'SUPERSEDED' in r2.stdout} "
             f"canonical sha unchanged={before == after} (banner present before={banner_before})\n"
           + f"escape hatch --i-know-this-is-superseded --out DIR still produces {out_name}: {still}")


# --------------------------------------------------------------------------- D2
def control_d2() -> None:
    rel = "command-center/casualty/verify_elided_digest.py"
    tmp = Path(tempfile.mkdtemp(prefix="r2_d2_"))
    try:
        p = tmp / "prefix_verify.py"
        p.write_text(blob_at_head(rel), encoding="utf-8", newline="\n")
        r = sh([sys.executable, str(p)])                    # NO ARGUMENTS
        broken = (r.returncode == 0 and r.stdout.strip() == "")
        bdet = (f"PRE-FIX no-arg run: rc={r.returncode} stdout={r.stdout.strip()!r} "
                f"-> a zero-input run is indistinguishable from two passing verifications")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    r2 = sh([sys.executable, str(CAS / "verify_elided_digest.py")])
    fixed = (r2.returncode != 0 and "FAILED:elided-digest no inputs" in r2.stdout)

    receipts = [str(CAS / "ADV-0021-install-path-stride-threat-model.json"),
                str(CAS / "ADV-0022-declared-permission-escape.json")]
    r3 = sh([sys.executable, str(CAS / "verify_elided_digest.py"), *receipts])
    still = (r3.returncode == 0 and r3.stdout.count("MATCH=True") >= 4)

    record("D2", "verify_elided_digest fails CLOSED on empty input", broken, fixed, still,
           bdet + f"\nPOST-FIX no-arg run: rc={r2.returncode} marker="
                  f"{'FAILED:elided-digest no inputs' in r2.stdout}\n"
                  f"POST-FIX with 2 real receipts: rc={r3.returncode} MATCH=True count="
                  f"{r3.stdout.count('MATCH=True')} (not inert)")


# --------------------------------------------------------------------------- D3 + D5
def control_d3_d5() -> None:
    lv = str(CAS / "liveness_v2.py")
    prefix_src = blob_at_head("command-center/casualty/liveness_v2.py")
    # BROKEN state is structural and is asserted on the pre-fix SOURCE plus its behaviour:
    #   (a) the default run never calls selftest(), and
    #   (b) main() carried a second copy of the gate logic that selftest() never touched.
    tmp = Path(tempfile.mkdtemp(prefix="r2_d3_"))
    broken_default_had_no_control = False
    try:
        p = tmp / "prefix_liveness.py"
        p.write_text(prefix_src, encoding="utf-8", newline="\n")
        r = sh([sys.executable, str(p)])
        broken_default_had_no_control = ("BOTH-STATES CONTROL" not in r.stdout
                                         and "verdict tally" in r.stdout)
        bdet = (f"PRE-FIX default run: control printed={'BOTH-STATES CONTROL' in r.stdout} "
                f"tally printed={'verdict tally' in r.stdout} -> a citable tally with no control")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # DETECTOR NOTE (round 2): the first version of this line counted the literal
    # `verdict = "MID-FLIGHT"` and scored pre-fix=1 / post-fix=0, i.e. it reported the defect
    # as ABSENT before the fix and the fix as having DELETED the logic. It was counting a
    # syntax form -- evaluate() writes the same decision as a ternary -- not the decision.
    # Counting the AND-gate expression itself is form-independent: pre=2, post=1.
    GATE_EXPR = "g1 and g2 and g3"
    dup = prefix_src.count(GATE_EXPR)
    bdet += (f"\nPRE-FIX evaluation sites of the AND-gate expression {GATE_EXPR!r}: {dup} "
             f"(selftest exercised evaluate(); the tally came from main()'s own copy)")

    r2 = sh([sys.executable, lv])
    fixed = ("BOTH-STATES CONTROL" in r2.stdout
             and r2.stdout.index("BOTH-STATES CONTROL") < r2.stdout.index("verdict tally")
             and r2.returncode == 0)
    r3 = sh([sys.executable, lv, "--selftest-mutate", "drop-g3"])
    mutation_blocks = (r3.returncode != 0 and "verdict tally" not in r3.stdout
                       and "FAILED:liveness-v2-selftest" in r3.stdout)
    now_dup = (CAS / "liveness_v2.py").read_text(encoding="utf-8").count(GATE_EXPR)

    record("D3+D5", "liveness_v2 control runs by default AND guards the same code path as the tally",
           broken_default_had_no_control and dup == 2, fixed and now_dup == 1, mutation_blocks,
           bdet + f"\nPOST-FIX default run: control precedes tally={fixed} rc={r2.returncode}\n"
                  f"POST-FIX copies of the gate logic: {now_dup} (one implementation)\n"
                  f"MUTATED gate (--selftest-mutate drop-g3): rc={r3.returncode}, tally "
                  f"suppressed={'verdict tally' not in r3.stdout} -> the control is not inert")


# --------------------------------------------------------------------------- D4
def control_d4() -> None:
    old = (CAS / "probe-output" / "adv0022_git_verifier_out.txt").read_text(encoding="utf-8")
    new_path = CAS / "probe-output" / "adv0022_git_verifier_out.R2.txt"
    new = new_path.read_text(encoding="utf-8")
    frozen = "219 files, of which 12"

    # DETECTOR NOTE (round 2): the first version asserted "raw_including_this_lane=225" was in
    # the OLD capture. It is not -- 225 is TODAY's value; the old capture computed 219. That
    # made the control demand a number the broken state never contained, so it scored the
    # defect as absent. The real, capture-time contradiction is internal to the old file:
    # the narrative claims a 12-file lane delta while the same block computes 219 - 208 = 11.
    # (The stray 12 is the C3 block's raw count, borrowed from the wrong block.)
    old_c2 = old.split("--- Q2:")[0]
    o_raw = int([ln for ln in old_c2.splitlines()
                 if ln.startswith("raw_including_this_lane=")][0].split("=")[1])
    o_ex = int([ln for ln in old_c2.splitlines()
                if ln.startswith("repo_wide_files_with_tool_permissions=")][0].split("=")[1])
    broken = frozen in old and (o_raw - o_ex) != 12
    fixed = frozen not in new

    # Independent recomputation of the delta the fixed probe now prints.
    raw = len(sh(["git", "grep", "-l", "tool_permissions"]).stdout.strip().splitlines())
    ex = len(sh(["git", "grep", "-l", "tool_permissions", "--",
                 ":!command-center/casualty"]).stdout.strip().splitlines())
    printed = None
    for line in new.splitlines():
        if line.startswith("self_match_inflation=") and "THIS lane" in line:
            printed = int(line.split("=")[1].split()[0])
    still = printed is not None and printed == raw - ex and raw > ex

    record("D4", "adv0022_git_verifier no longer narrates a frozen pair it also computes",
           broken, fixed, still,
           f"PRE-FIX capture narrates {frozen!r} while the SAME block computes raw={o_raw} "
           f"excluding-lane={o_ex} -> delta {o_raw - o_ex}, not 12. Wrong AT CAPTURE TIME, not "
           f"merely drifted: the 12 is the C3 block's raw count, borrowed from the wrong block\n"
           f"POST-FIX capture contains the frozen string: {frozen in new}\n"
           f"independent recomputation: raw={raw} excluding-lane={ex} delta={raw - ex}; "
           f"probe printed self_match_inflation={printed} -> agree={still}")


def main() -> int:
    print(f"ROUND-2 DEFECT CONTROLS  repo={ROOT}  head="
          f"{sh(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip()}")
    print("Each control materialises the PRE-FIX blob and requires the defect to REPRODUCE "
          "there before the fix may be called a fix.\n")
    control_d1("command-center/casualty/_probe_liveness.py", "ADV-LIVENESS.json", "D1a",
               ["ADV-COMPLETENESS-CENSUS.json", "ADV-DISPATCH-CENSUS.json"])
    control_d1("command-center/casualty/_probe_census.py", "ADV-COMPLETENESS-CENSUS.json",
               "D1b", [])
    control_d2()
    control_d3_d5()
    control_d4()

    out = CAS / "R2-DEFECT-CONTROLS.json"
    failed = [r for r in RESULTS if not r["PASS"]]
    out.write_text(json.dumps({
        "generated_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "head": sh(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "method": ("each defect is reproduced from the PRE-FIX blob at HEAD via "
                   "`git show HEAD:<path>` before the fixed code is trusted"),
        "controls": RESULTS,
        "all_pass": not failed,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    if failed:
        print(f"FAILED:r2-defect-controls {len(failed)} control(s) did not separate: "
              f"{[f['defect'] for f in failed]}")
        return 1
    print(f"SUCCESS:r2-defect-controls {len(RESULTS)} controls, all separate broken-vs-fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
