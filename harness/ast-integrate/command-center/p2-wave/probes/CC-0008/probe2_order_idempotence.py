#!/usr/bin/env python3
"""CC-0008 probe 2: order-independence, idempotence, live disk recount vs floor.

Merging the same slices in permuted order must be byte-identical.
Re-merging must be a no-op, not a duplication.
Live catalog work_unit count is read back off disk; shortfall vs 2048 is first-class.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import merge_catalog as M  # noqa: E402

UNIT = "CC-0008"
LIVE = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FLOOR = 2048


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    alloc = M.load_allocation()
    tmp = Path(tempfile.mkdtemp(prefix="cc0008-p2-"))
    try:
        fx = tmp / "fx"
        fx.mkdir()
        slices = [
            M.write_canonical(
                fx / "c.json",
                {"work_units": [M.minimal_unit("CC-0010"), M.minimal_unit("CC-0011")]},
            )
            or (fx / "c.json"),
            fx / "a.json",
            fx / "b.json",
        ]
        # write_canonical returns None; write the other two explicitly
        M.write_canonical(fx / "a.json", {"work_units": [M.minimal_unit("ADV-0099")]})
        M.write_canonical(fx / "b.json", {"work_units": [M.minimal_unit("IMP-0007")]})
        paths = [fx / "a.json", fx / "b.json", fx / "c.json"]

        orders = [paths, list(reversed(paths)), [paths[1], paths[2], paths[0]]]
        dumps = []
        for order in orders:
            units = M.merge_slices(order, allocation=alloc)
            dumps.append(M.canonical_dumps({"work_units": units}).encode("utf-8"))
        if not (dumps[0] == dumps[1] == dumps[2]):
            print(f"FAILED:{UNIT}-probe2 permuted merge not byte-identical")
            return 1
        print(f"order-independence sha256={digest(dumps[0])} n={len(json.loads(dumps[0])['work_units'])}")

        first = tmp / "out1.json"
        second = tmp / "out2.json"
        cat1 = M.merge_to_catalog(paths, allocation=alloc)
        M.write_canonical(first, cat1)
        cat2 = M.merge_to_catalog(paths, allocation=alloc)
        M.write_canonical(second, cat2)
        b1, b2 = first.read_bytes(), second.read_bytes()
        if b1 != b2:
            print(f"FAILED:{UNIT}-probe2 re-merge not byte-identical")
            return 1
        n1, _ = M.read_back_count(first)
        n2, _ = M.read_back_count(second)
        if n1 != n2 or n1 != 4:
            print(f"FAILED:{UNIT}-probe2 idempotence counts n1={n1} n2={n2}")
            return 1
        print(f"idempotence n_read_back={n1} sha256={digest(b1)}")

        live = json.loads(LIVE.read_text(encoding="utf-8"))
        live_units = live.get("work_units") if isinstance(live, dict) else None
        if not isinstance(live_units, list):
            print(f"FAILED:{UNIT}-probe2 live catalog has no work_units")
            return 1
        live_n = len(live_units)
        live_prefix = M.counts_by_prefix(live_units)
        live_bucket_field: dict[str, int] = {}
        missing_bucket = 0
        for u in live_units:
            b = u.get("bucket") if isinstance(u, dict) else None
            if not b:
                missing_bucket += 1
            else:
                live_bucket_field[str(b)] = live_bucket_field.get(str(b), 0) + 1
        prefix_sum = sum(live_prefix.values())
        if prefix_sum != live_n:
            print(f"FAILED:{UNIT}-probe2 prefix sum {prefix_sum} != live_n {live_n}")
            return 1

        extracted = tmp / "live-slices"
        exported = M.export_slices_from_catalog(live, extracted)
        merged_path = tmp / "live-merged.json"
        merged = M.merge_to_catalog(exported, allocation=alloc)
        M.write_canonical(merged_path, merged)
        read_n, read_prefix = M.read_back_count(merged_path)
        if read_n != live_n:
            print(
                f"FAILED:{UNIT}-probe2 live re-merge read_back={read_n} live_disk={live_n}"
            )
            return 1
        if read_prefix != live_prefix:
            print(f"FAILED:{UNIT}-probe2 live re-merge prefix mismatch")
            return 1

        shortfall = FLOOR - live_n
        print(
            json.dumps(
                {
                    "floor": FLOOR,
                    "idempotent": True,
                    "live_bucket_field_counts": dict(sorted(live_bucket_field.items())),
                    "live_missing_bucket_field": missing_bucket,
                    "live_per_prefix": live_prefix,
                    "live_work_units_read_from_disk": live_n,
                    "order_independent": True,
                    "pass": True,
                    "prefix_sum": prefix_sum,
                    "probe": "probe2-order-idempotence-live-recount",
                    "remerge_units_read_back": read_n,
                    "shortfall": shortfall,
                    "shortfall_is_first_class": True,
                    "slices_exported": len(exported),
                    "unit_id": UNIT,
                },
                sort_keys=True,
            )
        )
        print(
            f"SUCCESS:{UNIT}-probe2 order-independence+idempotence "
            f"live_n={live_n} floor={FLOOR} shortfall={shortfall}"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
