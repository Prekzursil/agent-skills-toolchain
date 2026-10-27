#!/usr/bin/env python
"""mcp_health — per-server MCP health report (READ-ONLY, spawns nothing).

Reports, for every configured MCP server: where it is configured, whether it is
currently reachable AND BY WHAT GRADE OF EVIDENCE, its historical failure rate
from the session corpus, and a KEEP / FIX / RETIRE verdict with the evidence the
verdict rests on.

Usage:
  uv run mcp_health.py                    # table, loopback probes only
  uv run mcp_health.py --json             # machine-readable
  uv run mcp_health.py --allow-remote     # also TCP-probe remote http/sse hosts
  uv run mcp_health.py --corpus PATH      # point at a different corpus.json
  uv run mcp_health.py --verdict retire   # filter to one verdict

Evidence grades, weakest to strongest — never conflate them:
  not_probed  nothing was measured
  command     the stdio command resolves to a real file (says NOTHING about
              whether the server starts, speaks MCP, or has credentials)
  endpoint    a bounded TCP connection to the http/sse endpoint completed
  handshake   an MCP initialize round-trip succeeded  [NOT IMPLEMENTED]

`handshake` is deliberately absent: obtaining it means starting every configured
server, and this box has ~1.5 GB free. A health check that causes an outage is
not a health check. Use `claude mcp list` when you explicitly want that cost.

This tool never writes config and never disables anything. It reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.health import Verdict, build_report  # noqa: E402

_DEFAULT_CORPUS = (
    Path.home() / ".claude" / "harness-sota-2026-07-18" / "corpus" / "corpus.json"
)


def _fmt_rate(rate: float | None) -> str:
    """None renders as '--', never as '0.0%'.

    A server with no corpus row has no measured rate. Printing 0.0% would read
    as a perfect record and is the exact false-absence bug this tool exists to
    avoid making.
    """
    return "--" if rate is None else f"{rate:.1%}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp_health", description=__doc__)
    _ = parser.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    _ = parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="also TCP-probe non-loopback http/sse hosts (network egress)",
    )
    _ = parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    _ = parser.add_argument("--home", type=Path, default=Path.home())
    _ = parser.add_argument(
        "--from-mcp-list",
        type=Path,
        metavar="FILE",
        help=(
            "a saved `claude mcp list` dump. Upgrades those rows to HANDSHAKE "
            "grade and reveals plugin/remote servers that no local config file "
            "exposes. Produce it with: claude mcp list > mcp-list.txt"
        ),
    )
    _ = parser.add_argument(
        "--verdict",
        choices=[v.value for v in Verdict],
        help="show only rows with this verdict",
    )
    args = parser.parse_args(argv)

    corpus: Path = args.corpus
    dump: Path | None = args.from_mcp_list
    rows = build_report(
        home=args.home,
        corpus_path=corpus,
        allow_remote=args.allow_remote,
        mcp_list_output=dump.read_text(encoding="utf-8", errors="replace")
        if dump
        else None,
    )
    if args.verdict:
        rows = [r for r in rows if r.verdict.value == args.verdict]

    if args.json:
        print(json.dumps([r.to_dict() for r in rows], indent=2))
        return 0

    if not corpus.is_file():
        print(
            f"WARNING: corpus not found at {corpus} — every history column reads '--'"
        )
        print("         that is ABSENCE OF EVIDENCE, not a clean record.\n")

    # DEAD% and ANSERR% are the two ORTHOGONAL failure axes and need different
    # repairs; their sum (a plain error rate) hides which one is broken.
    print(
        f"{'SERVER':26} {'VERDICT':22} {'REACH':12} {'GRADE':11} "
        f"{'CALLS':>7} {'DEAD':>6} {'DEAD%':>7} {'ANSERR%':>8}  CONFIGURED-IN"
    )
    print("-" * 138)
    for row in rows:
        print(
            f"{row.id[:26]:26} {row.verdict.value:22} {row.reach.reach.value:12} "
            f"{row.rests_on.value:11} {row.history.calls:>7} "
            f"{row.history.not_connected:>6} {_fmt_rate(row.history.dead_rate):>7} "
            f"{_fmt_rate(row.history.answered_error_rate):>8}  "
            f"{', '.join(row.configured_in) or '(not in local config)'}"
        )

    actionable = [r for r in rows if r.verdict is not Verdict.KEEP]
    if actionable:
        print("\nEVIDENCE for every non-KEEP verdict:")
        for row in actionable:
            print(f"\n  {row.id}  ->  {row.verdict.value.upper()}")
            for line in row.evidence:
                print(f"    - {line}")

    print(
        "\nNOTE: corpus counts are LOWER BOUNDS (the corpus caps its own lists), and "
        "'--' means\n      no row was found — absence of evidence, not evidence of "
        "health."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
