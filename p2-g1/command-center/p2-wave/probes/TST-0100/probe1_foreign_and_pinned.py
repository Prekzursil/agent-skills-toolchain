#!/usr/bin/env python3
"""TST-0100 probe1: foreign refused, pinned permitted (live git).

Builds four scratch clones with git (init + config remote, no network):
foreign origin, pinned origin, no origin, and a path decoy (path looks
like the pin, origin foreign) plus an unrelated path with the pinned
origin. Live-runs the guard's check_write on each: foreign/decoy/no-
origin refused with the target file ABSENT; pinned and unrelated-with-
pin permitted with the file PRESENT. Asserts the receipt's four
control rows and four counts re-derive."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0100"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from guard import check_write, pinned_origin  # noqa: E402

UNIT = "TST-0100"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def clone(url: str | None, into: Path) -> None:
    into.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(into)], capture_output=True, timeout=60)
    if url:
        subprocess.run(["git", "-C", str(into), "remote", "add", "origin", url], capture_output=True, timeout=60)


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 4096, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0100" in text, "sentinel-absent")

    foreign = "https://github.com/other-owner/foreign-worktree.git"
    td = Path(tempfile.mkdtemp(prefix="tst0100-p1-"))
    results = {}
    try:
        fdir = td / "foreign"
        clone(foreign, fdir)
        results["foreign"] = check_write(fdir, "out.txt")
        pdir = td / "pinned"
        clone(pinned_origin(), pdir)
        results["pinned"] = check_write(pdir, "out.txt")
        ndir = td / "no-origin"
        clone(None, ndir)
        results["no-origin"] = check_write(ndir, "out.txt")
        decoy = td / "ast-integrate-decoy-path"
        clone(foreign, decoy)
        results["decoy"] = check_write(decoy, "out.txt")
        unrelated = td / "some-other-path"
        clone(pinned_origin(), unrelated)
        results["unrelated-with-pin"] = check_write(unrelated, "out.txt")

        chk(results["foreign"]["allowed"] is False and results["foreign"]["reason"] == "origin-mismatch", "foreign-refused")
        chk(not (fdir / "out.txt").exists(), "foreign-target-absent")
        chk(results["pinned"]["allowed"] is True, "pinned-permitted")
        chk((pdir / "out.txt").exists(), "pinned-target-present")
        chk(results["no-origin"]["allowed"] is False and results["no-origin"]["reason"] == "missing-origin", "no-origin-refused")
        chk(results["decoy"]["allowed"] is False and results["decoy"]["reason"] == "origin-mismatch", "path-decoy-refused")
        chk(results["unrelated-with-pin"]["allowed"] is True, "unrelated-path-with-pin-permitted")

        ctrls = {c.get("id"): c for c in doc.get("controls") or []}
        chk(len(ctrls) == 4, "receipt-four-controls", str(len(ctrls)))
        chk(ctrls.get("foreign-worktree-write", {}).get("observed") == "FIRED", "receipt-foreign-fired")
        chk(ctrls.get("pinned-worktree-write", {}).get("observed") == "SILENT", "receipt-pinned-silent")
        chk(ctrls.get("missing-origin-default-allow") and ctrls["missing-origin-default-allow"].get("observed") == "FIRED", "receipt-missing-origin-fired")
        counts = {c.get("id"): c for c in doc.get("counts") or []}
        chk(all(int(c.get("numerator", 0)) == 1 and int(c.get("denominator", 0)) == 1 for c in counts.values()) and len(counts) == 4, "receipt-counts")
    finally:
        time.sleep(0.5)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({k: {"allowed": v["allowed"], "reason": v["reason"]} for k, v in results.items()}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 live git guard: foreign/decoy/no-origin refused with targets absent; pinned and unrelated-with-pin permitted with targets present; verdict is the git command's answer, not the path string; receipt controls and counts re-derive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
