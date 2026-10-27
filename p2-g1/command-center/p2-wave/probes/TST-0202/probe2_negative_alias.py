#!/usr/bin/env python3
"""TST-0202 probe 2: negative control - the alias-measuring writer is the defect.

write_measuring_alias applies the budget to the SHORT junction alias and
therefore ADMITS a write whose resolved path exceeds WINDOWS_MAX_PATH, while
the production write_artifact refuses the same alias with zero residue.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import build, teardown  # noqa: E402


def main() -> int:
    info = build()
    from artifact_writer import (  # noqa: E402
        PathBudgetExceeded,
        write_artifact,
        write_measuring_alias,
    )

    alias_target_file = info["alias"] / "through-alias.bin"

    production_refused = None
    prod_residue = -1
    prod_measured = -1
    prod_measure = ""
    try:
        write_artifact(alias_target_file, b"x")
        production_refused = False
    except PathBudgetExceeded as exc:
        production_refused = True
        prod_residue = int(exc.check["residue_bytes"])
        prod_measured = int(exc.check["measured_length"])
        prod_measure = str(exc.check["measure"])

    alias_admitted = None
    alias_check = {}
    try:
        alias_check = write_measuring_alias(alias_target_file, b"defect-admits-over-limit")
        alias_admitted = True
    except PathBudgetExceeded:
        alias_admitted = False

    resolved_after = Path(alias_target_file).resolve() if alias_admitted else None
    residue_on_resolved = int(resolved_after.stat().st_size) if resolved_after is not None and resolved_after.is_file() else 0


    checks = {
        "alias_writer_admits_over_limit": alias_admitted is True and alias_check.get("measure") == "alias",
        "residue_lands_on_over_budget_resolved": residue_on_resolved > 0 and info["over_budget"] is True,
        "production_writer_refuses_alias": production_refused is True,
        "production_measures_resolved": prod_measure == "resolved" and prod_measured > alias_check.get("measured_length", 0),
        "production_zero_residue": prod_residue == 0,
    }
    out = {
        "probe": "probe2_negative_alias",
        "unit": "TST-0202",
        "alias_len": info["alias_len"],
        "resolved_len": info["resolved_len"],
        "over_budget": info["over_budget"],
        "alias_writer_check": alias_check,
        "production_refused": production_refused,
        "production_measured": prod_measured if production_refused else None,
        "residue_on_resolved": residue_on_resolved,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_negative_alias.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    teardown()
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
