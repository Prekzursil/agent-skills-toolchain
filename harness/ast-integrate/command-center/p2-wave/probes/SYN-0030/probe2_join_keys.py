#!/usr/bin/env python3
"""Named probe 2: join keys are ids not titles; live artifact has eight counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import join as J  # noqa: E402
import shape as S  # noqa: E402

OUT = "command-center/receipts/SYN-0030.json"
SCHEMA = "command-center/schema/referential-integrity.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
REQUIRED = list(J.DIRECTION_ORDER)
GARBAGE = S.GARBAGE


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0030-probe2 {msg}")
    return 1


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "SYN-0030":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:SYN-0030-probe2 catalog unit missing")


def main() -> int:
    docs = F.title_collision_fixture()
    id_join = J.join_registries(
        docs["catalog"], docs["artifact"], docs["test"], docs["claim"]
    )
    title_join = J.title_join_registries(
        docs["catalog"], docs["artifact"], docs["test"], docs["claim"]
    )
    orphan_ids = id_join["by_direction"]["catalog_without_artifact"]["ids"]
    print(f"id_join_orphans={orphan_ids}")
    print(f"title_join_orphans={title_join['catalog_without_artifact']}")
    if "U-ORPHAN" not in orphan_ids:
        return fail("id join missed U-ORPHAN (same title as U-KEEP)")
    if "U-ORPHAN" in title_join["catalog_without_artifact"]:
        return fail("title join unexpectedly listed U-ORPHAN; control is broken")
    if title_join["catalog_without_artifact"]:
        # Shared title is present on both sides, so title join should be silent.
        return fail("title join was not silent on the shared title")

    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact absent")
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"unparseable {type(exc).__name__}")
    sentinel = catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        return fail("declared output_schema missing")
    validator = jsonschema.Draft7Validator(S.DISCRIMINATOR)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("schema errors:")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return fail("schema")
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")

    rows = doc.get("directed_counts") or []
    if len(rows) != 8:
        return fail(f"directed_counts len={len(rows)}")
    names = [row.get("direction") for row in rows if isinstance(row, dict)]
    if sorted(names) != sorted(REQUIRED):
        return fail(f"direction set {names}")
    for row in rows:
        if "denominator" not in row:
            return fail(f"{row.get('direction')} missing denominator")
        count = int(row["count"])
        ids = row.get("ids") or []
        if count != len(ids):
            return fail(
                f"{row['direction']} count={count} ids={len(ids)} mismatch"
            )
        if count > 0 and not ids:
            return fail(f"{row['direction']} non-zero without id list")
        if int(row["denominator"]) < 0:
            return fail(f"{row['direction']} negative denominator")
    if "all_consistent" in doc and "directed_counts" not in doc:
        return fail("all_consistent without directed_counts")
    live = J.load_live(REPO)
    for row in rows:
        live_row = live["by_direction"][row["direction"]]
        if int(live_row["count"]) != int(row["count"]):
            return fail(
                f"live drift {row['direction']} artifact={row['count']} "
                f"live={live_row['count']}"
            )
        if int(live_row["denominator"]) != int(row["denominator"]):
            return fail(f"denominator drift {row['direction']}")
    keys = doc.get("join_keys") or {}
    if keys.get("are_ids") is not True:
        return fail("join_keys.are_ids is not true")
    print(
        "join_keys=ids title_collision_detected=True "
        "eight_counts_with_denominators=True schema_ok=True"
    )
    print("SUCCESS:SYN-0030-probe2 join-keys schema live-counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
