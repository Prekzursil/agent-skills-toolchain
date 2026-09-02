#!/usr/bin/env python3
"""Probe 1: hand-edit of a generated table goes red; regeneration is byte-identical."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import report as R  # noqa: E402

LEDGER = REPO / "command-center" / "bench" / "results" / "runs.jsonl"
INDEX = REPO / "command-center" / "bench" / "report-index.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0310-probe1 {msg}")
    return 1


def main() -> int:
    identical, first, second = R.two_run_identical(LEDGER)
    if not identical:
        keys = [k for k in first if first.get(k) != second.get(k)]
        return fail(f"two render_all() passes differed files={keys}")
    print(f"idempotent_render files={sorted(first)} identical=True")

    with tempfile.TemporaryDirectory(prefix="tst0310-p1-") as tmp:
        published = Path(tmp) / "published"
        files = R.generate(LEDGER, published)
        clean = R.check(LEDGER, published, INDEX)
        if not clean.ok:
            return fail(f"fresh generate was not green {clean.as_dict()}")
        print(
            f"clean_gate ok=True figures_checked={clean.figures_checked} "
            f"unresolved={clean.figures_unresolved} drift={clean.drift_files}"
        )

        target = published / "leaderboard.md"
        original = target.read_text(encoding="utf-8")
        if "0.940" not in original:
            return fail("expected fused accuracy 0.940 in generated leaderboard.md")
        mutated = original.replace("0.940", "0.941", 1)
        if mutated == original:
            return fail("mutation did not change leaderboard.md")
        target.write_text(mutated, encoding="utf-8", newline="\n")
        red = R.check(LEDGER, published, INDEX)
        if red.ok:
            return fail("hand-edit of 0.940 -> 0.941 left the gate green")
        if "leaderboard.md" not in red.drift_files:
            return fail(f"expected leaderboard.md drift, got {red.drift_files} reasons={red.reasons}")
        print(
            f"hand_edit_gate ok=False drift={red.drift_files} "
            f"reasons={red.reasons}"
        )

        # Restore by regenerating; must match the first in-memory bytes.
        restored = R.generate(LEDGER, published)
        if restored["leaderboard.md"] != files["leaderboard.md"]:
            return fail("regeneration after edit did not restore original leaderboard.md")
        after = R.check(LEDGER, published, INDEX)
        if not after.ok:
            return fail(f"regeneration did not return to green {after.as_dict()}")

    payload = {
        "idempotent_render": True,
        "clean_gate_ok": True,
        "hand_edit_went_red": True,
        "hand_edit_named_file": "leaderboard.md",
        "regeneration_restored": True,
        "figures_checked_clean": clean.figures_checked,
        "figures_unresolved_clean": clean.figures_unresolved,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0310-probe1 hand-edit red, regeneration identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
