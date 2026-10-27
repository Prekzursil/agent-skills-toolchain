"""DoD-3, round 5 -- the round-4 demonstration ran on a file that was in NO bucket. Fixed.

WHAT WAS WRONG (audit finding D1, CONFIRMED):
round 4's cycle targeted `command-center/slop-report/_r4_shellcov.out.json`, which
`git ls-tree -r 7ccaa24b` shows was ALREADY TRACKED at the classification rev. A tracked
file was never an untracked candidate, so it appears in no bucket at all -- while the
round-4 report's own bucket-(c) table listed a DIFFERENT file. The property was really
demonstrated; the sentence "one deletion EXECUTED" read as a bucket-(c) deletion and was
wider than its evidence.

THIS ROUND runs the cycle on a REAL bucket-(c) candidate:

    target   platform/architecture/_secfirst_selfaudit.out.json   (untracked, bucket c)
    producer platform/architecture/_secfirst_selfaudit.py         (TRACKED)

WHY THE CYCLE ENDS IN A RESTORE, AND WHY THAT IS NOT A DODGE.
The target is ANOTHER LANE's receipt. Regenerating a receipt is not idempotent: this one
re-derives working-tree counts that have moved since its pin, so re-running it OVERWRITES
a measurement taken at a different rev. Deleting or silently rewriting another lane's
evidence is exactly the destructive-action default this program forbids, and this lane's
mandate is propose-moves / execute-only-the-unambiguous. So the run proves the property
and then puts the original bytes back, with a digest proving the restore was exact.
Zero bucket-(c) files are deleted by this lane. The DoD item -- "bucket (c) deletions each
backed by a shown regenerating command" -- is satisfied because there are no unbacked
deletions, and the regenerating command is now SHOWN on a file that really is in bucket (c).

K7 IS THE NEW ONE AND IT CHANGES THE VERDICT.
"Reproducible" has two different meanings and round 4 did not separate them:
  (i)  regenerable IN THIS WORKTREE by a tracked command, and
  (ii) regenerable BY ANYONE WHO CLONES THE REPO.
Only (ii) makes a file safe to delete. K7 walks the producer's declared inputs and asks
whether each is tracked. An untracked input means a clone cannot rebuild the file, so the
file is bucket (b) -- evidence that exists only here -- however cleanly it regenerates on
this disk.

CONTROLS:
  K1 producer is tracked.
  K2 the target really is ABSENT between delete and regenerate (else the cycle proves
     only that a file exists).
  K3 the command exits 0.
  K4 nothing OTHER than the target changed -- computed over the FULL `-uall` porcelain,
     so a new untracked side-effect file is caught too, not just tracked churn.
  K5 byte identity reported, never required (a receipt embeds the rev it was taken at).
  K6 the SUBSTANCE survives: same checks, same controls, same auditor-valid verdict.
  K7 clone-regenerability: every declared input tracked.
  K8 RESTORE verified by digest against the pre-delete original.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
BACKUP_DIR = (
    "C:/Users/PREKZU~1/AppData/Local/Temp/claude/C--Users-Prekzursil/"
    "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/scratchpad"
)
OUT = os.path.join(REPO, "command-center/slop-report/_r5_bucket_c.out.json")

TARGET = "platform/architecture/_secfirst_selfaudit.out.json"
PRODUCER = "platform/architecture/_secfirst_selfaudit.py"
COMMAND = ["python", PRODUCER]

# Read out of the producer's source, not guessed: every path it opens for READ.
DECLARED_INPUTS = [
    "platform/architecture/security-first.md",
    "platform/architecture/_secfirst_measure.out.json",
    "platform/architecture/_secfirst_measure2.out.json",
    "platform/architecture/_secfirst_measure3.out.json",
    "platform/architecture/_secfirst_probe_denydefault.out.json",
    "command-center/WORK-UNIT-CATALOG.json",
]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def porcelain() -> set[str]:
    return {
        ln
        for ln in git("status", "--porcelain", "-uall")
        .replace("\r\n", "\n")
        .split("\n")
        if ln.strip()
    }


def digest_of(path: str) -> str | None:
    fp = os.path.join(REPO, path)
    if not os.path.exists(fp):
        return None
    with open(fp, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def substance(raw: bytes | None) -> dict | None:
    """The structural claim, minus the numbers a moving tree legitimately changes."""
    if raw is None:
        return None
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return {
        "probe": body.get("probe"),
        "checks_n": body.get("checks_n"),
        "controls_n": body.get("controls_n"),
        "controls_caught": body.get("controls_caught"),
        "auditor_valid": body.get("auditor_valid"),
        "claim_labels": sorted(r.get("claim") for r in body.get("rows", [])),
    }


def main() -> int:
    fp = os.path.join(REPO, TARGET)
    tracked = {p for p in git("ls-files").replace("\r\n", "\n").split("\n") if p}
    res: dict = {
        "rev": git("rev-parse", "HEAD").strip()[:8],
        "target": TARGET,
        "producer": PRODUCER,
        "command": " ".join(COMMAND),
    }

    res["K1_producer_is_tracked"] = PRODUCER in tracked
    res["target_is_untracked_candidate"] = TARGET not in tracked
    res["existed_before"] = os.path.exists(fp)
    if not (
        res["K1_producer_is_tracked"]
        and res["target_is_untracked_candidate"]
        and res["existed_before"]
    ):
        res["verdict"] = "NOT-RUN: preconditions unmet, nothing was deleted"
        json.dump(res, sys.stdout, indent=1, sort_keys=True)
        return 1

    # ---- K7: could a CLONE rebuild this? ----------------------------------
    inputs = {p: (p in tracked) for p in DECLARED_INPUTS}
    res["K7_declared_inputs_tracked"] = inputs
    res["K7_untracked_inputs"] = sorted(p for p, t in inputs.items() if not t)
    res["K7_clone_regenerable"] = not res["K7_untracked_inputs"]

    # ---- back up OUTSIDE the repo before touching anything ----------------
    with open(fp, "rb") as fh:
        original = fh.read()
    before_digest = hashlib.sha256(original).hexdigest()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, "_r5_bucket_c_backup.bin")
    with open(backup, "wb") as fh:
        fh.write(original)
    res["backup_path"] = backup
    res["backup_verified"] = (
        hashlib.sha256(open(backup, "rb").read()).hexdigest() == before_digest
    )
    if not res["backup_verified"]:
        res["verdict"] = "NOT-RUN: backup did not verify, nothing was deleted"
        json.dump(res, sys.stdout, indent=1, sort_keys=True)
        return 1

    state_before = porcelain()
    regenerated = None
    try:
        os.remove(fp)
        res["K2_absent_after_delete"] = not os.path.exists(fp)

        proc = subprocess.run(COMMAND, cwd=REPO, capture_output=True, text=True)
        res["K3_command_rc"] = proc.returncode
        res["K3_command_rc_zero"] = proc.returncode == 0
        res["K3_stdout_tail"] = proc.stdout.strip().splitlines()[-3:]

        res["present_after_regen"] = os.path.exists(fp)
        if res["present_after_regen"]:
            with open(fp, "rb") as fh:
                regenerated = fh.read()
        state_after = porcelain()
        other = {ln for ln in (state_after - state_before) if not ln.endswith(TARGET)}
        res["K4_no_other_change"] = other == set()
        res["K4_other_lines"] = sorted(other)
        res["K5_digest_before"] = before_digest[:16]
        res["K5_digest_after"] = (
            hashlib.sha256(regenerated).hexdigest()[:16] if regenerated else None
        )
        res["K5_byte_identical"] = regenerated == original
        sub_b, sub_a = substance(original), substance(regenerated)
        res["K6_substance_reproduced"] = sub_b is not None and sub_b == sub_a
        res["K6_checks_before"] = (sub_b or {}).get("checks_n")
        res["K6_checks_after"] = (sub_a or {}).get("checks_n")
    finally:
        # ---- K8: put the lane's evidence back, byte for byte --------------
        with open(fp, "wb") as fh:
            fh.write(original)
        res["K8_restored"] = digest_of(TARGET) == before_digest

    res["regeneration_proven"] = bool(
        res.get("K2_absent_after_delete")
        and res.get("K3_command_rc_zero")
        and res.get("present_after_regen")
        and res.get("K4_no_other_change")
        and res.get("K6_substance_reproduced")
    )
    res["deleted_by_this_lane"] = 0
    if not res["K8_restored"]:
        res["verdict"] = "RESTORE-FAILED -- manual attention required"
    elif res["regeneration_proven"] and res["K7_clone_regenerable"]:
        res["verdict"] = "BUCKET-C-CONFIRMED: regenerable from tracked inputs alone"
    elif res["regeneration_proven"]:
        res["verdict"] = (
            "RECLASSIFY-TO-B: regenerates HERE, but a clone cannot -- "
            "an input exists only on this disk"
        )
    else:
        res["verdict"] = "NOT-REPRODUCIBLE: bucket (b), must be committed not deleted"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    ok = res["K8_restored"] and res["regeneration_proven"]
    print("SUCCESS:r5-bucket-c" if ok else "FAILED:r5-bucket-c see-verdict")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
