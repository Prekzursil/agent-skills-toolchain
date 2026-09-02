#!/usr/bin/env python3
"""Probe 2: independent 30-cell re-derivation plus planted source-mismatch control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / E.OUT_REL
UNIT = "WFA-0043"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if E.SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    live = E.run_census()
    extractors = live["_extractors_live"]
    sample = E.rederive_sample(live["rows"], extractors)
    if sample["n"] != E.RERIVE_N:
        return fail(f"sample n={sample['n']} expected {E.RERIVE_N}")
    art_r = doc.get("rederive") or {}
    if int(art_r.get("n") or 0) != E.RERIVE_N:
        return fail("artifact rederive n != 30")
    if "error_rate" not in art_r:
        return fail("artifact omitted rederive error_rate")
    if abs(float(art_r["error_rate"]) - float(sample["error_rate"])) > 1e-12:
        return fail(
            f"error_rate drift artifact={art_r['error_rate']} live={sample['error_rate']}"
        )
    if float(art_r["error_rate"]) > float(art_r.get("threshold") or E.RERIVE_THRESHOLD):
        if not (art_r.get("dimensions_rerun") or doc.get("dimensions_rerun")):
            return fail("error_rate over threshold but no dimension re-run recorded")

    # Control fixture: both-states + planted forgery.
    ctrl_ext = E.control_extractors()
    ctrl_uni = E.control_universe()
    ctrl_rows = E.census_grid(ctrl_uni, ctrl_ext)
    alpha = E.rederive_cell("ctrl-alpha", "provenance", ctrl_ext)
    beta = E.rederive_cell("ctrl-beta", "provenance", ctrl_ext)
    gamma = E.rederive_cell("ctrl-gamma", "provenance", ctrl_ext)
    delta = E.rederive_cell("ctrl-delta", "provenance", ctrl_ext)
    if alpha["state"] != "EVIDENCED":
        return fail(f"ctrl-alpha provenance should rederive EVIDENCED got {alpha}")
    if beta["state"] != "HONEST-NULL":
        return fail(f"ctrl-beta provenance should rederive HONEST-NULL got {beta}")
    if gamma["state"] != "EMPTY":
        return fail(f"ctrl-gamma provenance should rederive EMPTY got {gamma}")
    if delta["state"] == "EVIDENCED":
        return fail("planted FORGED evidenced cell was not caught against raw source")

    census_delta = None
    for row in ctrl_rows:
        if row["id"] == "ctrl-delta":
            census_delta = row["cells"][0]  # provenance is dimension 0
    if census_delta == "EVIDENCED" and delta["state"] != "EVIDENCED":
        planted_caught = True
    elif census_delta != "EVIDENCED":
        # Classifier already refused the unconfirmable cell; still a catch.
        planted_caught = True
    else:
        planted_caught = False
    if not planted_caught:
        return fail("planted mismatch did not fire")

    states_seen = {st for row in ctrl_rows for st in row["cells"]}
    if set(E.STATES) - states_seen:
        return fail(f"control census missing states {set(E.STATES) - states_seen}")

    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    if tests.get("WFA-0043-RERIVE-30", {}).get("result") != "PASS":
        return fail("embedded rederive test not PASS")

    payload = {
        "pass": True,
        "probe": "probe2-rederive",
        "unit_id": UNIT,
        "n": sample["n"],
        "error_rate": sample["error_rate"],
        "threshold": sample["threshold"],
        "composition": sample["composition"],
        "dimensions_rerun": sample["dimensions_rerun"],
        "planted_forgery_caught": True,
        "ctrl_alpha": alpha["state"],
        "ctrl_beta": beta["state"],
        "ctrl_gamma": gamma["state"],
        "ctrl_delta": delta["state"],
        "reviewer_starts_from_tests": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"rederive n=30 error_rate={sample['error_rate']} "
        f"forgery_caught=True alpha={alpha['state']} delta={delta['state']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 30-cell re-derivation and planted source mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
