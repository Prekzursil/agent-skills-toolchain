#!/usr/bin/env python3
"""IMP-0036 probe1: emit decision packets over the planted divergence tree.

Contract under test: every DIVERGED packet carries BOTH unique-line sets, an
advisory recommendation (may_authorize_act=false, HOLD-FOR-RECORDED-DECISION),
an UNRECORDED owner-decision slot, and records mtime WITHOUT treating it (or
size) as an authorship signal.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.packet import emit_packet, packet_has_both_unique_sets  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "packets.json"


def main() -> int:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="imp0036-p1-"))
    try:
        repo_root = tmp / "repo"
        live_root = tmp / "live"
        rels = sorted(spec["files"])
        packets = []
        classes = {}
        for rel in rels:
            entry = spec["files"][rel]
            (repo_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (live_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo_root / rel).write_text(entry["repo"], encoding="utf-8", newline="\n")
            (live_root / rel).write_text(entry["live"], encoding="utf-8", newline="\n")
        for rel in rels:
            pkt = emit_packet(
                path=rel,
                repo_text=(repo_root / rel).read_text(encoding="utf-8"),
                live_text=(live_root / rel).read_text(encoding="utf-8"),
                repo_root=repo_root,
                live_path=(live_root / rel),
            )
            classes[pkt["classification"]] = classes.get(pkt["classification"], 0) + 1
            packets.append(pkt)

        diverged = [p for p in packets if p["classification"] == "DIVERGED"]
        nonempty_one_side = [p for p in packets
                             if p["repo_unique_lines"] or p["live_unique_lines"]]
        both_unique = [p for p in packets if packet_has_both_unique_sets(p)]

        checks = {
            "packet_count": len(packets) == len(rels),
            "diverged_count": len(diverged) == spec["distribution"]["DIVERGED"],
            "repo_ahead_count": classes.get("REPO-AHEAD", 0) == spec["distribution"]["REPO-AHEAD"],
            "live_ahead_count": classes.get("LIVE-AHEAD", 0) == spec["distribution"]["LIVE-AHEAD"],
            "both_sets_present": all(packet_has_both_unique_sets(p) for p in diverged),
            "advisory_kind": all(p["recommendation"]["kind"] == "advisory" for p in diverged),
            "never_authorize": all(p["recommendation"]["may_authorize_act"] is False
                                   for p in diverged),
            "hold_action": all(p["recommendation"]["action"] == "HOLD-FOR-RECORDED-DECISION"
                               for p in diverged),
            "unrecorded": all(p["decision"]["status"] == "UNRECORDED" for p in diverged),
            "mtime_recorded": all(p.get("live_mtime") is not None for p in diverged),
            "mtime_not_authorship": all(p.get("mtime_is_authorship_signal") is False
                                        and p.get("size_is_authorship_signal") is False
                                        for p in diverged),
            "git_cited": all("%cI" in p["last_repo_commit"]["git"]["command"]
                             for p in diverged),
        }
        out = {
            "unit_id": "IMP-0036",
            "probe": "probe1-packets",
            "host_present_trees": 1,
            "packets": len(packets),
            "nonempty_one_side": len(nonempty_one_side),
            "both_unique": len(both_unique),
            "DIVERGED": classes.get("DIVERGED", 0),
            "REPO-AHEAD": classes.get("REPO-AHEAD", 0),
            "LIVE-AHEAD": classes.get("LIVE-AHEAD", 0),
            "cited_owner_live_tree": False,
            "checks": checks,
            "pass": all(checks.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print(f"SUCCESS:IMP-0036-probe1 {len(packets)} decision packets")
        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            print(f"FAILED:IMP-0036-probe1 {failed}")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
