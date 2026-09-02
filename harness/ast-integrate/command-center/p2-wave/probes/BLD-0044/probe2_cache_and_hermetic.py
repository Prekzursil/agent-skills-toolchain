#!/usr/bin/env python3
"""Probe 2: independent blocked-fetch repeat + cold/warm cache + hermetic control."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_cell  # noqa: E402
from common import (  # noqa: E402
    ORDER_WRITE_FIRST_SEED,
    PRNG_HIT_SEED,
    REPO,
    block_control,
)

RECEIPT = REPO / "command-center/receipts/BLD-0044.json"


def _cell(cache_mode: str, tmp: Path, *, egress: str = "open") -> dict:
    scratch = tmp / f"scratch-{cache_mode}-{egress}"
    cache = tmp / f"cache-{cache_mode}-{egress}"
    scratch.mkdir()
    cache.mkdir()
    if cache_mode == "warm":
        (cache / "warm-token").write_text("warm", encoding="utf-8")
    empty = tmp / "empty"
    empty.mkdir(exist_ok=True)
    axes = {
        "order_seed": ORDER_WRITE_FIRST_SEED,
        "prng_seed": PRNG_HIT_SEED,
        "tz": "UTC",
        "cwd": "suite",
        "cache": cache_mode,
        "egress": egress,
    }
    return run_cell(axes, scratch, cache, HERE, empty)


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:BLD-0044-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0044" not in json.dumps(doc):
        print("FAILED:BLD-0044-probe2 sentinel")
        return 1

    block = block_control()
    if not block["both_states"]:
        print("FAILED:BLD-0044-probe2 independent block control failed", json.dumps(block))
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0044-p2-") as td:
        tmp = Path(td)
        cold = _cell("cold", tmp)
        warm = _cell("warm", tmp)
        blocked = _cell("warm", tmp, egress="blocked")

    cold_hit = (cold["results"].get("test_cache_hit") or {}).get("outcome")
    warm_hit = (warm["results"].get("test_cache_hit") or {}).get("outcome")
    hermetic = [
        (cold["results"].get("test_hermetic") or {}).get("outcome"),
        (warm["results"].get("test_hermetic") or {}).get("outcome"),
        (blocked["results"].get("test_hermetic") or {}).get("outcome"),
    ]
    fetch_open = (warm["results"].get("test_undeclared_fetch") or {}).get("outcome")
    fetch_blocked = (blocked["results"].get("test_undeclared_fetch") or {}).get("outcome")

    if cold_hit != "FAIL" or warm_hit != "PASS":
        print(f"FAILED:BLD-0044-probe2 cache polarities cold={cold_hit} warm={warm_hit}")
        return 1
    if any(x != "PASS" for x in hermetic):
        print(f"FAILED:BLD-0044-probe2 hermetic false positive {hermetic}")
        return 1
    if fetch_open != "PASS" or fetch_blocked != "FAIL":
        print(
            f"FAILED:BLD-0044-probe2 undeclared fetch open={fetch_open} blocked={fetch_blocked}"
        )
        return 1

    axes_reported = set((doc.get("divergences_by_axis") or {}).keys())
    need = {"order_seed", "prng_seed", "tz", "cwd", "cache", "egress"}
    if not need.issubset(axes_reported):
        print(f"FAILED:BLD-0044-probe2 receipt missing axes {need - axes_reported}")
        return 1
    if (doc.get("measured_scope") or {}).get("overclaim") is True:
        print("FAILED:BLD-0044-probe2 receipt overclaim flag")
        return 1
    cnf = (doc.get("dependency_receipts") or {}).get("CNF-0147") or {}
    if cnf.get("re_derived") is True:
        print("FAILED:BLD-0044-probe2 CNF-0147 was re-derived")
        return 1

    out = {
        "probe": "probe2-cache-hermetic-block-repeat",
        "unit_id": "BLD-0044",
        "independent_block": block,
        "cache": {"cold": cold_hit, "warm": warm_hit},
        "hermetic": hermetic,
        "undeclared_fetch": {"open": fetch_open, "blocked": fetch_blocked},
        "receipt_axes": sorted(axes_reported),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:BLD-0044-probe2 independent block repeat "
        f"cache cold={cold_hit} warm={warm_hit} hermetic=PASS fetch {fetch_open}/{fetch_blocked}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
