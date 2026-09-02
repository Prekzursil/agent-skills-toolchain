#!/usr/bin/env python3
"""Probe 2: live process table vs declared effective state.

The declared map from probe 1 is a claim; this probe is the receipt.
A fixture /proc tree with and without spawned MCP servers must produce
different answers so an always-empty scanner cannot pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import write_proc_fixture  # noqa: E402
from processes import join_declared_and_live, scan_proc  # noqa: E402
from reader import leak_hits  # noqa: E402
from resolver import resolve_estate  # noqa: E402


def main() -> int:
    live_scan = scan_proc(Path("/proc"))
    live = resolve_estate(Path.home(), Path("/opt/p2/ast-integrate"))
    live_join = join_declared_and_live(live.get("servers") or [], live_scan)
    live_blob = json.dumps({"scan": live_scan, "join": live_join}, sort_keys=True)
    if leak_hits(live_blob):
        print("FAILED:AUD-0015-probe2 live process table leaked credential-shaped text")
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0015-p2-") as tmp:
        tmp_path = Path(tmp)
        populated = write_proc_fixture(tmp_path / "with", with_mcp=True)
        empty = write_proc_fixture(tmp_path / "without", with_mcp=False)
        scan_yes = scan_proc(populated)
        scan_no = scan_proc(empty)

    yes_count = scan_yes.get("match_count") or 0
    no_count = scan_no.get("match_count") or 0
    both_states = yes_count != no_count and yes_count >= 1 and no_count == 0

    argv_blob = json.dumps(scan_yes.get("matches") or [], sort_keys=True)
    redacted = "sk-planted-not-real" not in argv_blob
    needles_ok = any(
        m.get("needle") == "@modelcontextprotocol" for m in (scan_yes.get("matches") or [])
    ) and any(
        m.get("needle") == "mcp-server" for m in (scan_yes.get("matches") or [])
    )

    declared_fixture = [
        {
            "name": "filesystem",
            "effective_enabled": True,
            "winning_surface": "~/.mcp.json:mcpServers",
        },
        {
            "name": "github",
            "effective_enabled": True,
            "winning_surface": "~/.mcp.json:mcpServers",
        },
        {
            "name": "memory",
            "effective_enabled": True,
            "winning_surface": "~/.mcp.json:mcpServers",
        },
        {
            "name": "agentbridge",
            "effective_enabled": False,
            "winning_surface": "claude.json:projects[].disabledMcpServers",
        },
    ]
    joined_yes = join_declared_and_live(declared_fixture, scan_yes)
    joined_no = join_declared_and_live(declared_fixture, scan_no)
    splits_yes = {r["name"]: r["split"] for r in joined_yes["rows"]}
    splits_no = {r["name"]: r["split"] for r in joined_no["rows"]}
    split_differs = splits_yes != splits_no
    exposed = splits_yes.get("memory") == "exposed-inactive"
    disabled_quiet = splits_yes.get("agentbridge") == "disabled"
    empty_all_inactive = all(
        r["split"] in {"exposed-inactive", "disabled", "inert-unmatched"}
        for r in joined_no["rows"]
    )

    ok = (
        both_states
        and redacted
        and needles_ok
        and split_differs
        and exposed
        and disabled_quiet
        and empty_all_inactive
        and live_scan.get("status") == "PRESENT"
    )
    result = {
        "unit_id": "AUD-0015",
        "probe": "probe2-process-table",
        "pass": ok,
        "both_states": both_states,
        "fixture_populated_matches": yes_count,
        "fixture_empty_matches": no_count,
        "secret_shaped_argv_redacted": redacted,
        "needles_ok": needles_ok,
        "split_differs_populated_vs_empty": split_differs,
        "populated_splits": splits_yes,
        "empty_splits": splits_no,
        "exposed_inactive_preserved": exposed,
        "disabled_not_collapsed": disabled_quiet,
        "live": {
            "proc_root": live_scan.get("proc_root"),
            "status": live_scan.get("status"),
            "scanned_pids": live_scan.get("scanned_pids"),
            "match_count": live_scan.get("match_count"),
            "names": live_scan.get("names"),
            "declared_server_count": len(live.get("servers") or []),
            "join_rows": live_join.get("rows"),
            "disabled_but_running": live_join.get("disabled_but_running"),
            "exposed_inactive": live_join.get("exposed_inactive"),
            "unmatched_live": live_join.get("unmatched_live_processes"),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:AUD-0015-probe2 process-table both-states")
        return 1
    print(
        "SUCCESS:AUD-0015-probe2 live process table recorded; "
        "populated vs empty /proc fixtures differ; declared-vs-live splits preserved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
