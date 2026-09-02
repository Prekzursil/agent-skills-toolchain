#!/usr/bin/env python3
"""Probe 1: emit a decision packet for each of 28 content-differing rules files.

Signal 1 of the catalog evidence requirement. Unique-line sets come from
plugin.packet (str-set differ). Host live trees are re-measured; on this
Linux worktree they are absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from plugin.classifier import DIVERGED, LIVE_AHEAD, REPO_AHEAD  # noqa: E402
from plugin.packet import emit_packet, packet_has_both_unique_sets  # noqa: E402

OUT = HERE / "probe1-packets.raw.json"
PACKETS = HERE / "packets.json"


def main() -> int:
    host = F.host_candidates()
    host_present = [h for h in host if h["is_dir"] and h["file_count"] > 0]
    snap = F.build_fixtures()
    ledger = F.load_ledger()
    packets: list[dict] = []
    for rel in F.PATHS:
        repo_text, live_text, _rp, lp = F.read_pair(rel)
        packets.append(
            emit_packet(
                path=rel,
                repo_text=repo_text,
                live_text=live_text,
                repo_root=REPO,
                live_path=lp,
                ledger=ledger,
            )
        )

    nonempty_one_side = 0
    both_unique = 0
    by_class: dict[str, int] = {}
    planted_ok = 0
    for i, pkt in enumerate(packets):
        planted = F.kind_for(i)
        got = pkt["classification"]
        by_class[got] = by_class.get(got, 0) + 1
        if planted == got:
            planted_ok += 1
        ru, lu = pkt["repo_unique_lines"], pkt["live_unique_lines"]
        if ru or lu:
            nonempty_one_side += 1
        if packet_has_both_unique_sets(pkt):
            both_unique += 1
        if got == DIVERGED:
            if not packet_has_both_unique_sets(pkt):
                print("FAILED:IMP-0036-probe1 DIVERGED missing a unique-line set")
                return 1
            if pkt["recommendation"]["action"] != "HOLD-FOR-RECORDED-DECISION":
                print("FAILED:IMP-0036-probe1 DIVERGED auto-resolved")
                return 1
            if pkt["facts"]["used_as_authorship"] is not False:
                print("FAILED:IMP-0036-probe1 size used as authorship")
                return 1
            if pkt["mtime_is_authorship_signal"] is not False:
                print("FAILED:IMP-0036-probe1 mtime used as authorship")
                return 1
            if pkt["decision"]["status"] != "UNRECORDED":
                print("FAILED:IMP-0036-probe1 auto-recorded a decision")
                return 1
            if pkt["recommendation"]["kind"] == pkt["decision"]["kind"]:
                print("FAILED:IMP-0036-probe1 recommendation not distinguishable")
                return 1
        rec = pkt["recommendation"]
        if rec["may_authorize_act"] is not False or rec["kind"] != "advisory":
            print("FAILED:IMP-0036-probe1 recommendation not advisory")
            return 1
        git = pkt["last_repo_commit"]["git"]
        if "format=%cI" not in str(git.get("command") or ""):
            print("FAILED:IMP-0036-probe1 missing git log %cI command")
            return 1
        if pkt["live_mtime"] is None:
            print("FAILED:IMP-0036-probe1 missing live mtime")
            return 1

    if len(packets) != 28:
        print(f"FAILED:IMP-0036-probe1 expected 28 packets got {len(packets)}")
        return 1
    if nonempty_one_side != 28:
        print("FAILED:IMP-0036-probe1 a packet has empty unique sets on both sides")
        return 1
    if planted_ok != 28:
        print(f"FAILED:IMP-0036-probe1 planted/got mismatch {planted_ok}/28")
        return 1
    if by_class.get(DIVERGED, 0) != 20:
        print(f"FAILED:IMP-0036-probe1 DIVERGED count {by_class}")
        return 1
    if by_class.get(REPO_AHEAD, 0) != 5 or by_class.get(LIVE_AHEAD, 0) != 3:
        print(f"FAILED:IMP-0036-probe1 one-sided counts {by_class}")
        return 1
    if both_unique != 20:
        print(f"FAILED:IMP-0036-probe1 both-unique {both_unique}")
        return 1

    payload = {
        "probe": "probe1-packets",
        "unit_id": "IMP-0036",
        "host_candidates": host,
        "host_present_trees": len(host_present),
        "fixture_count": snap["count"],
        "packet_count": len(packets),
        "nonempty_unique_one_side": nonempty_one_side,
        "both_unique_sets": both_unique,
        "by_classification": by_class,
        "cited_owner_live_tree": False,
        "packets": packets,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    PACKETS.write_text(json.dumps({"packets": packets}, indent=2) + "\n", encoding="utf-8")
    print(
        "host_present_trees="
        + str(len(host_present))
        + " packets="
        + str(len(packets))
        + " nonempty_one_side="
        + str(nonempty_one_side)
        + " both_unique="
        + str(both_unique)
        + " DIVERGED="
        + str(by_class.get(DIVERGED, 0))
        + " REPO-AHEAD="
        + str(by_class.get(REPO_AHEAD, 0))
        + " LIVE-AHEAD="
        + str(by_class.get(LIVE_AHEAD, 0))
        + " cited_owner_live_tree=False"
    )
    print("SUCCESS:IMP-0036-probe1 28 decision packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
