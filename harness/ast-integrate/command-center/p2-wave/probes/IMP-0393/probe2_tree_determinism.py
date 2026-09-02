#!/usr/bin/env python3
"""Probe 2: duplicated deployed trees + cwd-invariance + receipt cross-check.

Evidence requirement: full duplicate list with candidate paths, winner, and
rule; plus a same-input-different-cwd determinism check.

Failure class cwd-dependent-nondeterminism: preferring the tree that contains
cwd must NOT be how duplicated trees are resolved. A known-broken helper that
does that is required to disagree with the production resolver (both-states).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from conflict_resolve import (  # noqa: E402
    TREE_RULE,
    cwd_tree_shadow_winner,
    group_by_name,
    resolve_index,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0393.json"
SENTINEL = "SENTINEL:IMP-0393:CONFLICTS-RESOLVED-DETERMINISTIC"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0393-probe2 {msg}")
    return 1


def winner_id(report: dict, name: str) -> str | None:
    row = report["winners_by_name"][name]
    w = row.get("winner") or {}
    return w.get("capability_id")


def main() -> int:
    idx = S.index()
    grouped = group_by_name(idx["records"])
    if len(grouped.get("shadowed") or []) != 2:
        return fail("fixture must have exactly two shadowed tree copies")

    from_web = S.resolve_at(S.CWD_WEB_SRC)
    from_other = S.resolve_at(S.CWD_OTHER)
    from_claude = S.resolve_at(S.CLAUDE_TREE / "shadowed")
    from_agents = S.resolve_at(S.AGENTS_TREE / "shadowed")

    for label, report in (
        ("web", from_web),
        ("other", from_other),
        ("claude-tree", from_claude),
        ("agents-tree", from_agents),
    ):
        row = report["winners_by_name"]["shadowed"]
        if not row["entered_resolution"]:
            return fail(f"shadowed did not enter resolution from {label}")
        if row["rule"] != TREE_RULE:
            return fail(f"shadowed rule from {label}={row['rule']} want={TREE_RULE}")
        if winner_id(report, "shadowed") != "cap.shadowed.claude":
            return fail(
                f"shadowed winner from {label}="
                f"{winner_id(report, 'shadowed')} want=cap.shadowed.claude"
            )

    # Process-cwd leak: chdir into each tree and re-resolve with the same
    # requested cwd argument. Production ranking uses index_root, not getcwd.
    saved = Path.cwd()
    try:
        os.chdir(S.CLAUDE_TREE)
        a = resolve_index(idx, S.CWD_OTHER)
        os.chdir(S.AGENTS_TREE)
        b = resolve_index(idx, S.CWD_OTHER)
    finally:
        os.chdir(saved)
    if winner_id(a, "shadowed") != winner_id(b, "shadowed"):
        return fail("process cwd leaked into duplicated-tree winner")
    if winner_id(a, "deploy") != winner_id(b, "deploy"):
        return fail("process cwd leaked into deploy winner for a fixed cwd arg")

    # Known-broken control: prefer the tree that contains cwd. Must fire
    # (disagree with production) when cwd is inside the losing tree.
    recs = grouped["shadowed"]
    broken = cwd_tree_shadow_winner(recs, S.AGENTS_TREE / "shadowed", idx["root"])
    production = from_agents["winners_by_name"]["shadowed"]["winner"]
    if broken is None:
        return fail("broken helper returned None")
    if broken.get("capability_id") == production.get("capability_id"):
        return fail("cwd-tree-shadow helper agreed with production (control silent)")
    if broken.get("capability_id") != "cap.shadowed.agents":
        return fail(
            f"cwd-tree-shadow helper winner={broken.get('capability_id')} "
            "want=cap.shadowed.agents"
        )

    # Same-input repeat determinism.
    again = S.resolve_at(S.CWD_OTHER)
    if json.dumps(from_other, sort_keys=True) != json.dumps(again, sort_keys=True):
        return fail("same cwd produced a different report")

    receipt_ok = None
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if SENTINEL not in RECEIPT.read_text(encoding="utf-8"):
            return fail("receipt missing completion sentinel")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {st}")
        table = doc.get("duplicate_resolutions") or []
        if not isinstance(table, list) or len(table) < 2:
            return fail("receipt duplicate_resolutions too short")
        live_by_key = {}
        for report in (from_web, from_other):
            for row in report["conflicts"]:
                live_by_key[(row["name"], report["cwd"])] = row
        matched = 0
        for item in table:
            if not isinstance(item, dict):
                continue
            key = (item.get("name"), item.get("cwd"))
            live = live_by_key.get(key)
            if live is None:
                continue
            want = (live["winner"] or {}).get("capability_id")
            got = item.get("winner_id") or (item.get("winner") or {}).get("capability_id")
            if got != want:
                return fail(f"receipt winner mismatch {key}: {got} != {want}")
            if item.get("rule") != live.get("rule"):
                return fail(f"receipt rule mismatch {key}")
            matched += 1
        if matched < 2:
            return fail(f"receipt table did not overlap live conflicts matched={matched}")
        if "unique-only" in [i.get("name") for i in table if isinstance(i, dict)]:
            return fail("receipt listed unique-only as a duplicate")
        receipt_ok = True

    summary = {
        "probe": "probe2-tree-determinism",
        "shadowed_winner": "cap.shadowed.claude",
        "cwd_invariant": True,
        "process_cwd_invariant": True,
        "broken_helper_fired": True,
        "receipt_cross_checked": receipt_ok,
        "pass": True,
        "unit_id": "IMP-0393",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "shadowed_winner=cap.shadowed.claude "
        "broken_helper="
        + str(broken.get("capability_id"))
        + " receipt_cross_checked="
        + str(receipt_ok)
    )
    print("SUCCESS:IMP-0393-probe2 duplicated-tree precedence is cwd-invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
