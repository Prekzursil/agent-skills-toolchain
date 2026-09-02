#!/usr/bin/env python3
"""Named probe 2: missing origin fail-closed + origin resolved by git command.

A worktree with no origin must be refused, not defaulted to allowed.
A directory whose path contains the pinned repo name but whose origin is a
foreign URL must be refused — proving the guard does not trust path strings.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import MARKER, build_cases, pin_doc, pinned_url  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0432.json"
SENTINEL = "SENTINEL:IMP-0432:WORKTREE-REPO-ASSERTED"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0432-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing or too small")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    pin = pin_doc()
    if pin.get("fail_closed_when_origin_missing") is not True:
        return fail("pin fail_closed_when_origin_missing is not true")

    token = Path(pinned_url().rstrip("/")).name.replace(".git", "")

    with tempfile.TemporaryDirectory(prefix="imp0432-p2-") as tmp:
        rows = build_cases(Path(tmp))
        by_id = {r["id"]: r for r in rows}
        missing = by_id["missing-origin"]
        spoof = by_id["path-spoof-wrong-origin"]

        if missing["decision"] != "REFUSE" or missing["result"]["write_performed"]:
            return fail(
                f"missing-origin defaulted to allow: decision={missing['decision']} "
                f"performed={missing['result']['write_performed']}"
            )
        if missing["reason"] != "MISSING_ORIGIN":
            return fail(f"missing-origin reason {missing['reason']} want MISSING_ORIGIN")
        if missing["result"].get("bytes_after") != MARKER:
            return fail("missing-origin write mutated the pre-seeded marker")
        if not missing["naive_missing_would_allow"]:
            return fail("negative control naive_missing_origin_allow did not fire on the no-origin tree")

        if spoof["decision"] != "REFUSE" or spoof["result"]["write_performed"]:
            return fail(f"path-spoof was not refused: {spoof['decision']}")
        if not spoof["naive_path_would_permit"]:
            return fail("spoof path does not contain pin token; negative control is vacuous")
        if spoof.get("path_string_used_as_origin"):
            return fail("guard used path string as origin")
        cmd = spoof["git_command"] or []
        if "remote" not in cmd or "get-url" not in cmd:
            return fail(f"origin not resolved by git command: {cmd}")
        if spoof["resolved_origin_url"] is None:
            return fail("spoof tree origin was not resolved (need a foreign URL, not a miss)")
        if token.lower() in str(spoof["resolved_origin_url"]).lower() and "evil.example" not in str(
            spoof["resolved_origin_url"]
        ):
            return fail("spoof origin unexpectedly looks like the pin")

    table = doc.get("worktree_origin_table") or []
    if not any(r.get("reason") == "MISSING_ORIGIN" and r.get("match_verdict") == "REFUSE" for r in table):
        return fail("receipt table lacks a MISSING_ORIGIN REFUSE row")

    summary = {
        "probe": "probe2-fail-closed",
        "unit_id": "IMP-0432",
        "pass": True,
        "missing_origin_refused": True,
        "missing_origin_not_default_allow": True,
        "path_spoof_refused": True,
        "naive_path_matcher_would_permit_spoof": True,
        "naive_missing_would_allow": True,
        "resolved_by_git_command": True,
        "spoof_origin": spoof["resolved_origin_url"],
        "spoof_worktree": spoof["worktree"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0432-probe2 missing-origin refuse and command-not-path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
