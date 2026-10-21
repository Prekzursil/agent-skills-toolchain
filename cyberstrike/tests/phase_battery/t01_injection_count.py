#!/usr/bin/env python3
"""T-1 (CRITICAL) injection-count - AGENTS.md must load EXACTLY ONCE.

Defect (audit CS-02): AGENTS.md was injected twice per session - the native
loader (Global.Path.config) PLUS an explicit `{file:...AGENTS.md}` entry in
cyberstrike.json instructions[]. Phase-1 fix2 (b7ab510) removed the duplicate
instructions[] entry. Fixes apply at next TUI start.

Two halves:

  (a) RUNTIME (owner-executed at next TUI start): start the TUI fresh, obtain
      the assembled system prompt of a brand-new session (TUI prompt-dump
      facility, or ask the session to quote its system prompt verbatim into a
      file), save it, then run:
          python tests/phase_battery/t01_injection_count.py --prompt-dump <file>
      The marker (first heading of the live AGENTS.md, derived automatically
      at run time so it survives the Phase-3 switch) must occur EXACTLY ONCE.
      CONTEXT.md (post-switch) likewise exactly once.

  (b) BOTH-STATES CONTROL (runs now, no TUI needed): reconstruct the baseline
      config era via `git show 2c0f3c6:cyberstrike.json` and count AGENTS.md
      LOAD SITES: baseline = native load + instructions[] entry = 2; live =
      native load only = 1. Per the both-states rule, a probe that cannot show
      the broken state measures nothing - this control proves the detector
      would have fired in the baseline era (2x) and is silent now (1x).

Never starts, stops, or touches the TUI (PID 19684 stays untouched).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO,
    BASELINE_REV,
    SUCCESS,
    FAILED,
    PENDING_OWNER,
    VerdictRecorder,
    git_show,
    read_text,
)


def marker_for(agents_md_text: str) -> dict:
    """Derive count-markers from the live AGENTS.md (survives Phase-3 switch).

    Primary: the first ATX heading line (unique per copy of the file).
    Secondary: the posture banner phrase (present in old and new contract).
    """
    first_heading = None
    for line in agents_md_text.splitlines():
        if line.startswith("#"):
            first_heading = line.strip()
            break
    return {
        "primary": first_heading,
        "secondary": "ZERO PERMISSION THEATER",
    }


def load_sites_for_config(config_text: str) -> dict:
    """Count AGENTS.md load sites implied by a cyberstrike.json text.

    Native loader (Global.Path.config) always loads AGENTS.md once - Phase-1
    proved the native load. instructions[] may add a second explicit entry.
    """
    cfg = json.loads(config_text)
    instructions = cfg.get("instructions", [])
    explicit = [i for i in instructions if "AGENTS.md" in i.replace("\\", "/")]
    native = 1
    return {
        "native_load": native,
        "instructions_agents_entry": explicit,
        "total_load_sites": native + len(explicit),
    }


def control(rec: VerdictRecorder) -> str:
    """Both-states control via git-show reconstruction. Returns status."""
    base = load_sites_for_config(git_show(BASELINE_REV, "cyberstrike.json"))
    live_cfg = read_text(REPO / "cyberstrike.json")
    live = load_sites_for_config(live_cfg)

    for name, sites in (("baseline", base), ("live", live)):
        rec.hit("T-1.control", "load_sites", state=name, **sites)
    both = {
        "method": "git-show reconstruction of instructions[] + proven native "
        "loader (Global.Path.config)",
        "baseline_load_sites": base["total_load_sites"],
        "live_load_sites": live["total_load_sites"],
        "control_fires_in_broken_state": base["total_load_sites"] == 2,
        "live_is_single_load": live["total_load_sites"] == 1,
    }
    ok = both["control_fires_in_broken_state"] and both["live_is_single_load"]
    status = SUCCESS if ok else FAILED
    rec.record(
        "T-1.control",
        status,
        details={
            "baseline_rev": BASELINE_REV,
            "note": "static both-states control; runtime half of "
            "T-1 is owner-executed at next TUI start",
        },
        both_states=both,
        anchors=[REPO / "cyberstrike.json"],
        reason=None if ok else "control did not show 2x/1x split",
    )
    return status


def runtime(rec: VerdictRecorder, dump_path: Path) -> str:
    """Owner-executed half: count markers in an assembled-prompt dump."""
    if not dump_path.is_file():
        rec.record("T-1", FAILED, reason="prompt dump not found", anchors=[dump_path])
        return FAILED
    dump = read_text(dump_path)
    agents_text = read_text(REPO / "AGENTS.md")
    markers = marker_for(agents_text)
    primary = markers["primary"] or "CyberStrike TUI"
    p_count = dump.count(primary)
    s_count = dump.count(markers["secondary"])
    context_count = sum(
        1 for ln in dump.splitlines() if ln.strip().startswith("# CONTEXT.md")
    )
    for k, v in (
        ("primary_marker_hits", p_count),
        ("secondary_marker_hits", s_count),
        ("context_md_heading_hits", context_count),
    ):
        rec.hit("T-1", "marker_count", marker=k, count=v)
    ok = p_count == 1 and s_count >= 1 and context_count <= 1
    rec.record(
        "T-1",
        SUCCESS if ok else FAILED,
        details={
            "markers": markers,
            "expected": {"primary": 1, "secondary_min": 1, "context_max": 1},
        },
        anchors=[dump_path, REPO / "AGENTS.md"],
        reason=None if ok else "marker count != 1 (double-load back?)",
    )
    return SUCCESS if ok else FAILED


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    """Battery entrypoint: control now; runtime half marked owner-pending."""
    opts = opts or {}
    control_status = control(rec)
    dump = opts.get("prompt_dump")
    if dump:
        rt = runtime(rec, Path(dump))
        return rt if control_status == SUCCESS else FAILED
    rec.record(
        "T-1",
        PENDING_OWNER,
        reason="runtime half awaits next TUI start (owner-executed)",
        details={
            "protocol": "tests/README.md §T-1; dump the assembled "
            "prompt of a fresh session, then re-run "
            "with --prompt-dump <file>"
        },
        anchors=[REPO / "AGENTS.md"],
    )
    return control_status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--prompt-dump",
        type=Path,
        default=None,
        help="assembled system-prompt dump from a fresh TUI session",
    )
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-1"}) as rec:
        status = run(rec, {"prompt_dump": args.prompt_dump})
        print(f"T-1 {status}")
        return 0 if status in (SUCCESS, PENDING_OWNER) else 1


if __name__ == "__main__":
    sys.exit(main())
