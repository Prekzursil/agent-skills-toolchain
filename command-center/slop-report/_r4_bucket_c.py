"""DoD-3: a bucket-(c) deletion, backed by an EXECUTED regenerating command.

The DoD does not accept "a script exists that could regenerate this". It requires the
regenerating command to be SHOWN, so this runs the whole cycle and records each leg:

    exists -> DELETE -> assert ABSENT -> run the command -> assert PRESENT again

A file that survives that cycle is reproducible by anyone who has the repo, which is
what makes deleting it safe. A file that does not is bucket (b) and must be committed.

TARGET is deliberately one of THIS lane's own artifacts. The three bucket-(c) files the
classifier found live in `command-center/p2-wave/` and `platform/architecture/`, and
regenerating those means EXECUTING another lane's script while that lane is running --
a side effect this lane has declined twice and been vindicated for. Proving the property
on a file this lane owns costs nothing and risks nothing.

CONTROLS:
  K1 the producer is TRACKED. An untracked producer makes the command unrunnable in a
     clone, which is the very defect the published-command gate exists to catch.
  K2 the file really is ABSENT between the delete and the regenerate. Without this the
     cycle proves only that the file exists, not that the command created it.
  K3 the command exits 0.
  K4 the command dirties NO tracked file. A "regenerator" with side effects on tracked
     paths is not safe to run casually, whatever it does to its own output.
  K5 content equality is reported EXCLUDING the volatile `rev` field, and the raw digest
     is reported too. HEAD moves under this lane constantly (six times in round 3), so a
     byte difference confined to `rev` is churn, not a failure to reproduce -- and saying
     which of the two it is beats a bare pass/fail.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
TARGET = "command-center/slop-report/_r4_shellcov.out.json"
PRODUCER = "command-center/slop-report/_r4_shellcov.py"
COMMAND = ["python", PRODUCER]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def digest(path: str) -> str | None:
    fp = os.path.join(REPO, path)
    if not os.path.exists(fp):
        return None
    return hashlib.sha256(open(fp, "rb").read()).hexdigest()


def load_no_rev(path: str) -> dict | None:
    fp = os.path.join(REPO, path)
    if not os.path.exists(fp):
        return None
    d = json.load(open(fp, encoding="utf-8"))
    d.pop("rev", None)
    return d


def dirty_tracked() -> set[str]:
    return {
        ln[3:]
        for ln in git("status", "--porcelain").replace("\r\n", "\n").split("\n")
        if ln and not ln.startswith("??")
    }


def main() -> int:
    tracked = set(git("ls-files").replace("\r\n", "\n").split("\n"))
    res: dict = {"target": TARGET, "producer": PRODUCER, "command": " ".join(COMMAND)}

    res["K1_producer_is_tracked"] = PRODUCER in tracked
    if not res["K1_producer_is_tracked"]:
        res["verdict"] = "NOT-PROVEN: producer is untracked, so a clone cannot run it"
        print(json.dumps(res, indent=1))
        return 1

    res["existed_before"] = os.path.exists(os.path.join(REPO, TARGET))
    before_digest = digest(TARGET)
    before_body = load_no_rev(TARGET)
    dirty_before = dirty_tracked()

    os.remove(os.path.join(REPO, TARGET))
    res["K2_absent_after_delete"] = not os.path.exists(os.path.join(REPO, TARGET))

    r = subprocess.run(COMMAND, cwd=REPO, capture_output=True, text=True)
    res["K3_command_rc"] = r.returncode
    res["K3_command_rc_zero"] = r.returncode == 0

    res["present_after_regen"] = os.path.exists(os.path.join(REPO, TARGET))
    after_digest = digest(TARGET)
    after_body = load_no_rev(TARGET)
    dirty_after = dirty_tracked()

    res["K4_dirties_no_tracked_file"] = (dirty_after - dirty_before) == set()
    res["K4_newly_dirty"] = sorted(dirty_after - dirty_before)
    res["K5_digest_before"] = before_digest
    res["K5_digest_after"] = after_digest
    res["K5_byte_identical"] = before_digest == after_digest
    res["K5_identical_ignoring_rev"] = before_body == after_body

    ok = (
        res["K1_producer_is_tracked"]
        and res["existed_before"]
        and res["K2_absent_after_delete"]
        and res["K3_command_rc_zero"]
        and res["present_after_regen"]
        and res["K4_dirties_no_tracked_file"]
        and res["K5_identical_ignoring_rev"]
    )
    res["verdict"] = "BUCKET-C-PROVEN" if ok else "BUCKET-C-NOT-PROVEN"
    with open(
        os.path.join(REPO, "command-center/slop-report/_r4_bucket_c.out.json"),
        "w",
        encoding="utf-8",
        newline="\n",
    ) as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
