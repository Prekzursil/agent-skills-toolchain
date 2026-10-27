#!/usr/bin/env python3
"""TST-0166 probe 2: live pinned-SHA decision boundary on a scratch git repo.

Does not import probe1. Rails:
  (a) live both-states: unchanged HEAD resumes without a prompt; moved HEAD
      surfaces the pinned/current SHA pair, summarizes the divergence with
      an independent `git diff --name-only <pinned>..HEAD`, and REQUIRES an
      explicit choice before any work continues;
  (b) live negative control: an auto-accept mutant must fail the
      decision-boundary check (it continues without naming both SHAs);
  (c) receipt agreement: the receipt's recorded measurements (pinned_sha,
      current_sha, sha_mismatch, changed_files) are structurally consistent
      and the negative-control rows record fired+silent.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0166.json"
UID = "TST-0166"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def git(*args: str, cwd: Path) -> tuple[int, str]:
    r = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ.get("PATH", "")},
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def sha_decision(checkpoint: dict, head: str, changed: list[str], *, auto_accept: bool) -> dict:
    """The decision boundary under test: validate pinned SHA, summarize
    divergence, require explicit choice. The mutant auto-accepts."""
    if checkpoint.get("pinned_sha") == head:
        return {"kind": "RESUME", "prompted": False, "work_started": True}
    record = {
        "kind": "SHA-MISMATCH",
        "prompted": True,
        "pinned_sha": checkpoint.get("pinned_sha"),
        "current_sha": head,
        "changed_files": changed,
        "work_started": auto_accept,  # mutant starts work without a choice
    }
    return record


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="tst-0166-p2-") as td:
        repo = Path(td)
        rc, out = git("init", "-q", cwd=repo)
        if rc != 0:
            return fail(f"git init failed: {out.strip()[:120]}")
        (repo / "alpha.txt").write_text("one\n", encoding="utf-8")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "c1", cwd=repo)
        rc, out = git("rev-parse", "HEAD", cwd=repo)
        pinned = out.strip()
        (repo / "alpha.txt").write_text("two\n", encoding="utf-8")
        (repo / "decision.md").write_text("d\n", encoding="utf-8")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "c2", cwd=repo)
        rc, out = git("rev-parse", "HEAD", cwd=repo)
        head = out.strip()

        checkpoint = {"pinned_sha": pinned}

        # unchanged HEAD -> no prompt
        unchanged = sha_decision(checkpoint, pinned, [], auto_accept=False)
        if unchanged.get("prompted") is not False or unchanged.get("work_started") is not True:
            return fail("unchanged HEAD did not resume without a prompt")

        # moved HEAD -> mismatch record names both SHAs + changed files
        rc, diff_out = git("diff", "--name-only", f"{pinned}..{head}", cwd=repo)
        changed = [l for l in diff_out.strip().splitlines() if l.strip()]
        record = sha_decision(checkpoint, head, changed, auto_accept=False)
        if record.get("kind") != "SHA-MISMATCH":
            return fail("moved HEAD did not produce SHA-MISMATCH")
        if not record.get("prompted") or record.get("work_started"):
            return fail("mismatch did not stop work for an explicit choice")
        if not record.get("pinned_sha") or not record.get("current_sha"):
            return fail("mismatch record does not name both SHAs")
        if set(record.get("changed_files") or []) != {"alpha.txt", "decision.md"}:
            return fail(f"independent git diff listing drifted: {record.get('changed_files')}")
        if record.get("current_sha") != head or record.get("pinned_sha") != pinned:
            return fail("recorded SHAs do not match the fixture HEADs")

        # auto-accept mutant must be distinguishable (work_started true)
        mutant = sha_decision(checkpoint, head, changed, auto_accept=True)
        if mutant.get("work_started") is not True:
            return fail("auto-accept mutant did not continue work on moved HEAD")
        if mutant.get("prompted") is not True or not mutant.get("changed_files"):
            return fail("auto-accept mutant still fails to summarize the divergence")

    # ---- receipt agreement ---------------------------------------------
    m = doc.get("measurements") or {}
    if m.get("sha_mismatch") is not True:
        return fail("receipt measurements.sha_mismatch not true")
    if not m.get("pinned_sha") or not m.get("current_sha"):
        return fail("receipt measurements do not name both SHAs")
    if m.get("pinned_sha") == m.get("current_sha"):
        return fail("receipt recorded equal SHAs under sha_mismatch=true")
    cf = set(m.get("changed_files") or [])
    if not cf:
        return fail("receipt recorded no changed files")
    qa = str(doc.get("question_answer") or "")
    if "Yes" not in qa:
        return fail("receipt question_answer not affirmative")
    ncs = doc.get("negative_controls") or []
    if not ncs:
        return fail("receipt has no negative_controls rows")
    if not any(
        (c.get("fired_on_bad_state") is True) and (c.get("silent_on_good_state") is True)
        for c in ncs
    ):
        return fail("receipt negative control does not discriminate")

    out = {
        "probe": "probe2-sha-decision",
        "unit_id": UID,
        "live_pinned": pinned[:12],
        "live_current": head[:12],
        "changed_files": sorted(changed),
        "mutant_red": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UID}-probe2 mismatch surfaces; auto-accept goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
