"""P13 Q03: turn the Linux full-suite run into a structured artifact.

Source data: command-center/p13_linux_fails.txt, produced by
  wsl python3 -m pytest platform -q -p no:cacheprovider
on Ubuntu 24.04 / python 3.12.3, exported verbatim from /tmp.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
SRC = CC / "p13_linux_fails.txt"
OUT = CC / "P13-LINUX-SUITE.json"

ROOT_CAUSE_EXEMPT = [
    "platform/coordination/test_docs.py::test_every_resolution_source_anchor_points_at_a_real_file",
    "platform/coordination/test_leases.py::test_backslash_and_case_fold_on_windows",
    "platform/routing/test_descriptions.py::test_corpus_stats_reports_a_real_length_distribution",
]


def main() -> int:
    raw = SRC.read_text(encoding="utf-8", errors="replace")
    fails = [
        line.split(" ", 1)[1].strip()
        for line in raw.splitlines()
        if line.startswith("FAILED platform")
    ]
    summary_line = next(
        (line.strip() for line in reversed(raw.splitlines()) if "passed" in line),
        "UNAVAILABLE",
    )
    m = re.search(
        r"(\d+) failed, (\d+) passed, (\d+) skipped in ([\d.]+)s", summary_line
    )
    if not m:
        print(f"FAILED:p13-linux-report cannot parse summary line: {summary_line!r}")
        return 1
    failed, passed, skipped, secs = int(m[1]), int(m[2]), int(m[3]), float(m[4])

    if len(fails) != failed:
        print(
            f"FAILED:p13-linux-report self-contradiction - summary says {failed} failed "
            f"but {len(fails)} FAILED lines were parsed. A detector that disagrees with "
            f"itself is a detector failure, not a finding."
        )
        return 1
    print(
        f"consistency check PASS: {failed} failed in summary == {len(fails)} FAILED lines"
    )

    by_pkg = collections.Counter(f.split("::")[0].rsplit("/", 1)[0] for f in fails)
    routing = [f for f in fails if f.startswith("platform/routing/")]
    attributed = [f for f in routing if f not in ROOT_CAUSE_EXEMPT]

    report = {
        "artifact": "P13-LINUX-SUITE",
        "unit": "depth/p13-blindspot",
        "status": "MEASURED",
        "question": "Q03 what platforms were never tested - measured on Linux, not asserted",
        "environment": {
            "os": "Ubuntu 24.04 (WSL2)",
            "python": "3.12.3 (GCC 13.3.0)",
            "pytest": "8.3.3",
            "jsonschema": "4.25.1",
            "repo_path": "/mnt/c/Users/Prekzursil/source/ast-integrate",
            "home": "/home/prekzursil",
            "command": "python3 -m pytest platform -q -p no:cacheprovider",
        },
        "summary_line": summary_line,
        "summary": {
            "failed": failed,
            "passed": passed,
            "skipped": skipped,
            "seconds": secs,
            "exit_code": 1,
            "collected": failed + passed + skipped,
        },
        "windows_baseline_for_comparison": {
            "failed": 0,
            "passed": 3847,
            "skipped": 14,
            "collected": 3861,
            "note": "carried figure from the pinned baseline; NOT re-run by this unit",
        },
        "deltas": {
            "failures_linux_minus_windows": failed,
            "skips_linux_minus_windows": skipped - 14,
            "collected_delta": (failed + passed + skipped) - 3861,
            "collected_delta_note": (
                "UNVERIFIED: more tests collected on Linux than the Windows baseline "
                "reports; parametrisation over discovered files is the likely driver but "
                "the cause was not investigated. Settling experiment: "
                "pytest --collect-only -q on both platforms and diff the node id lists."
            ),
        },
        "failures": fails,
        "failures_by_package": dict(by_pkg.most_common()),
        "root_cause": {
            "verdict": f"CONFIRMED for {len(attributed)} of {failed} failures (all in platform/routing)",
            "mechanism": (
                "platform/routing/index.py:55 sets "
                "HOME = Path(os.environ.get('ROUTING_HOME') or Path.home()), and "
                "index.py:93-97 binds skills/agents/commands under that HOME. The "
                "capability corpus under test is therefore the OPERATOR's LIVE ~/.claude "
                "harness, not a committed fixture."
            ),
            "measurement": (
                "Windows ~/.claude: agents=27 commands=71 skills=79. "
                "Linux ~/.claude: agents=0 commands=0 skills=0. Linux indexed 383 records; "
                "the test's own positive-form guard asserts >800 and fired: "
                "'corpus implausibly small (383); the walk is probably broken'."
            ),
            "consequence": (
                "The Phase 8 capability count and every derived precision/recall and "
                "bytes-per-query figure are machine-specific and not reproducible in CI or "
                "on any other host. This also structurally explains the missing platform/ "
                "CI lane: these tests cannot pass on a runner with no ~/.claude harness, so "
                "the absence of CI is forced by the design rather than merely forgotten."
            ),
            "credit_where_due": (
                "The tests are well designed: they assert the POSITIVE form (N of N, plus an "
                "explicit implausibly-small floor) which is exactly why the coupling surfaced "
                "instead of passing vacuously."
            ),
            "available_fix_seam": (
                "ROUTING_HOME already exists at index.py:55 and no test sets it. Pointing it "
                "at a committed fixture corpus would make the lane hermetic (ci-hygiene.md 2) "
                "and unblock a platform/ CI lane."
            ),
        },
        "not_attributed_to_that_root_cause": ROOT_CAUSE_EXEMPT,
        "control": {
            "probe": "python3 -m pytest platform/plugin -q on the SAME Linux interpreter",
            "result": "252 passed in 118.98s",
            "meaning": (
                "a disjoint subpackage passes cleanly, so the 24 failures are localised - "
                "a blanket 'the build breaks on Linux' claim is REFUTED"
            ),
        },
        "scope_limits": [
            "the 3 non-routing failures were not individually triaged",
            "no macOS run was attempted - no macOS host exists on this estate",
            "the Windows baseline was carried, not re-measured by this unit",
            "run over /mnt/c (Windows filesystem) so wall-clock is not a fair perf comparison",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"failed={failed} passed={passed} skipped={skipped} (windows: 0/3847/14)")
    print("by package:")
    for k, v in by_pkg.most_common():
        print(f"  {v:3d}  {k}")
    print(f"SUCCESS:p13-linux-report wrote {OUT} ({OUT.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
