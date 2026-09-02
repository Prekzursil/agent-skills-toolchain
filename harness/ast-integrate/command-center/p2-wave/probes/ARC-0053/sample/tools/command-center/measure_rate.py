"""Measure the register gate's firing rate by replaying a real prompt corpus.

A gate that fires too often becomes wallpaper. That is not a hypothetical on
this estate: `module-modes.json:32` holds `ipass_readback` in shadow with the
verbatim reason *"971 fires / 51 sessions = 19.0 per session. Would become
wallpaper on promotion; a gate that fires 19x a session trains the reader to
ignore it, which is worse than silence."*

So the rate is MEASURED, not estimated, and it is measured by running the
module's OWN predicate (`RegisterGateModule.would_fire`) rather than a
re-implementation of it -- a paraphrased predicate would measure a gate that
does not ship.

The corpus lives outside the repository (it is raw owner prompts), so this is an
operator tool, not a CI step. What CI can check -- the selectivity ceiling, the
per-session cooldown, the cap -- is asserted in
`agent-self/harness/tests/test_register_gate.py`.

Usage:
    python tools/command-center/measure_rate.py --corpus <path to _USER-PROMPTS.md>
    python tools/command-center/measure_rate.py --corpus <path> --clean   # control
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-self"))

import catalog as cat
from harness.modules import RegisterGateModule

# `^### line N (M chars)` with COMMA-GROUPED numbers. Without the commas the
# pattern matches 6 of 375 headers and silently drops every long prompt -- which
# is exactly the population most likely to fire. Measured on this corpus:
# comma-aware 375, comma-blind 6.
_HEADER = re.compile(r"^### line [\d,]+ \([\d,]+ chars\)\s*$")


def split_prompts(text: str) -> list[str]:
    """Split on the structural header only.

    USE-VS-MENTION: this corpus contains 290 further `### ` lines that are
    markdown *inside* prompt bodies. Matching the bare token would shatter long
    prompts into fragments and inflate the denominator."""
    prompts: list[str] = []
    current: list[str] = []
    started = False
    for line in text.splitlines():
        if _HEADER.match(line):
            if started:
                prompts.append("\n".join(current))
            current = []
            started = True
            continue
        if started:
            current.append(line)
    if started:
        prompts.append("\n".join(current))
    return prompts


def measure(prompts: list[str], items: list[dict]) -> dict:
    gate = RegisterGateModule()
    fired = 0
    long_fired = 0
    long_total = 0
    program_only = 0
    histogram: dict[int, int] = {}
    for prompt in prompts:
        matched, programs = gate.would_fire(prompt, items)
        is_long = len(prompt) >= 4000
        long_total += is_long
        hit = bool(matched)
        if not matched and programs and items:
            # Counted for diagnosis only. The shipped module does NOT fire here:
            # measuring a program-level fallback it does not have would measure a
            # different gate. Removing that fallback was decided BY this number
            # (37 of 97 fires, 42 of them from the single token "harness").
            program_only += 1
        fired += hit
        long_fired += hit and is_long
        histogram[len(matched)] = histogram.get(len(matched), 0) + 1
    total = len(prompts) or 1
    rate = fired / total
    return {
        "prompts": len(prompts),
        "open_items": len(items),
        "fired": fired,
        "fire_pct": round(100.0 * rate, 2),
        "program_level_only": program_only,
        "long_prompts": long_total,
        "long_fired": long_fired,
        "per_session_at_10": round(rate * 10, 2),
        "per_session_at_20": round(rate * 20, 2),
        "per_session_at_40": round(rate * 40, 2),
        "matches_histogram": dict(sorted(histogram.items())),
    }


def measure_sessions(prompts: list[str], items: list[dict], size: int) -> dict:
    """Replay the corpus as consecutive sessions WITH the shipped cooldown.

    This is the number that matters. `measure()` above counts a fire per
    matching prompt, which is a gross overestimate of the shipped gate: an item
    id is surfaced at most ONCE per session, so a session that keeps discussing
    the monitor cockpit produces one notice, not fifteen. Reporting the uncapped
    figure as the operating point would be measuring a gate that does not exist
    -- and reporting the capped one without saying so would hide the assumption,
    so both are printed.

    Measured 2026-08-09 on the 375-prompt corpus against the real catalog:
    stale 3.16/session, clean 0.00/session, clean-MONITOR 2.58/session."""
    gate = RegisterGateModule()
    per_session: list[int] = []
    for start in range(0, len(prompts), size):
        seen: set[str] = set()
        fires = 0
        for prompt in prompts[start : start + size]:
            matched, programs = gate.would_fire(prompt, items)
            del programs  # the shipped module has NO program-level prompt fire
            fresh = [item_id for item_id in matched if item_id not in seen]
            if fresh:
                seen.update(fresh)
                fires += 1
        per_session.append(fires)
    sessions = len(per_session) or 1
    return {
        "session_size": size,
        "sessions": len(per_session),
        "total_fires": sum(per_session),
        "mean_fires_per_session": round(sum(per_session) / sessions, 2),
        "max_fires_in_a_session": max(per_session) if per_session else 0,
        "sessions_with_zero_fires": sum(1 for count in per_session if count == 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--session-size", type=int, default=20)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="control run: close every open item first; a correct gate fires ZERO times",
    )
    parser.add_argument(
        "--clean-program",
        default=None,
        help="control run: close only this program's items; the gate must go silent for it alone",
    )
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_file():
        print(f"FAILED:cc-rate corpus not found: {corpus}")
        return 1
    prompts = split_prompts(corpus.read_text(encoding="utf-8", errors="replace"))
    if not prompts:
        print(
            "FAILED:cc-rate corpus split produced zero prompts (detector failure, not a result)"
        )
        return 1

    catalog = cat.load(args.catalog) if args.catalog else cat.load()
    items = [item for item in cat.items(catalog) if not item.get("disposition")]
    if args.clean:
        items = []
    elif args.clean_program:
        items = [item for item in items if item.get("program") != args.clean_program]

    report = measure(prompts, items)
    report["mode"] = (
        "clean"
        if args.clean
        else (f"clean-{args.clean_program}" if args.clean_program else "stale")
    )
    report["uncapped_note"] = (
        "fire_pct and per_session_at_N ignore the per-item and per-program session "
        "cooldown, so they are an UPPER bound. `with_cooldown` is the shipped behaviour."
    )
    report["with_cooldown"] = measure_sessions(prompts, items, args.session_size)
    print(json.dumps(report, indent=2))
    print(
        f"SUCCESS:cc-rate uncapped={report['fire_pct']}% "
        f"shipped={report['with_cooldown']['mean_fires_per_session']}/session"
        f"@{args.session_size}prompts"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
