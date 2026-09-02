#!/usr/bin/env python3
"""Probe 2: test_corrected_form_resolves_to_the_same_object_in_both_shells."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from peel_measure import equivalent, live_measure  # noqa: E402

UNIT = "TST-0062"
ART = REPO / "command-center/receipts/TST-0062.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def _wrong_vs_commit(rec: dict, commit: str) -> bool:
    if not rec.get("ok"):
        return True
    sha = rec.get("sha") or ""
    return sha != commit


def main() -> int:
    m = live_measure()
    rows = m["rows"]
    commit = m["commit_sha"]
    if not commit or len(commit) != 40:
        return fail("could not peel annotated tag to a commit")
    if not m.get("tag_object_differs_from_commit"):
        return fail("annotated tag object SHA equals commit (peel control dead)")

    bash_q = rows["bash_quoted"]["sha"]
    bash_rl = rows["bash_rev_list"]["sha"]
    argv_peel = rows["peel_argv"]["sha"]
    argv_rl = rows["rev_list"]["sha"]
    leftover = rows["pwsh_leftover_argv"]
    cmd_m = rows["cmd_caret_unescape"]

    if not equivalent(commit, bash_q):
        return fail(f"bash quoted peel {bash_q!r} != commit {commit!r}")
    if not equivalent(commit, bash_rl):
        return fail(f"bash rev-list {bash_rl!r} != commit {commit!r}")
    if not equivalent(commit, argv_peel) or not equivalent(commit, argv_rl):
        return fail("execve argv peel/rev-list diverged from commit")

    if not _wrong_vs_commit(leftover, commit):
        return fail("pwsh leftover argv v1.4.1^ silently equalled the peel")
    if not _wrong_vs_commit(cmd_m, commit):
        return fail("cmd.exe-unescaped argv silently equalled the peel")

    pwsh = m.get("pwsh_path")
    pwsh_unquoted_rc = None
    if pwsh:
        uq = rows["unquoted_peel"]
        sq = rows["single_quoted_peel"]["sha"]
        dq = rows["double_quoted_peel"]["sha"]
        prl = rows["pwsh_rev_list"]["sha"]
        pwsh_unquoted_rc = uq.get("returncode")
        if not _wrong_vs_commit(uq, commit):
            return fail("live pwsh unquoted peel returned the commit SHA (hazard not live)")
        if not equivalent(commit, sq):
            return fail("pwsh single-quoted peel diverged from bash")
        if not equivalent(commit, dq):
            return fail("pwsh double-quoted peel diverged from bash")
        if not equivalent(commit, prl):
            return fail("pwsh rev-list diverged from bash")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0062" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {doc.get('state')}")
    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    if "test_corrected_form_resolves_to_the_same_object_in_both_shells" not in tests:
        return fail("catalog test id missing from receipt")

    payload = {
        "probe": "probe2-peel-equivalent",
        "unit_id": UNIT,
        "pass": True,
        "commit_sha": commit,
        "tag_object_sha": m["tag_object_sha"],
        "bash_quoted": bash_q,
        "bash_rev_list": bash_rl,
        "leftover_rc": leftover["returncode"],
        "leftover_sha": leftover["sha"],
        "cmd_unescape_rc": cmd_m["returncode"],
        "pwsh_path": pwsh,
        "pwsh_version": m.get("pwsh_version"),
        "pwsh_unquoted_rc": pwsh_unquoted_rc,
        "two_shells": ["bash", "pwsh" if pwsh else "execve-argv"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0062-probe2 corrected forms match; corrupted argv does not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
