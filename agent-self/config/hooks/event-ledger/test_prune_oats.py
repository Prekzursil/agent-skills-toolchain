#!/usr/bin/env python
"""Self-contained tests for prune-report.py and oats.py.
Uses a temp EVENT_LEDGER_ROOT seeded with synthetic events.
Run: python test_prune_oats.py
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

fails: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def _load_module(alias: str, path: Path):
    """Load a module fresh from a file path (no sys.modules cache)."""
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed_project(ledger_mod, project: str, tool_events: dict[str, int]) -> None:
    """Seed a project with synthetic turn events carrying tool= field."""
    for tool, count in tool_events.items():
        for _ in range(count):
            ledger_mod.append(
                project, "turn", head="abc123", branch="main", dirty_files=0, tool=tool
            )


def main() -> int:
    # One temp root for all prune/oats tests.
    tmp = tempfile.mkdtemp(prefix="prune-oats-test-")
    os.environ["EVENT_LEDGER_ROOT"] = tmp
    sys.path.insert(0, str(HERE))

    # ------------------------------------------------------------------ #
    # Reload ledger so ROOT picks up the new env var                      #
    # ------------------------------------------------------------------ #
    import ledger as _ledger_orig

    ledger = importlib.reload(_ledger_orig)

    # Load prune and oats fresh; they import ledger at module load time,
    # so we do this AFTER setting EVENT_LEDGER_ROOT.
    prune = _load_module("prune_report", HERE / "prune-report.py")
    oats = _load_module("oats", HERE / "oats.py")
    # Ensure both modules' internal ledger also points at our tmp root.
    importlib.reload(prune.ledger)
    importlib.reload(oats.ledger)

    proj_a = os.path.join(tmp, "fake_projA")
    proj_b = os.path.join(tmp, "fake_projB")

    # ------------------------------------------------------------------ #
    # Section 1 — OATS inert (no selection events)                       #
    # ------------------------------------------------------------------ #
    print("== oats: inert with no selection events ==")
    oats_status = oats.status()
    check(
        "oats reports inert when 0 selection events",
        "OATS inert" in oats_status and "0 selection events" in oats_status,
    )
    check("oats inert message mentions >=100 threshold", "100" in oats_status)

    # ------------------------------------------------------------------ #
    # Section 2 — prune-report: sparse data advisory                     #
    # ------------------------------------------------------------------ #
    print("== prune-report: sparse data advisory ==")
    # Seed only 5 events — well below the min_events=100 threshold.
    _seed_project(ledger, proj_a, {"tool_alpha": 3, "tool_beta": 2})
    r_sparse = prune.report(min_events=100)
    check("sparse report says INSUFFICIENT DATA", "INSUFFICIENT DATA" in r_sparse)
    check("sparse report shows 5 tool events", "5 tool events" in r_sparse)
    check(
        "sparse report does NOT produce a ranking table", "LEAST-FIRED" not in r_sparse
    )

    # ------------------------------------------------------------------ #
    # Section 3 — prune-report: sufficient data + correct ranking        #
    # ------------------------------------------------------------------ #
    print("== prune-report: ranking with sufficient synthetic data ==")
    # Totals after this section:
    #   proj_a: alpha=3+57=60, beta=2 (no new), gamma=30  → 92 events
    #   proj_b: beta_new=7, delta=1                        → 8 events
    #   Grand total tool events: 100  ✓ hits min_events=100
    _seed_project(ledger, proj_a, {"tool_alpha": 57, "tool_gamma": 30})
    _seed_project(ledger, proj_b, {"tool_beta_new": 7, "tool_delta": 1})

    # min_events=100 — we have exactly 100 tool events now.
    r_full = prune.report(min_events=100, top=4)
    check("full report says no INSUFFICIENT DATA", "INSUFFICIENT DATA" not in r_full)
    check("full report has LEAST-FIRED section", "LEAST-FIRED" in r_full)
    check("full report has MOST-FIRED section", "MOST-FIRED" in r_full)
    check("full report has FULL RANKING section", "FULL RANKING" in r_full)
    # tool_alpha (60) is most fired
    check("most-fired section contains tool_alpha", "tool_alpha" in r_full)
    # tool_delta (1) is least fired — should be the top prune candidate
    check("least-fired section contains tool_delta", "tool_delta" in r_full)
    # Report must not disable anything
    check(
        "report contains advisory note (never disables)",
        "never disables" in r_full.lower() or "NEVER disables" in r_full,
    )

    # Verify ranking order in the FULL RANKING section:
    # alpha(60) > gamma(30) > beta_new(7) > beta(2) > delta(1)
    full_start = r_full.find("FULL RANKING")
    full_section = r_full[full_start:] if full_start >= 0 else ""
    pos_alpha = full_section.find("tool_alpha")
    pos_gamma = full_section.find("tool_gamma")
    pos_delta = full_section.find("tool_delta")
    check("full ranking: alpha ranked above gamma", 0 <= pos_alpha < pos_gamma)
    check("full ranking: gamma ranked above delta", 0 <= pos_gamma < pos_delta)

    # ------------------------------------------------------------------ #
    # Section 4 — prune-report: per-project event counts section        #
    # ------------------------------------------------------------------ #
    print("== prune-report: per-project event counts section ==")
    check("report includes PER-PROJECT COUNTS section", "PER-PROJECT" in r_full)

    # ------------------------------------------------------------------ #
    # Section 5 — prune-report: empty root advisory                     #
    # ------------------------------------------------------------------ #
    print("== prune-report: empty root advisory ==")
    empty_tmp = tempfile.mkdtemp(prefix="prune-empty-")
    # Load a fresh prune module pointed at the empty root (no global reload
    # needed — just set the env var before the load so ledger.ROOT is right).
    old_root = os.environ.get("EVENT_LEDGER_ROOT")
    os.environ["EVENT_LEDGER_ROOT"] = empty_tmp
    prune_empty = _load_module("prune_report_empty", HERE / "prune-report.py")
    importlib.reload(prune_empty.ledger)
    r_empty = prune_empty.report()
    # Restore
    if old_root is not None:
        os.environ["EVENT_LEDGER_ROOT"] = old_root
    check(
        "empty root gives advisory message (no crash)",
        any(kw in r_empty for kw in ("empty", "does not exist", "INSUFFICIENT DATA")),
    )

    # ------------------------------------------------------------------ #
    # Section 5b — prune-report: OUTCOME, not attempt frequency (D-wu-25) #
    # ------------------------------------------------------------------ #
    print("== prune-report: failed attempts are not proven value ==")
    # 99 FAILED loop_tool selections + 1 SUCCESSFUL rare_rescue selection.
    # Ranking on raw fires calls loop_tool "proven value (keep)" and offers
    # rare_rescue — the only thing that ever worked — as the prune candidate.
    # Written as raw JSONL because "selection" is NOT in ledger.KINDS -- the
    # producer (hooks/selection-events/emitter.py:551-576) detects that and
    # falls back to writing the kind:"selection" line itself, so this IS the
    # real on-disk schema the consumer must read.
    out_tmp = tempfile.mkdtemp(prefix="prune-outcome-")
    out_proj = Path(out_tmp) / "proj_outcome"
    out_proj.mkdir(parents=True, exist_ok=True)
    rows = [{"kind": "selection", "chosen_tool": "loop_tool", "success": False}] * 99
    rows.append({"kind": "selection", "chosen_tool": "rare_rescue", "success": True})
    (out_proj / "events.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    old_root = os.environ.get("EVENT_LEDGER_ROOT")
    os.environ["EVENT_LEDGER_ROOT"] = out_tmp
    prune_out = _load_module("prune_report_outcome", HERE / "prune-report.py")
    importlib.reload(prune_out.ledger)
    r_out = prune_out.report(min_events=100, top=1)
    if old_root is not None:
        os.environ["EVENT_LEDGER_ROOT"] = old_root
    # `ledger` is a SHARED sys.modules entry: the reload above repointed
    # ledger.ROOT globally, so restoring the env var alone would leak this
    # section's selection events into the oats assertions below.
    importlib.reload(prune_out.ledger)

    def _section(text: str, start: str, end: str) -> str:
        i = text.find(start)
        j = text.find(end, i + 1) if i >= 0 else -1
        return text[i:j] if i >= 0 and j > i else ""

    keep = _section(r_out, "MOST-FIRED", "FULL RANKING")
    prune = _section(r_out, "LEAST-FIRED", "MOST-FIRED")
    check("outcome ranking produced (100 events clears the bar)", "MOST-FIRED" in r_out)
    check(
        "99x-failed loop_tool is NOT listed as proven value",
        "loop_tool" not in keep,
    )
    check("the one tool that succeeded is kept", "rare_rescue" in keep)
    check(
        "the only successful tool is NOT the prune candidate",
        "rare_rescue" not in prune,
    )
    check("99x-failed loop_tool IS the prune candidate", "loop_tool" in prune)
    check("report still shows raw attempt counts alongside wins", "Fires" in r_out)

    # ------------------------------------------------------------------ #
    # Section 6 — oats: nudge vector math                                #
    # ------------------------------------------------------------------ #
    print("== oats: nudge vector math ==")
    e = [1.0, 0.0, 0.0]
    q_pos = [[0.0, 1.0, 0.0]]  # mean(Q+) = [0, 1, 0]
    q_neg = [[0.0, 0.0, 1.0]]  # mean(Q-) = [0, 0, 1]
    # ê = (1-0.3)*[1,0,0] + 0.3*[0,1,0] - 0.1*[0,0,1]
    #   = [0.7, 0.0, 0.0] + [0.0, 0.3, 0.0] - [0.0, 0.0, 0.1]
    #   = [0.7, 0.3, -0.1]
    nudged = oats.nudge(e, q_pos, q_neg)
    check("nudge dimension preserved", len(nudged) == 3)
    check(
        "nudge[0] ≈ 0.7 (positive pull reduces base component)",
        abs(nudged[0] - 0.7) < 1e-9,
    )
    check("nudge[1] ≈ 0.3 (positive centroid pulled in)", abs(nudged[1] - 0.3) < 1e-9)
    check(
        "nudge[2] ≈ -0.1 (negative centroid pushed away)",
        abs(nudged[2] - (-0.1)) < 1e-9,
    )

    # Edge: empty negative pool — Q- term dropped, only positive pull.
    nudged_no_neg = oats.nudge(e, q_pos, [])
    check(
        "nudge with empty Q-: dim-2 stays 0.0 (no negative push)",
        abs(nudged_no_neg[2] - 0.0) < 1e-9,
    )
    check(
        "nudge with empty Q-: dim-1 = 0.3 (positive pull present)",
        abs(nudged_no_neg[1] - 0.3) < 1e-9,
    )

    # Edge: both pools empty — returns (1-α)*e.
    nudged_empty = oats.nudge(e, [], [])
    check(
        "nudge with empty pools: dim-0 = (1-α)*1.0",
        abs(nudged_empty[0] - (1 - oats.ALPHA) * 1.0) < 1e-9,
    )
    check("nudge with empty pools: dim-1 = 0.0", abs(nudged_empty[1] - 0.0) < 1e-9)

    # ------------------------------------------------------------------ #
    # Section 7 — oats: rank passthrough (scaffold no-op)               #
    # ------------------------------------------------------------------ #
    print("== oats: rank passthrough (scaffold no-op) ==")
    tools_in = ["tool_x", "tool_y", "tool_z"]
    ranked = oats.rank("some query", tools_in)
    check("rank returns same number of tools", len(ranked) == len(tools_in))
    check("rank result contains the same tools", sorted(ranked) == sorted(tools_in))

    # ------------------------------------------------------------------ #
    # Section 8 — oats: update dry-run scaffold (no selection events)   #
    # ------------------------------------------------------------------ #
    print("== oats: update dry-run scaffold ==")
    update_out = oats.update(dry_run=True)
    check(
        "update with no selection events reports inert",
        "inert" in update_out.lower() or "OATS inert" in update_out,
    )

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    print(
        f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  "
        f"({len(fails)} failures)"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
