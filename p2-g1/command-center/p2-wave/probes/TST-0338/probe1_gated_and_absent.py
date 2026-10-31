#!/usr/bin/env python3
"""TST-0338 probe1: with-file runs command and absent is NOT-CHECKED.

Recomputes, live on this worktree, the receipt fixture_proof blocks
(alpha / beta / ungated / parent trap) and the live-tree gated census.
Exits 0 only when every receipt claim re-verifies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from coverage_resolver import THRESHOLDS_NAME, resolve_project  # noqa: E402

FIXTURES = PROBE_DIR / "fixtures" / "two-project"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0338.json"
SENTINEL = "SUCCESS:TST-0338-probe1"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0338-probe1 {msg}")
    return 1


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    alpha = resolve_project(FIXTURES / "project-alpha")
    beta = resolve_project(FIXTURES / "project-beta")
    ungated = resolve_project(FIXTURES / "project-ungated")

    fp = receipt["fixture_proof"]
    checks = [
        ("alpha.result", alpha["result"] == fp["alpha"]["result"] == "COMMAND-RAN"),
        ("alpha.exit0", alpha["exit_code"] == fp["alpha"]["exit_code"] == 0),
        ("alpha.cmd", alpha["declared_command"] == fp["alpha"]["declared_command"]),
        ("alpha.thresholds", alpha["thresholds"] == fp["alpha"]["thresholds"]),
        ("beta.result", beta["result"] == fp["beta"]["result"] == "COMMAND-RAN"),
        ("beta.exit3", beta["exit_code"] == fp["beta"]["exit_code"] == 3),
        ("beta.cmd", beta["declared_command"] == fp["beta"]["declared_command"]),
        ("beta.thresholds", beta["thresholds"] == fp["beta"]["thresholds"]),
        ("ungated.NOT-CHECKED", ungated["result"] == fp["ungated"]["result"] == "NOT-CHECKED"),
        ("ungated.never-pass", ungated["pass"] is False and fp["ungated"]["pass"] is False),
        ("ungated.never-block", ungated["blocked"] is False and fp["ungated"]["blocked"] is False),
        ("ungated.no-cmd", ungated["declared_command"] is None and fp["ungated"]["declared_command"] is None),
    ]
    trap = json.loads((FIXTURES / THRESHOLDS_NAME).read_text(encoding="utf-8"))
    inherited = ungated["file_exists"] or ungated["declared_command"] is not None
    checks.append(("parent-trap-present", trap.get("$comment", "").startswith("TST0338-PARENT-TRAP-MARKER")))
    checks.append(("parent-trap-not-inherited", inherited is False and fp["parent_trap"]["inherited_by_ungated"] is False))
    checks.append(("trap-not-run", "parent_trap_never_runs" not in json.dumps(ungated)))

    skip_parts = {"__pycache__", ".git", "node_modules", ".venv", "fixtures"}
    live_gated = []
    for path in REPO.rglob(THRESHOLDS_NAME):
        rel = path.relative_to(REPO)
        if any(part in skip_parts for part in rel.parts):
            continue
        live_gated.append(rel.as_posix())
    checks.append(("live-gated-set", live_gated == receipt["inputs"]["coverage_thresholds_files_live_tree"]))
    checks.append(("live-gated-is-metaswarm", live_gated == ["tools/editor/metaswarm/.coverage-thresholds.json"]))
    metaswarm = resolve_project(REPO / "tools" / "editor" / "metaswarm", run=False)
    checks.append(("metaswarm-resolves", metaswarm["declared_command"] == "pnpm test:coverage"))
    checks.append(("metaswarm-not-pass", metaswarm["pass"] is False))
    checks.append(("aggregate-refused-flag", receipt["aggregate_coverage_refused"] is True))
    checks.append(("headline-no-aggregate", receipt["headline"]["coverage"].startswith("NOT-CHECKED per project")))

    for name, ok in checks:
        print(f"  {'ok' if ok else 'RED'} {name}")
        if not ok:
            return fail(f"check {name} RED")
    out = {
        "probe": "probe1-gated-and-absent",
        "unit_id": "TST-0338",
        "pass": True,
        "alpha_exit": alpha["exit_code"],
        "beta_exit": beta["exit_code"],
        "ungated_result": ungated["result"],
        "parent_trap_inherited": inherited,
        "live_gated": live_gated,
    }
    print(json.dumps(out))
    print(SENTINEL + " with-file runs declared command (alpha 0, beta 3); absent emits NOT-CHECKED; parent trap not inherited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
