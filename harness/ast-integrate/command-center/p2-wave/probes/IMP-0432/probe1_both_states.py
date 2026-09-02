#!/usr/bin/env python3
"""Named probe 1: both-states write (wrong-repo refuse, right-repo permit).

A discriminating guard must PERMIT the pinned origin and REFUSE a foreign
origin. A write that was refused must leave no new bytes (pre-seeded marker
intact). Path-string matching is not this probe's subject — see probe 2.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import MARKER, PAYLOAD, build_cases  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0432.json"
SENTINEL = "SENTINEL:IMP-0432:WORKTREE-REPO-ASSERTED"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0432-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing or too small")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0432":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    with tempfile.TemporaryDirectory(prefix="imp0432-p1-") as tmp:
        rows = build_cases(Path(tmp))
        by_id = {r["id"]: r for r in rows}
        right = by_id["right-repo-https"]
        ssh = by_id["right-repo-ssh-alias"]
        wrong = by_id["wrong-repo"]

        if right["decision"] != "PERMIT" or not right["result"]["write_performed"]:
            return fail(f"right-repo did not permit write: {right['decision']} {right['reason']}")
        if right["result"].get("bytes_after") != PAYLOAD:
            return fail("right-repo write did not persist payload")
        if ssh["decision"] != "PERMIT" or not ssh["result"]["write_performed"]:
            return fail(f"ssh-alias of pin did not permit: {ssh['decision']} {ssh['reason']}")

        if wrong["decision"] != "REFUSE" or wrong["result"]["write_performed"]:
            return fail(
                f"wrong-repo did not refuse write: {wrong['decision']} "
                f"performed={wrong['result']['write_performed']}"
            )
        if wrong["reason"] != "WRONG_REPO":
            return fail(f"wrong-repo reason {wrong['reason']} want WRONG_REPO")
        if wrong["result"].get("bytes_after") != MARKER:
            return fail("wrong-repo write mutated or deleted the pre-seeded marker")
        if not wrong["marker_intact"]:
            return fail("wrong-repo marker not intact")

        cmd = wrong["git_command"] or []
        if "remote" not in cmd or "get-url" not in cmd:
            return fail(f"origin not resolved by git command: {cmd}")
        if wrong.get("path_string_used_as_origin"):
            return fail("guard used path string as origin")
        if right["decision"] == wrong["decision"]:
            return fail("both-states collapsed: right and wrong produced the same decision")

    table = doc.get("worktree_origin_table") or []
    if not any(r.get("reason") == "WRONG_REPO" and r.get("match_verdict") == "REFUSE" for r in table):
        return fail("receipt table lacks a wrong-repo REFUSE row")
    if not any(r.get("reason") == "MATCH" and r.get("match_verdict") == "PERMIT" for r in table):
        return fail("receipt table lacks a MATCH PERMIT row")

    summary = {
        "probe": "probe1-both-states",
        "unit_id": "IMP-0432",
        "pass": True,
        "right_repo_permitted": True,
        "ssh_alias_permitted": True,
        "wrong_repo_refused": True,
        "wrong_repo_marker_intact": True,
        "resolved_by_git_command": True,
        "right_origin": right["resolved_origin_url"],
        "wrong_origin": wrong["resolved_origin_url"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0432-probe1 both-states wrong-repo refuse / right-repo permit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
