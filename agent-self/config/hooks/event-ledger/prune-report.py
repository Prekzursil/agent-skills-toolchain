#!/usr/bin/env python
"""prune-report.py — scan ALL project ledgers and produce a ranked capability-prune report.

Reads events.jsonl for every project under EVENT_LEDGER_ROOT. Tallies tool and skill
invocations recorded as 'tool' fields on 'turn' events (the Stop hook writes these via
stop-hook.py). Produces a ranked table: LEAST-fired (candidate to disable) vs most-fired
(proven value), across the rolling window of all events.

Designed to be RUN MANUALLY (not a hook). Print-only — never disables anything.
Safe with sparse data: when the ledger holds < ~100 tool events (roughly 1 week of data),
prints an advisory instead of a misleading ranking.

Usage:
    python prune-report.py [--min-events N] [--top N] [--window-days N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402

# Minimum event count before we produce a meaningful ranking.
# Below this we say "insufficient data" rather than surface a misleading list.
SPARSE_THRESHOLD = 100
# Default: rank the 10 least-fired and 10 most-fired capabilities.
DEFAULT_TOP = 10


def _collect_all_projects() -> list[Path]:
    """Return all project directories under the ledger root."""
    root = ledger.ROOT
    if not root.exists():
        return []
    return [d for d in root.iterdir() if d.is_dir() and (d / "events.jsonl").exists()]


def _parse_events(events_file: Path, window_cutoff_ts: str | None) -> list[dict]:
    """Parse events from a single project, optionally filtering by timestamp."""
    out = []
    try:
        for line in events_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if window_cutoff_ts and ev.get("ts", "") < window_cutoff_ts:
                continue
            out.append(ev)
    except Exception:
        pass
    return out


def _tool_counts(events: list[dict]) -> tuple[Counter, Counter]:
    """Extract tool/skill FIRES and SUCCESSFUL fires from events.

    The Stop hook records a 'tool' field on 'turn' events when a tool was the last
    action. 'selection' events (Tier-3/OATS) also carry 'chosen_tool'. We harvest
    both, plus any 'skill' field.

    Returns ``(fires, wins)``. An attempt is only evidence of VALUE when it
    SUCCEEDED: hooks/selection-events/emitter.py writes an explicit ``success``
    boolean alongside ``chosen_tool``, and 99 failed attempts must not outrank one
    rare success. Rows that carry no ``success`` field (plain Stop-hook 'turn'
    rows) have no outcome recorded, so they count as wins — treating an unknown
    outcome as a failure would silently zero out every capability the emitter
    does not instrument.
    """
    fires: Counter = Counter()
    wins: Counter = Counter()

    def _tally(name: object, event: dict) -> None:
        if not name:
            return
        key = str(name)
        fires[key] += 1
        if event.get("success", True):
            wins[key] += 1

    for ev in events:
        kind = ev.get("kind", "")
        # turn events from stop-hook may carry last tool used
        if kind == "turn":
            _tally(ev.get("tool") or ev.get("skill"), ev)
        # OATS selection events — these DO carry an explicit outcome
        elif kind == "selection":
            _tally(ev.get("chosen_tool") or ev.get("tool"), ev)
        # note/decision events sometimes tag a tool
        elif kind in ("note", "decision", "milestone"):
            _tally(ev.get("tool") or ev.get("skill"), ev)
    return fires, wins


def _make_cutoff(window_days: int | None) -> str | None:
    """ISO-8601 timestamp for the start of the window (or None = no filter)."""
    if not window_days:
        return None
    cutoff = time.time() - window_days * 86400
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(cutoff))


def report(
    min_events: int = SPARSE_THRESHOLD,
    top: int = DEFAULT_TOP,
    window_days: int | None = None,
) -> str:
    """Build and return the prune report string."""
    dirs = _collect_all_projects()
    if not dirs:
        return (
            "prune-report: EVENT_LEDGER_ROOT is empty or does not exist.\n"
            f"  Root: {ledger.ROOT}\n"
            "  Run some Claude sessions to accumulate data first."
        )

    cutoff = _make_cutoff(window_days)
    all_events: list[dict] = []
    project_event_counts: dict[str, int] = {}
    for d in dirs:
        evs = _parse_events(d / "events.jsonl", cutoff)
        project_event_counts[d.name] = len(evs)
        all_events.extend(evs)

    total = len(all_events)
    # Total tool events — non-turn events without a tool field won't inflate this count.
    tool_counts, tool_wins = _tool_counts(all_events)
    total_tool_events = sum(tool_counts.values())

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("PRUNE REPORT — event-ledger capability usage analysis")
    lines.append("=" * 70)
    lines.append(f"Ledger root      : {ledger.ROOT}")
    lines.append(f"Projects scanned : {len(dirs)}")
    window_label = f"last {window_days}d" if window_days else "all time"
    lines.append(f"Window           : {window_label}")
    lines.append(f"Total events     : {total}")
    lines.append(f"Tool events      : {total_tool_events}")

    if total_tool_events < min_events:
        weeks_needed = max(
            1, round((min_events - total_tool_events) / max(total_tool_events, 1))
        )
        lines.append("")
        lines.append(
            f"INSUFFICIENT DATA — {total_tool_events} tool events recorded; "
            f"need ~{min_events} (~1 week of typical usage)."
        )
        lines.append(
            f"Rough estimate: {weeks_needed} more week(s) of sessions needed "
            "before rankings become meaningful."
        )
        lines.append("No ranking produced. Check back after more sessions.")
        lines.append("=" * 70)
        return "\n".join(lines)

    # Enough data — produce rankings.
    lines.append("")
    lines.append("NOTE: This report is advisory only. It NEVER disables anything.")
    lines.append("      Verify business-value before removing any capability.")
    lines.append("")

    # Rank by SUCCESSFUL fires, never by raw attempts. Attempt frequency is not
    # value: with 99 failed `loop_tool` selections and 1 successful `rare_rescue`,
    # a fire-count ranking recommends KEEPING the tool that never worked and
    # PRUNING the one that did. Ties (and every uninstrumented capability, whose
    # wins == fires) fall back to name for a deterministic order.
    ranked = sorted(tool_counts, key=lambda name: (-tool_wins[name], name))
    most = ranked[:top]
    least = ranked[::-1][:top]

    def _row(name: str, rank: str = "") -> str:
        cnt = tool_counts[name]
        won = tool_wins[name]
        return (
            f"  {rank:>4}  {won:>6}  {cnt:>6}  {100.0 * won / cnt:>7.1f}%  "
            f"{100.0 * cnt / total_tool_events:>9.1f}%  {name}"
        )

    header = (
        f"  {'Rank':>4}  {'Wins':>6}  {'Fires':>6}  {'Win rate':>8}  "
        f"{'% of total':>10}  Capability"
    )

    lines.append(f"{'─' * 70}")
    lines.append(f"LEAST-FIRED — top {top} prune candidates (low observed value)")
    lines.append(f"{'─' * 70}")
    lines.append(header)
    lines.extend(_row(name) for name in least)

    lines.append("")
    lines.append(f"{'─' * 70}")
    lines.append(f"MOST-FIRED — top {top} proven-value capabilities (keep)")
    lines.append(f"{'─' * 70}")
    lines.append(header)
    lines.extend(_row(name) for name in most)

    lines.append("")
    lines.append(f"{'─' * 70}")
    lines.append(
        f"FULL RANKING ({len(tool_counts)} distinct capabilities, sorted by wins desc)"
    )
    lines.append(f"{'─' * 70}")
    lines.append(header)
    lines.extend(_row(name, str(rank)) for rank, name in enumerate(ranked, 1))

    lines.append("")
    lines.append("PER-PROJECT EVENT COUNTS")
    lines.append(f"  {'Events':>8}  Project slug")
    for slug, cnt in sorted(project_event_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {cnt:>8}  {slug}")

    lines.append("=" * 70)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scan event ledgers and print a capability prune report."
    )
    ap.add_argument(
        "--min-events",
        type=int,
        default=SPARSE_THRESHOLD,
        help=f"Minimum tool-event count before producing a ranking (default {SPARSE_THRESHOLD}).",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"How many least/most-fired entries to show (default {DEFAULT_TOP}).",
    )
    ap.add_argument(
        "--window-days",
        type=int,
        default=None,
        help="Restrict analysis to events from the last N days (default: all time).",
    )
    a = ap.parse_args()
    try:
        print(report(min_events=a.min_events, top=a.top, window_days=a.window_days))
    except Exception as exc:
        # fail-open: never crash the caller
        print(f"prune-report: error generating report: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
