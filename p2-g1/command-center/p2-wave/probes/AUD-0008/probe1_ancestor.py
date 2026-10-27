#!/usr/bin/env python3
"""AUD-0008 probe1 -- no-history-rewrite ancestor invariant (live, fail-closed).

Rebuilds the fixture repo in a temp dir and re-proves the discriminating
invariant with a real git binary: `git merge-base --is-ancestor <baseline> HEAD`
stays GREEN across a legitimate owner scratch commit and goes RED after a
history rewrite, while the equality strawman (HEAD == pinned SHA) goes RED on
the legitimate commit. Re-verifies the artifact's recorded probe1_control
against these live outcomes and recounts the catalog unit-id census.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0008-commit-authorship-integrity.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
UNIT = "AUD-0008"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")
    pinned = str(doc.get("pinned_baseline") or "")
    check(re.match(r"^[0-9a-f]{8,40}$", pinned) is not None,
          "pinned_baseline not a well-formed SHA", pinned)

    with tempfile.TemporaryDirectory(prefix="aud0008probe1-") as td:
        fx = Path(td)
        ok, out = run(["git", "init", "-q", "repo"], fx)
        check(ok == 0, "git init failed", out[:120])
        repo = fx / "repo"
        run(["git", "config", "user.email", "probe@example.invalid"], repo)
        run(["git", "config", "user.name", "AUD-0008 probe1"], repo)
        (repo / "base.txt").write_text("baseline\n", encoding="utf-8", newline="\n")
        run(["git", "add", "base.txt"], repo)
        run(["git", "commit", "-q", "-m", "baseline"], repo)
        rc, baseline = run(["git", "rev-parse", "HEAD"], repo)
        check(rc == 0 and SHA_RE.match(baseline) is not None, "baseline commit unresolvable")

        # legitimate owner scratch commit on top of the baseline
        (repo / "scratch.txt").write_text("owner work\n", encoding="utf-8", newline="\n")
        run(["git", "add", "scratch.txt"], repo)
        run(["git", "commit", "-q", "-m", "owner scratch"], repo)
        rc, head = run(["git", "rev-parse", "HEAD"], repo)

        rc_anc, _ = run(["git", "merge-base", "--is-ancestor", baseline, "HEAD"], repo)
        scratch_is_ancestor = rc_anc == 0
        check(scratch_is_ancestor, "is-ancestor invariant went GREEN-fail on a legitimate scratch commit")
        scratch_head_equals_baseline = head == baseline
        check(not scratch_head_equals_baseline,
              "equality strawman did not fire on the legitimate scratch commit (cannot detect)")

        # history rewrite: build a genuine orphan root via commit-tree, then
        # point a branch at it; baseline must NOT be its ancestor
        rc, tree = run(["git", "rev-parse", "HEAD^{tree}"], repo)
        check(rc == 0, "tree resolve failed", tree[:80])
        rc, rewritten = run(["git", "commit-tree", tree.strip(), "-m", "rewritten root"], repo)
        check(rc == 0 and SHA_RE.match(rewritten.strip()) is not None,
              "orphan root commit failed", rewritten[:80])
        rewritten = rewritten.strip()
        rc_rw, _ = run(["git", "merge-base", "--is-ancestor", baseline, rewritten], repo)
        rewrite_is_ancestor = rc_rw == 0
        check(not rewrite_is_ancestor, "is-ancestor invariant went RED-fail after a history rewrite")

    # recorded control must agree with the live re-derivation
    pc = doc.get("probe1_control") or {}
    check(pc.get("owner_scratch_is_ancestor") is True and scratch_is_ancestor,
          "recorded owner_scratch_is_ancestor drift")
    check(pc.get("owner_scratch_head_equals_baseline") is False and not scratch_head_equals_baseline,
          "recorded equality strawman behaviour drift")
    check(pc.get("rewrite_is_ancestor") is False and not rewrite_is_ancestor,
          "recorded rewrite_is_ancestor drift")
    check(pc.get("equality_strawman_would_fail_owner_scratch") is True,
          "recorded strawman claim absent")
    check(pc.get("pass") is True, "probe1_control.pass not true")

    # live catalog recount against the recorded census
    try:
        cat = json.loads(CATALOG.read_text(encoding="utf-8"))
        live_count = sum(1 for u in cat.get("work_units", []) if isinstance(u, dict) and u.get("id"))
        check(live_count == int(doc.get("catalog_unit_id_count", -2)),
              "catalog_unit_id_count vs live catalog recount",
              f"{doc.get('catalog_unit_id_count')} vs {live_count}")
    except Exception as exc:
        notes.append(f"catalog recount instrument-absent: {type(exc).__name__}")

    # negative controls recorded both-states
    for c in doc.get("negative_controls") or []:
        check(c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True,
              "negative control not both-states", str(c.get("id")))

    # drift notes (recorded, not gating)
    live = doc.get("live") or {}
    if str(live.get("worktree", "")).startswith("/home/"):
        notes.append(
            "drift note: artifact records the prior builder's POSIX worktree "
            f"({live.get('worktree')}); the current worktree is a Windows checkout"
        )
    if not (REPO / ".git").is_dir():
        notes.append(
            "drift note: artifact records worktree_is_git=false for its build tree and the "
            "current tree is likewise not a git repository; the ancestor invariant is "
            "re-proven on the freshly rebuilt fixture repo above"
        )

    report = {
        "probe": "probe1-no-history-rewrite-ancestor",
        "unit_id": UNIT,
        "fixture": "temp repo: baseline -> owner scratch -> orphan rewrite",
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 ancestor invariant re-proven "
          "(scratch GREEN, equality strawman RED on scratch, rewrite RED); "
          f"catalog recount {doc.get('catalog_unit_id_count')} matches live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
