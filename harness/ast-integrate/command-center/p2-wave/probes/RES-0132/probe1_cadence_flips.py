#!/usr/bin/env python3
"""Probe 1: T+0/T+7d/T+30d named flips, lag, and frozen-hash identity match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import measure as M  # noqa: E402

ART = REPO / C.OUTPUT_REL
SCHEMA = REPO / C.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0132-probe1 {msg}")
    return 1


def close(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= max(1e-9, 1e-12 * max(abs(float(a)), abs(float(b)), 1.0))


def flip_keys(rows: list) -> list[tuple[str, str, str]]:
    out = []
    for ev in rows:
        out.append(
            (
                str(ev.get("lockfile_id") or ""),
                str(ev.get("checkpoint") or ""),
                str(ev.get("advisory_id") or ""),
            )
        )
    return sorted(out)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != C.UNIT_ID:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("report_kind") != "measurement-run":
        return fail(f"report_kind={doc.get('report_kind')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errors:
        return fail(f"schema {errors[0].message}")

    live = M.run()
    if not live.get("invariants_ok"):
        return fail("live invariants_ok false")

    art_named = doc.get("named_flips") or []
    live_named = live.get("named_flips") or []
    if not live_named:
        return fail("live named_flips empty")
    if any(not ev.get("advisory_id") for ev in live_named):
        return fail("a live named flip lacks advisory_id")
    if flip_keys(art_named) != flip_keys(live_named):
        return fail(
            f"named flip ids mismatch art={flip_keys(art_named)} live={flip_keys(live_named)}"
        )

    if live.get("historical_t30_flip_rate") != doc.get("historical_t30_flip_rate"):
        return fail("historical_t30_flip_rate mismatch")
    if live.get("historical_interval_flip_rate") != doc.get("historical_interval_flip_rate"):
        return fail("historical_interval_flip_rate mismatch")
    if not close(live.get("median_lag_days"), doc.get("median_lag_days")):
        return fail(
            f"median_lag_days live={live.get('median_lag_days')} art={doc.get('median_lag_days')}"
        )
    if live.get("product_lockfile_flipped_in_30d") != doc.get(
        "product_lockfile_flipped_in_30d"
    ):
        return fail("product_lockfile_flipped_in_30d mismatch")
    if doc.get("control_t0_all_red") is not True:
        return fail("artifact control_t0_all_red is not true")
    if live.get("control_t0_all_red") is not True:
        return fail("live control_t0_all_red is not true")

    live_by_id = {r["id"]: r for r in live["lockfiles"]}
    art_by_id = {r["id"]: r for r in (doc.get("lockfiles") or [])}
    if set(live_by_id) != set(art_by_id):
        return fail("lockfile id set mismatch")
    for lid, row in live_by_id.items():
        hashes = row.get("lockfile_hash_reverified") or {}
        if hashes.get("identical") is not True:
            return fail(f"{lid} lockfile hash not identical across cadence")
        if hashes.get("T+0") != row.get("sha256"):
            return fail(f"{lid} T+0 hash != recorded sha256")
        art_row = art_by_id[lid]
        if art_row.get("sha256") != row.get("sha256"):
            return fail(f"{lid} artifact sha256 drifted")
        art_h = art_row.get("lockfile_hash_reverified") or {}
        if art_h.get("T+0") != hashes.get("T+0") or art_h.get("identical") is not True:
            return fail(f"{lid} artifact hash re-verify drifted")
        for label in ("T+0", "T+7d", "T+30d"):
            if row[label]["verdict"] != art_row[label]["verdict"]:
                return fail(f"{lid} {label} verdict mismatch")

    meas = {m["id"]: m for m in (doc.get("measurements") or []) if isinstance(m, dict)}
    for mid in (
        "historical-t30-verdict-flip-rate",
        "median-lag-days",
        "product-30d-verdict-flip",
        "lockfile-hash-identical-across-cadence",
    ):
        if mid not in meas:
            return fail(f"measurement {mid} absent")
    if meas["historical-t30-verdict-flip-rate"].get("value") != live["historical_t30_flip_rate"]:
        return fail("measurement flip-rate value mismatch")
    if not close(meas["median-lag-days"].get("value"), live["median_lag_days"]):
        return fail("measurement median-lag value mismatch")
    if meas["product-30d-verdict-flip"].get("value") != live["product_lockfile_flipped_in_30d"]:
        return fail("measurement product-flip value mismatch")
    if meas["lockfile-hash-identical-across-cadence"].get("value") is not True:
        return fail("measurement hash-identical is not true")

    print(
        "historical_t30_flip_rate="
        f"{live['historical_t30_flip_rate']} "
        f"interval_flip_rate={live['historical_interval_flip_rate']} "
        f"median_lag_days={live['median_lag_days']} "
        f"named_flips={len(live_named)} "
        f"product_flip={live['product_lockfile_flipped_in_30d']}"
    )
    print("SUCCESS:RES-0132-probe1 cadence named flips match artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
