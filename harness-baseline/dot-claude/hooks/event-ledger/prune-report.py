#!/usr/bin/env python
"""prune-report.py — scan ALL project ledgers and produce a ranked capability-prune report.

Reads events.jsonl for every project under EVENT_LEDGER_ROOT. Tallies tool and skill
invocations recorded as 'tool' fields on 'turn' events (the Stop hook writes these via
stop-hook.py). Produces a ranked table: LEAST-fired (candidate to disable) vs most-fired
(proven value), across the rolling window of all events.

Designed to be RUN MANUALLY (not a hook). Print-only — never disables anything.
Safe with sparse data: when the ledger holds < ~100 tool events (roughly 1 week of data),
prints an advisory instead of a misleading ranking.

ZERO-BLINDNESS (why --installed exists): event observations can only ever name a
capability that fired at least once, so a capability that NEVER fired cannot enter the
tally — yet the bottom of that tally is what gets labelled "prune candidates". Measured
with an installed universe of {frequent-tool, used-once, never-invoked} and a ledger of
100 frequent-tool + 1 used-once events, the observation-only ranking named `used-once` the
top prune candidate and omitted `never-invoked` entirely, while calling its 2-capability
list "FULL". Pass --installed <inventory> to admit the zero-fire capabilities; without it
the ranking is explicitly labelled OBSERVED-ONLY, never "full".

Usage:
    python prune-report.py [--min-events N] [--top N] [--window-days N]
                           [--installed PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Iterable
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


def _tool_counts(events: list[dict]) -> Counter:
    """Extract tool/skill name frequencies from events.

    The Stop hook records a 'tool' field on 'turn' events when a tool was the last
    action. 'selection' events (Tier-3/OATS, future) also carry 'chosen_tool'.
    We harvest both, plus any 'skill' field.
    """
    counts: Counter = Counter()
    for ev in events:
        kind = ev.get("kind", "")
        # turn events from stop-hook may carry last tool used
        if kind == "turn":
            t = ev.get("tool") or ev.get("skill")
            if t:
                counts[str(t)] += 1
        # future OATS selection events
        elif kind == "selection":
            t = ev.get("chosen_tool") or ev.get("tool")
            if t:
                counts[str(t)] += 1
        # note/decision events sometimes tag a tool
        elif kind in ("note", "decision", "milestone"):
            t = ev.get("tool") or ev.get("skill")
            if t:
                counts[str(t)] += 1
    return counts


def _dedupe(names: Iterable[str]) -> list[str]:
    """Strip, drop blanks, and de-duplicate while preserving first-seen order.

    De-duplication is load-bearing: a name repeated in the inventory would otherwise
    inflate the reported "N installed capabilities" count.
    """
    seen: dict[str, None] = {}
    for name in names:
        stripped = name.strip()
        if stripped:
            seen.setdefault(stripped, None)
    return list(seen)


def _installed_names(raw: object) -> list[str]:
    """Normalise a parsed inventory document into a list of capability names.

    Accepted shapes: a JSON list of strings, a JSON object whose KEYS are the
    capability names, or a JSON object with an explicit "capabilities" list.
    """
    if isinstance(raw, dict) and "capabilities" in raw:
        inner = raw["capabilities"]
        if not isinstance(inner, (list, dict)):
            raise ValueError('"capabilities" must be a list or an object')
        raw = inner
    if isinstance(raw, dict):
        raw = list(raw.keys())
    if not isinstance(raw, list):
        raise ValueError(
            "inventory must be a JSON list, or an object of/with capabilities"
        )
    names = _dedupe(str(x) for x in raw)
    if not names:
        raise ValueError("inventory contained no capability names")
    return names


def _load_installed(path: Path) -> list[str]:
    """Read an installed-capability inventory (JSON, or one bare name per line).

    Raises ValueError/OSError on an unusable inventory. The CALLER turns that into a
    failed REPORT, never a silent fallback: silently degrading to the observation-only
    universe is precisely the zero-blind behaviour this argument exists to remove.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith(("[", "{")):
        return _installed_names(json.loads(text))
    lines = [ln.strip() for ln in text.splitlines()]
    return _installed_names(
        [ln for ln in lines if ln and not ln.startswith("#")],
    )


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
    installed: Path | str | list[str] | None = None,
) -> str:
    """Build and return the prune report string.

    `installed` is the INSTALLED-capability inventory (a path to a JSON/text file, or an
    explicit list of names). Every name in it enters the ranking, at 0 fires if it never
    appeared in an event — which is what makes never-fired capabilities visible as prune
    candidates. Omitting it keeps the old observation-only universe, which is then
    labelled OBSERVED-ONLY rather than "full".
    """
    installed_names: list[str] = []
    if installed is not None:
        if isinstance(installed, (str, Path)):
            try:
                installed_names = _load_installed(Path(installed))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return (
                    "prune-report: FAILED — installed-capability inventory is unusable, "
                    "so never-fired capabilities could not be enumerated.\n"
                    f"  Inventory: {installed}\n"
                    f"  Reason   : {exc}\n"
                    "  No ranking produced (an observation-only ranking would silently "
                    "omit every zero-fire capability)."
                )
        else:
            installed_names = _dedupe(str(x) for x in installed)

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
    tool_counts = _tool_counts(all_events)
    total_tool_events = sum(tool_counts.values())
    # Admit the installed-but-never-observed capabilities at 0 fires. Done AFTER
    # total_tool_events so the zeros cannot change any percentage; `most_common()` puts
    # them at the bottom, i.e. ahead of every once-used capability as a prune candidate.
    never_fired = [n for n in installed_names if not tool_counts[n]]
    # Observed but NOT in the inventory => the inventory itself is incomplete/stale.
    # Reported, because an inventory-derived universe that silently drops observed
    # capabilities would be a second blindness of the same shape.
    installed_set = set(installed_names)
    absent_from_inventory = [n for n in tool_counts if n not in installed_set]
    for name in installed_names:
        tool_counts.setdefault(name, 0)

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
    if installed_names:
        lines.append(
            f"UNIVERSE: {len(installed_names)} installed capabilities from the "
            f"inventory; {len(never_fired)} of them NEVER fired (shown at 0 fires)."
        )
        if absent_from_inventory:
            lines.append(
                f"          {len(absent_from_inventory)} capabilities fired but are "
                "ABSENT from the inventory — it is incomplete or stale."
            )
    else:
        lines.append(
            "WARNING: no --installed inventory given, so this ranking covers ONLY "
            "capabilities that fired at least once."
        )
        lines.append(
            "         A never-fired capability CANNOT appear below, so the bottom entry "
            "is the least-used OBSERVED one — not necessarily the best prune candidate."
        )
    lines.append("")

    # Least-fired: prime prune candidates.
    least = tool_counts.most_common()[: -(top + 1) : -1]  # bottom N
    most = tool_counts.most_common(top)

    lines.append(f"{'─' * 70}")
    lines.append(f"LEAST-FIRED — top {top} prune candidates (low observed value)")
    lines.append(f"{'─' * 70}")
    lines.append(f"  {'Fires':>8}  {'% of total':>10}  Capability")
    for name, cnt in least:
        pct = 100.0 * cnt / total_tool_events
        lines.append(f"  {cnt:>8}  {pct:>9.1f}%  {name}")

    lines.append("")
    lines.append(f"{'─' * 70}")
    lines.append(f"MOST-FIRED — top {top} proven-value capabilities (keep)")
    lines.append(f"{'─' * 70}")
    lines.append(f"  {'Fires':>8}  {'% of total':>10}  Capability")
    for name, cnt in most:
        pct = 100.0 * cnt / total_tool_events
        lines.append(f"  {cnt:>8}  {pct:>9.1f}%  {name}")

    lines.append("")
    lines.append(f"{'─' * 70}")
    if installed_names:
        lines.append(
            f"FULL RANKING ({len(tool_counts)} capabilities = "
            f"{len(installed_names)} installed + {len(absent_from_inventory)} "
            "observed-only, sorted by fires desc)"
        )
    else:
        lines.append(
            f"OBSERVED-ONLY RANKING ({len(tool_counts)} capabilities seen firing; "
            "the installed universe is UNKNOWN here — pass --installed)"
        )
    lines.append(f"{'─' * 70}")
    lines.append(f"  {'Rank':>4}  {'Fires':>8}  {'% of total':>10}  Capability")
    for rank, (name, cnt) in enumerate(tool_counts.most_common(), 1):
        pct = 100.0 * cnt / total_tool_events
        lines.append(f"  {rank:>4}  {cnt:>8}  {pct:>9.1f}%  {name}")

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
    ap.add_argument(
        "--installed",
        default=None,
        metavar="PATH",
        help=(
            "Installed-capability inventory: a JSON list, a JSON object keyed by "
            "capability name, an object with a 'capabilities' list, or a plain text "
            "file with one name per line ('#' comments allowed). Names absent from the "
            "ledger are ranked at 0 fires. Without this the ranking is OBSERVED-ONLY "
            "and cannot name a never-fired capability."
        ),
    )
    a = ap.parse_args()
    try:
        print(
            report(
                min_events=a.min_events,
                top=a.top,
                window_days=a.window_days,
                installed=a.installed,
            )
        )
    except Exception as exc:
        # fail-open: never crash the caller
        print(f"prune-report: error generating report: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
