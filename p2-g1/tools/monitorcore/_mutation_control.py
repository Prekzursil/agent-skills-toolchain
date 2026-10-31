"""Both-states control for the health-pane increment.

A passing suite proves nothing unless it GOES RED when the behaviour is broken. Each mutation
below reverts one specific guarantee the new code makes; the named test must fail. A mutation
that survives means the test is decorative.

Restores every file from an in-memory backup in a finally block, then verifies the tree is
byte-identical to where it started.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent / "monitorcore"

# (label, file, old, new, test that MUST fail)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    (
        "unwire the pane from PANES",
        "pane_views.py",
        "    McpPane(),\n    HealthPane(),\n)",
        "    McpPane(),\n)",
        "tests/test_pane_views.py::test_every_registered_source_has_a_pane_that_renders_it",
    ),
    (
        "render the stale banner unconditionally",
        "pane_views.py",
        "    if stale:\n        lines.append(",
        "    if True:\n        lines.append(",
        "tests/test_pane_views.py::test_health_pane_omits_the_stale_row_on_a_fresh_sample",
    ),
    (
        "drop the stale banner entirely",
        "pane_views.py",
        "    if stale:\n        lines.append(",
        "    if False:\n        lines.append(",
        "tests/test_pane_views.py::"
        "test_health_pane_leads_with_an_explicit_stale_row_when_the_feed_is_not_advancing",
    ),
    (
        "let an unsampled GUI counter render as a bare value",
        "pane_views.py",
        'f"gdi_max {measured(p.gdi_max)} · usr_max {measured(p.usr_max)} · "',
        'f"gdi_max {p.gdi_max} · usr_max {p.usr_max} · "',
        "tests/test_pane_views.py::"
        "test_health_pane_never_fabricates_a_zero_for_an_unsampled_gui_counter",
    ),
    (
        "make payload_of trust any payload (the AttributeError hole)",
        "pane.py",
        "    payload = snap.payload\n    if isinstance(payload, of):\n        return payload\n    return None",
        "    return snap.payload",
        "tests/test_pane_views.py::"
        "test_health_pane_says_not_measured_when_the_payload_is_not_a_sentinel_sample",
    ),
    (
        "make snap_is_stale always False",
        "pane.py",
        "    return snap is not None and snap.stale",
        "    return False",
        "tests/test_pane_views.py::"
        "test_health_pane_leads_with_an_explicit_stale_row_when_the_feed_is_not_advancing",
    ),
]


def run(test: str) -> int:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            test,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=PKG.parent,
        capture_output=True,
    ).returncode


def main() -> int:
    backups = {name: (PKG / name).read_bytes() for _, name, _, _, _ in MUTATIONS}
    survivors: list[str] = []
    try:
        for label, name, old, new, test in MUTATIONS:
            path = PKG / name
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(
                    f"ANCHOR-MISS  {label}: {text.count(old)} matches (need exactly 1)"
                )
                survivors.append(f"{label} (anchor miss)")
                continue
            path.write_text(text.replace(old, new), encoding="utf-8")
            code = run(test)
            path.write_bytes(backups[name])
            verdict = "KILLED " if code != 0 else "SURVIVED"
            print(f"{verdict}  {label}  ->  {test.rsplit('::', 1)[1]}")
            if code == 0:
                survivors.append(label)
    finally:
        for name, blob in backups.items():
            (PKG / name).write_bytes(blob)

    for name, blob in backups.items():
        assert (PKG / name).read_bytes() == blob, f"restore failed for {name}"
    print("restore verified: every mutated file is byte-identical to its backup")

    if survivors:
        print(f"FAILED:mutation-control {len(survivors)} survived: {survivors}")
        return 1
    print(
        f"SUCCESS:mutation-control {len(MUTATIONS)}/{len(MUTATIONS)} mutations killed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
