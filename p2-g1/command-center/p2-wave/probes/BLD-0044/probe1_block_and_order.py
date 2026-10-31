#!/usr/bin/env python3
"""Probe 1: both-states egress block + two order seeds (live, not cached)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_cell  # noqa: E402
from common import (  # noqa: E402
    ORDER_READ_FIRST_SEED,
    ORDER_WRITE_FIRST_SEED,
    PRNG_HIT_SEED,
    REPO,
    block_control,
    verify_seeds,
)

RECEIPT = REPO / "command-center/receipts/BLD-0044.json"


def _cell(order_seed: int, tmp: Path) -> dict:
    scratch = tmp / f"scratch-{order_seed}"
    cache = tmp / f"cache-{order_seed}"
    scratch.mkdir()
    cache.mkdir()
    (cache / "warm-token").write_text("warm", encoding="utf-8")
    empty = tmp / "empty"
    empty.mkdir(exist_ok=True)
    axes = {
        "order_seed": order_seed,
        "prng_seed": PRNG_HIT_SEED,
        "tz": "UTC",
        "cwd": "suite",
        "cache": "warm",
        "egress": "open",
    }
    return run_cell(axes, scratch, cache, HERE, empty)


def main() -> int:
    verify_seeds()
    if not RECEIPT.is_file():
        print("FAILED:BLD-0044-probe1 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "BLD-0044" or "SUCCESS:BLD-0044" not in blob:
        print("FAILED:BLD-0044-probe1 sentinel/unit_id")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0044-probe1 self-declared", doc.get("state"))
        return 1

    block = block_control()
    if not block["both_states"]:
        print("FAILED:BLD-0044-probe1 block control not both-states", json.dumps(block))
        return 1
    if block["deliberate_fetch_open"] != "PASS" or block["deliberate_fetch_blocked"] != "FAIL":
        print("FAILED:BLD-0044-probe1 block polarity", json.dumps(block))
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0044-p1-") as td:
        tmp = Path(td)
        a = _cell(ORDER_WRITE_FIRST_SEED, tmp)
        b = _cell(ORDER_READ_FIRST_SEED, tmp)
    read_a = (a["results"].get("test_order_read") or {}).get("outcome")
    read_b = (b["results"].get("test_order_read") or {}).get("outcome")
    herm_a = (a["results"].get("test_hermetic") or {}).get("outcome")
    herm_b = (b["results"].get("test_hermetic") or {}).get("outcome")
    if read_a == read_b:
        print(f"FAILED:BLD-0044-probe1 order did not diverge read_a={read_a} read_b={read_b}")
        return 1
    if {read_a, read_b} != {"PASS", "FAIL"}:
        print(f"FAILED:BLD-0044-probe1 unexpected order pair {read_a} {read_b}")
        return 1
    if herm_a != "PASS" or herm_b != "PASS":
        print(f"FAILED:BLD-0044-probe1 hermetic flipped {herm_a} {herm_b}")
        return 1

    out = {
        "probe": "probe1-block-and-order",
        "unit_id": "BLD-0044",
        "block": block,
        "order_seeds": [ORDER_WRITE_FIRST_SEED, ORDER_READ_FIRST_SEED],
        "test_order_read": {"seed_write_first": read_a, "seed_read_first": read_b},
        "hermetic": {"a": herm_a, "b": herm_b},
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:BLD-0044-probe1 both-states block "
        f"open={block['deliberate_fetch_open']} blocked={block['deliberate_fetch_blocked']} "
        f"order_read {read_a}/{read_b}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
