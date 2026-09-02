"""Named probe 1: presence matrix over the live catalog + CI-shaped mutation.

Measures:
1. Per-field per-unit presence for items (103) and work_units (2007).
2. Historical validate.py silence: --no-require-complete still exits 0 after
   deleting the entire defaults block (the measured CI hole).
3. This unit's checker, invoked BARE, rejects a catalog whose mandated fields
   exist only in defaults — even while those defaults remain in the file.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import vfields_ci as vci  # noqa: E402
import work_unit_conformance as wuc  # noqa: E402

UNIT = "TST-0038"
DEFAULT_ONLY_EXPECTED = frozenset(
    {
        "assignment",
        "tool_permissions",
        "execution_substrate",
        "timeout_seconds",
        "output_schema",
        "evidence_requirement",
        "tests_required",
        "reviewer_requirement",
        "retry_policy",
        "failure_classification",
        "owner_approval_required",
    }
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    catalog = cat.load()
    matrix = wuc.presence_matrix(catalog)
    if matrix["n_fields"] != 19:
        return fail(f"expected 19 fields, got {matrix['n_fields']}")
    if set(matrix["fields"]) != set(cat.WORK_UNIT_FIELDS):
        return fail("matrix fields != catalog.WORK_UNIT_FIELDS")

    items = matrix["collections"].get("items") or {}
    work_units = matrix["collections"].get("work_units") or {}
    if items.get("n") != 103:
        return fail(f"items n={items.get('n')} want 103")
    if work_units.get("n", 0) < 2000:
        return fail(f"work_units n={work_units.get('n')} want >=2000")

    item_default_only = []
    for field, row in items["per_field"].items():
        if row["on_unit"] == 0 and row["defaults"] == items["n"]:
            item_default_only.append(field)
    if set(item_default_only) != DEFAULT_ONLY_EXPECTED:
        return fail(
            f"items defaults-only fields {sorted(item_default_only)} "
            f"!= {sorted(DEFAULT_ONLY_EXPECTED)}"
        )

    for field, row in work_units["per_field"].items():
        if row["on_unit"] != work_units["n"]:
            return fail(f"work_units {field} on_unit={row['on_unit']} / {work_units['n']}")

    live_item_violations = wuc.check_catalog(
        catalog,
        require_complete=True,
        enforce_enums=False,
        collections=("items",),
    )
    live_default_fields = {
        row["field"]
        for row in live_item_violations
        if row["rule"] == "R-DEFAULTS-NOT-COMPLETE"
    }
    if live_default_fields != DEFAULT_ONLY_EXPECTED:
        return fail(f"live checker defaults-only {sorted(live_default_fields)}")
    if len(live_item_violations) != 103 * 11:
        return fail(f"live item violations {len(live_item_violations)} want {103 * 11}")

    good = wuc.conforming_catalog()
    if wuc.check_catalog(good, require_complete=True, enforce_enums=True):
        return fail(f"conforming fixture was not silent: {wuc.check_catalog(good)}")

    bad = wuc.defaults_only_catalog()
    bad_v = wuc.check_catalog(bad, require_complete=True, enforce_enums=True)
    bad_fields = {row["field"] for row in bad_v}
    if bad_fields != DEFAULT_ONLY_EXPECTED:
        return fail(f"defaults-only fixture fields {sorted(bad_fields)}")

    with tempfile.TemporaryDirectory(prefix="tst0038-p1-") as raw:
        tmp = Path(raw)
        (tmp / "good.json").write_text(
            json.dumps(good, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (tmp / "bad.json").write_text(
            json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        rc_good = wuc.main(["--catalog", str(tmp / "good.json"), "--items-only"])
        rc_bad = wuc.main(["--catalog", str(tmp / "bad.json"), "--items-only"])
        if rc_good != 0:
            return fail(f"bare checker rejected conforming catalog rc={rc_good}")
        if rc_bad == 0:
            return fail("bare checker accepted defaults-only catalog")

        dropped = vci.write_sandbox(tmp / "dropped", vci.mini_catalog(), drop_defaults=True)
        historical = vci.run_validate(dropped, [vci.DISARM_FLAG])
        if historical["exit_code"] != 0 or historical["vfields"]:
            return fail(
                "historical --no-require-complete did not stay silent after "
                f"defaults deletion: exit={historical['exit_code']} "
                f"out={historical['output'][-600:]}"
            )

    out_dir = Path(__file__).resolve().parent
    (out_dir / "presence-matrix.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    payload = {
        "probe": "probe1-presence-and-mutation",
        "unit_id": UNIT,
        "n_fields": 19,
        "items": items["n"],
        "work_units": work_units["n"],
        "items_defaults_only_fields": sorted(item_default_only),
        "items_defaults_only_count": 11,
        "live_item_violations": len(live_item_violations),
        "bare_checker_conforming_rc": rc_good,
        "bare_checker_defaults_only_rc": rc_bad,
        "historical_disarmed_defaults_deletion_exit": historical["exit_code"],
        "historical_disarmed_vfields": historical["vfields"],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"items=103 defaults_only=11/{19} work_units={work_units['n']} "
        f"bare_bad_rc={rc_bad} historical_disarmed_exit=0"
    )
    print(f"SUCCESS:{UNIT}-probe1 presence matrix + defaults-only hole measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
