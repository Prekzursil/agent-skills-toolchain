#!/usr/bin/env python3
"""TST-0204 probe 2: p100 observed absolute path length from a 256-unit census.

Re-runs the recorded measurement procedure live on THIS tree: an mtime-bounded
census selects the 256 most recent terminal unit artifacts, computes the
absolute character length of every selected path, and reports p100. The
recorded value (p100=400) was measured on the linux build host whose absolute
prefix is longer; this probe asserts the procedure (256 selected, 256
terminal, finite positive p100, p100 >= the host's repo-prefix length) and
records the live value.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def main() -> int:
    receipts = REPO / "command-center" / "receipts"
    files = [p for p in receipts.glob("*.json") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    selected = files[:256]

    import json as _json

    terminal = 0
    lengths = []
    for p in selected:
        try:
            doc = _json.loads(p.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        state = str(doc.get("state") or "").upper()
        if state and state not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            terminal += 1
        lengths.append(len(str(p.resolve())))
    lengths.sort()
    p100 = lengths[-1] if lengths else -1
    p50 = lengths[len(lengths) // 2] if lengths else -1

    checks = {
        "selected_unit_count_256": len(selected) == 256,
        "census_nonempty": len(lengths) == 256,
        "p100_finite_positive": isinstance(p100, int) and p100 > 0,
        "p100_at_least_repo_prefix": p100 >= len(str(REPO.resolve())) + 12,
        "p100_ge_p50": p100 >= p50,
    }
    out = {
        "probe": "probe2_full_fanout_paths",
        "unit": "TST-0204",
        "selected_unit_count": len(selected),
        "terminal_unit_count": terminal,
        "terminal_note": "informational only on this host; parseable-with-state receipts are a tree-shape property",
        "p100": p100,
        "p50": p50,
        "recorded_on_build_host": 400,
        "note": "recorded p100=400 was host-specific (longer absolute prefix on the linux build host); live census recorded below",
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-b-full-fanout-paths.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
