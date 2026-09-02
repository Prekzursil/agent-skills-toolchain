#!/usr/bin/env python3
"""Probe 1: planted slowdown beyond declared tolerance is caught.

Re-derives IQR/MDE/tolerance from stored raw numbers (statistics reviewer),
then confirms the planted-slowdown pair is labeled regression. Also checks
empty-input and n<11 refusals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SCHEMA = REPO / H.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0106-probe1 {msg}")
    return 1


def close(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != H.UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    text = json.dumps(doc)
    if H.COMPLETION_SENTINEL not in text:
        return fail("completion_sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path)
    )
    if errs:
        return fail(f"schema {errs[0].message}")

    rows = H.make_rows()
    frame = doc.get("sampling_frame") or {}
    if frame.get("seed") != H.SEED:
        return fail("seed mismatch")
    if H.payload_digest(rows) != frame.get("payload_sha256"):
        return fail("payload redraw not identical")
    if len(rows) != int(frame.get("payload_n") or 0):
        return fail("payload_n mismatch")
    if len(rows) < 1:
        return fail("empty payload")

    empty = H.empty_input_control()
    if not empty["failed_as_required"]:
        return fail("empty input was not refused")
    nlt = H.n_lt_min_control()
    if not nlt["failed_as_required"]:
        return fail("n<11 was not refused")

    pin_raw = (doc.get("baseline") or {}).get("raw_ns") or []
    if len(pin_raw) < H.MIN_N:
        return fail("pinned baseline under-sampled")
    band = H.variance_band(pin_raw)
    tol = H.derive_tolerance(band)
    stored_tol = doc.get("tolerance") or {}
    if not close(float(tol["tolerance_ns"]), float(stored_tol.get("tolerance_ns") or 0)):
        return fail(
            f"tolerance recomputed={tol['tolerance_ns']} stored={stored_tol.get('tolerance_ns')}"
        )
    T = float(tol["tolerance_ns"])
    if T <= 0:
        return fail("non-positive tolerance")

    benches = {b["id"]: b for b in (doc.get("benchmarks") or []) if isinstance(b, dict)}
    slow = benches.get("planted-slowdown")
    if not slow:
        return fail("planted-slowdown benchmark missing")
    order = (slow.get("interleaving") or {}).get("order") or []
    if not H.is_abab(order):
        return fail(f"planted order not A B A B: {order}")
    arms = {a["id"]: a for a in slow.get("arms") or []}
    if "A" not in arms or "B" not in arms:
        return fail("planted missing arms")
    if len(arms["A"]["raw_ns"]) < H.MIN_N or len(arms["B"]["raw_ns"]) < H.MIN_N:
        return fail("planted under-sampled")
    if int(arms["A"].get("n_inputs") or 0) < 1:
        return fail("planted empty n_inputs")

    sa = H.summarize(arms["A"]["raw_ns"])
    sb = H.summarize(arms["B"]["raw_ns"])
    for key in ("n", "median_ns", "iqr_ns", "mean_ns", "ci95_lo_ns", "ci95_hi_ns", "stdev_ns"):
        stored = arms["A"]["statistics"][key]
        got = sa[key]
        if key == "n":
            if got != stored:
                return fail(f"planted.A n {got}!={stored}")
        elif not close(float(got), float(stored)):
            return fail(f"planted.A {key} recomputed={got} stored={stored}")

    cls = H.classify(sa, sb, T)
    stored_cls = slow.get("comparison") or {}
    if cls["label"] != stored_cls.get("label"):
        return fail(f"planted label recomputed={cls['label']} stored={stored_cls.get('label')}")
    if cls["label"] != "regression":
        return fail(f"planted slowdown not regression label={cls['label']}")
    if abs(cls["delta_median_ns"]) <= T:
        return fail("planted |delta| inside tolerance")

    pin_st = H.summarize(pin_raw)
    vs_pin = H.classify(pin_st, sb, T)
    if vs_pin["label"] != "regression":
        return fail(f"vs pinned baseline label={vs_pin['label']}")

    fake_series = [1000.0 + 10 * i for i in range(11)]
    syn = H.classify(
        H.summarize(fake_series),
        H.summarize([10000.0 + 10 * i for i in range(11)]),
        float(H.derive_tolerance(H.variance_band(fake_series))["tolerance_ns"]),
    )
    if syn["label"] != "regression":
        return fail(f"synthetic planted label={syn['label']}")

    out = {
        "n_inputs": len(rows),
        "pass": True,
        "planted_label": cls["label"],
        "probe": "probe1-planted-slowdown",
        "seed": H.SEED,
        "tolerance_ns": T,
        "unit_id": H.UNIT,
        "vs_pinned_label": vs_pin["label"],
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0106-probe1 planted slowdown beyond tolerance is caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
