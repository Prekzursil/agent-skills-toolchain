#!/usr/bin/env python3
"""Probe 2: within-noise change is not reported as a regression.

Recomputes the declared tolerance from the pinned raw series and confirms
the identity pair is no_measurable_change. A synthetic inside-band shift
must not be labeled regression.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0106-probe2 {msg}")
    return 1


def close(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if H.COMPLETION_SENTINEL not in json.dumps(doc):
        return fail("completion_sentinel absent")

    body = H.payload(doc)
    pin_raw = (body.get("baseline") or {}).get("raw_ns") or []
    if len(pin_raw) < H.MIN_N:
        return fail("pinned baseline under-sampled")
    band = H.variance_band(pin_raw)
    T = float(H.derive_tolerance(band)["tolerance_ns"])
    stored_t = float((body.get("tolerance") or {}).get("tolerance_ns") or 0)
    if not close(T, stored_t):
        return fail(f"tolerance recomputed={T} stored={stored_t}")

    benches = {b["id"]: b for b in (body.get("benchmarks") or []) if isinstance(b, dict)}
    ident = benches.get("within-noise-identity")
    if not ident:
        return fail("within-noise-identity benchmark missing")
    order = (ident.get("interleaving") or {}).get("order") or []
    if not H.is_abab(order):
        return fail(f"identity order not A B A B: {order}")
    arms = {a["id"]: a for a in ident.get("arms") or []}
    if "A" not in arms or "B" not in arms:
        return fail("identity missing arms")

    sa = H.summarize(arms["A"]["raw_ns"])
    sb = H.summarize(arms["B"]["raw_ns"])
    for key in ("median_ns", "iqr_ns", "mean_ns", "ci95_lo_ns", "ci95_hi_ns"):
        if not close(float(sa[key]), float(arms["A"]["statistics"][key])):
            return fail(f"identity.A {key} mismatch")
        if not close(float(sb[key]), float(arms["B"]["statistics"][key])):
            return fail(f"identity.B {key} mismatch")

    cls = H.classify(sa, sb, T)
    stored = ident.get("comparison") or {}
    if cls["label"] != stored.get("label"):
        return fail(f"identity label recomputed={cls['label']} stored={stored.get('label')}")
    if cls["label"] == "regression":
        return fail("within-noise identity labeled regression")
    if abs(cls["delta_median_ns"]) <= T and cls["label"] != "no_measurable_change":
        return fail("inside-tolerance not no_measurable_change")
    if cls["label"] != "no_measurable_change":
        return fail(f"identity label={cls['label']}")

    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t2 = tests.get("test_within_noise_change_is_not_reported_as_a_regression")
    if not t2 or t2.get("result") != "PASS":
        return fail("required test row missing or not PASS")

    fake_series = [1000.0 + 10 * i for i in range(11)]
    fake_t = float(H.derive_tolerance(H.variance_band(fake_series))["tolerance_ns"])
    fake = H.classify(
        H.summarize(fake_series),
        H.summarize([1005.0 + 10 * i for i in range(11)]),
        fake_t,
    )
    if fake["label"] == "regression":
        return fail(f"synthetic inside-band labeled regression ({fake})")
    if abs(fake["delta_median_ns"]) <= fake_t and fake["label"] != "no_measurable_change":
        return fail("synthetic inside-band not no_measurable_change")

    syn_stored = (body.get("synthetic_controls") or {}).get("within_band") or {}
    if syn_stored.get("label") == "regression":
        return fail("artifact synthetic within_band labeled regression")

    out = {
        "identity_label": cls["label"],
        "pass": True,
        "probe": "probe2-within-noise",
        "synthetic_inside_band": fake["label"],
        "tolerance_ns": T,
        "unit_id": H.UNIT,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0106-probe2 within-noise change is not a regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
