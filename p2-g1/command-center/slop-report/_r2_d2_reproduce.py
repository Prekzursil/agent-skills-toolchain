"""BUILD R2 / D2 -- reproduce the self-refuting control receipt, DURABLY.

The verifier (MF1) and the auditor (D2) both claim: `_b1_control.out.json` was committed
asserting `quiet_citer_count: 0 / PASS`, but re-running its own script yields 2 / FAIL, because
committing the detector AND its receipt put the negative-control sentinel string into the very
corpus `citations()` greps.

H1 (defect real): at the rev that shipped them, the sentinel literal is present in >=1 tracked
     blob, the committed receipt says 0, and executing that script yields >0 and rc=1.
H2 (defect not real): the sentinel is absent from that tree, or the script still returns 0/PASS.

EVERYTHING HERE IS PINNED TO `fa87d1a2`, the commit that shipped the broken pair. The first
version of this probe ran the LIVE `_b1_control.py` -- which meant that the moment the fix
landed, this receipt would stop reproducing its own verdict. That is precisely the defect class
this round exists to close, so it was rewritten to execute the HISTORICAL BLOB instead: a
commit is immutable, so this reproduction is re-runnable forever.

The pre-fix script is run BYTE-UNMODIFIED (its sha256 is asserted against the blob before
execution). It hardcodes the tracked receipt as its output path, so it dirties that file. The
restore writes back the EXACT PRE-EXISTING BYTES, not `git checkout --`: the first run of this
probe used `git checkout --` and silently ate this round's own uncommitted, already-fixed
receipt, reverting it to the broken round-1 version. Restoring "to HEAD" and restoring "to what
was there" are different operations, and only the second is safe in a tree with live work in it.
"""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
HERE = os.path.join(ROOT, "command-center/slop-report")
OUT = os.path.join(HERE, "_r2_d2_reproduce.out.json")
RECEIPT_REL = "command-center/slop-report/_b1_control.out.json"
SCRIPT_REL = "command-center/slop-report/_b1_control.py"
IMPORT_REL = "command-center/slop-report/_b1_cited_probes.py"
SENTINEL = "_zzz_control_no_such_probe_9f3a17.py"
# The commit that shipped the broken detector + receipt together. Pinned, never resolved live:
# resolving it live would silently re-point at the FIX commit and the probe would go green.
PREFIX_REV = "fa87d1a2ef65dd3b9dbfc06e19f446c9fe06149e"


def git(*args, check=True, binary=False):
    r = subprocess.run(
        ["git", "-C", ROOT, *args],
        capture_output=True,
        text=not binary,
        encoding=None if binary else "utf-8",
        errors=None if binary else "replace",
    )
    if check and r.returncode not in (0, 1):
        raise SystemExit(f"git {args} rc={r.returncode}")
    return r


def grep_rev(needle, rev):
    r = git("grep", "-I", "-F", "-l", "-e", needle, rev, check=False)
    return sorted(p.split(":", 1)[1] for p in r.stdout.splitlines() if ":" in p)


def main():
    out = {
        "pinned_rev": PREFIX_REV,
        "live_head": git("rev-parse", "HEAD").stdout.strip(),
    }

    # ---- detector control for the grep itself (both states, at the pinned rev) --
    known_present = "_b1_cited_probes.py"
    ctl_fire = grep_rev(known_present, PREFIX_REV)
    ctl_quiet = grep_rev(f"_zz_nothing_{uuid.uuid4().hex}.py", PREFIX_REV)
    out["control"] = {
        "known_present_needle": known_present,
        "fire_hits": len(ctl_fire),
        "known_absent_needle": "<random per run>",
        "quiet_hits": len(ctl_quiet),
        "fires": len(ctl_fire) >= 1,
        "silent": len(ctl_quiet) == 0,
        "states_distinguishable": len(ctl_fire) > len(ctl_quiet),
    }

    # ---- A: the sentinel is inside the corpus AT THE REV THAT SHIPPED IT ------
    hits = grep_rev(SENTINEL, PREFIX_REV)
    out["A_sentinel_in_pinned_blobs"] = {"count": len(hits), "paths": hits}
    live_hits = grep_rev(SENTINEL, "HEAD")
    out["A_live_head_observation"] = {
        "count": len(live_hits),
        "paths": live_hits,
        "note": "DRIFTS. After the round-2 fix commit this drops to 1 (the receipt no longer "
        "carries the literal; _b1_control.py keeps it so the legacy control stays armed). "
        "It must never reach 0 -- at 0 the negative control is dead.",
    }

    # ---- B: what the COMMITTED receipt asserted ------------------------------
    committed = json.loads(git("show", f"{PREFIX_REV}:{RECEIPT_REL}").stdout)
    out["B_committed_receipt"] = {
        "quiet_citer_count": committed.get("quiet_citer_count"),
        "fire_citer_count": committed.get("fire_citer_count"),
        "verdict": committed.get("verdict"),
    }

    # ---- C: execute the PRE-FIX script, byte-unmodified ----------------------
    tmp = tempfile.mkdtemp(prefix="r2_d2_")
    try:
        blobs = {}
        for rel in (SCRIPT_REL, IMPORT_REL):
            raw = git("show", f"{PREFIX_REV}:{rel}", binary=True).stdout
            dst = pathlib.Path(tmp) / rel.rsplit("/", 1)[-1]
            dst.write_bytes(raw)
            blobs[rel] = hashlib.sha256(raw).hexdigest()[:16]
        materialised = {
            rel: hashlib.sha256(
                (pathlib.Path(tmp) / rel.rsplit("/", 1)[-1]).read_bytes()
            ).hexdigest()[:16]
            for rel in (SCRIPT_REL, IMPORT_REL)
        }
        before = git("status", "--porcelain", "--", RECEIPT_REL).stdout.strip()
        # Restore to what was ACTUALLY there, not to HEAD. `git checkout --` would silently
        # discard an uncommitted receipt -- measured: it ate this round's own regenerated
        # receipt on the first run of this probe.
        receipt_abs = os.path.join(ROOT, RECEIPT_REL)
        preexisting = pathlib.Path(receipt_abs).read_bytes()
        r = subprocess.run(
            [sys.executable, os.path.join(tmp, "_b1_control.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ROOT,
        )
        with open(receipt_abs, encoding="utf-8", newline="") as fh:
            after_run = json.loads(fh.read())
        dirty_after_run = git("status", "--porcelain", "--", RECEIPT_REL).stdout.strip()
        pathlib.Path(receipt_abs).write_bytes(preexisting)
        dirty_after_restore = git(
            "status", "--porcelain", "--", RECEIPT_REL
        ).stdout.strip()
        restored_exactly = pathlib.Path(receipt_abs).read_bytes() == preexisting
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out["C_execute_prefix_blob"] = {
        "script_source": f"git show {PREFIX_REV[:8]}:{SCRIPT_REL}",
        "blob_sha16": blobs,
        "materialised_sha16": materialised,
        "bytes_unmodified": blobs == materialised,
        "rc": r.returncode,
        "quiet_citer_count": after_run.get("quiet_citer_count"),
        "fire_citer_count": after_run.get("fire_citer_count"),
        "verdict": after_run.get("verdict"),
        "tracked_file_dirty_before": before,
        "tracked_file_dirty_after_run": dirty_after_run,
        "tracked_file_dirty_after_restore": dirty_after_restore,
        "restored_to_preexisting_bytes": restored_exactly,
        "restored_same_state_as_before": dirty_after_restore == before,
    }

    checks = {
        "control_both_states": out["control"]["fires"]
        and out["control"]["silent"]
        and out["control"]["states_distinguishable"],
        "ran_unmodified_historical_bytes": blobs == materialised,
        "H1_sentinel_in_pinned_tree": len(hits) >= 1,
        "H1_committed_receipt_says_zero": committed.get("quiet_citer_count") == 0,
        "H1_rerun_says_nonzero": (after_run.get("quiet_citer_count") or 0) > 0,
        "H1_rerun_rc_nonzero": r.returncode != 0,
        "H1_rerun_dirties_tracked_file": dirty_after_run != "",
        "restored_to_preexisting_bytes": restored_exactly,
        "restored_same_state_as_before": dirty_after_restore == before,
        "negative_control_still_armed_at_head": len(live_hits) >= 1,
    }
    out["checks"] = checks
    out["verdict"] = "D2-REPRODUCED" if all(checks.values()) else "D2-NOT-REPRODUCED"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "D2-REPRODUCED" else 1


if __name__ == "__main__":
    sys.exit(main())
