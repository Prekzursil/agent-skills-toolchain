#!/usr/bin/env python3
"""Probe 1: re-harvest, re-generate, re-run; require 30 tags and >=5 discriminating RUN."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402
from generator import generate  # noqa: E402
from runner import combine, execute  # noqa: E402

UNIT = "RES-0153"
ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0153-settling-experiment-generator.json"
)
SENTINEL = "SUCCESS:RES-0153"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if str(doc.get("unit_id") or "") != UNIT:
        return fail("unit_id")

    live = []
    for row in H.harvest_thirty():
        gen = generate(row["claim"])
        exe = execute(gen)
        live.append(combine(row, gen, exe))

    if len(live) != 30:
        return fail(f"harvest n={len(live)}")
    n_disc = sum(
        1
        for r in live
        if r["final_status"] == "RUN" and r["execution"]["discriminating"]
    )
    if n_disc < 5:
        return fail(f"discriminating RUN={n_disc}")

    recorded = doc.get("rows") or []
    if len(recorded) != 30:
        return fail(f"artifact rows={len(recorded)}")
    live_ids = [r["id"] for r in live]
    rec_ids = [r.get("id") for r in recorded]
    if live_ids != rec_ids:
        return fail(f"id-drift live={live_ids[:5]} rec={rec_ids[:5]}")
    for a, b in zip(live, recorded):
        if a["final_status"] != b.get("final_status"):
            return fail(f"status-drift {a['id']} {a['final_status']} {b.get('final_status')}")
        if a["experiment"].get("status") != (b.get("experiment") or {}).get("status"):
            return fail(f"gen-drift {a['id']}")

    meas = doc.get("measurements") or {}
    if int(meas.get("n_discriminating") or 0) != n_disc:
        return fail("measurement n_discriminating drift")
    if int(meas.get("sample_size") or 0) != 30:
        return fail("sample_size")

    claims = doc.get("claims") or []
    if len(claims) < 2:
        return fail("claims thin")
    for c in claims:
        sigs = c.get("signals") or []
        if len(sigs) < 2:
            return fail(f"single-signal {c.get('id')}")
        lin = c.get("lineage") or {}
        if len(str(lin.get("sha256") or "")) != 64:
            return fail(f"lineage sha {c.get('id')}")
        if not lin.get("resolved_url") or not lin.get("fetch_timestamp"):
            return fail(f"lineage incomplete {c.get('id')}")

    payload = {
        "probe": "probe1-generate-and-run",
        "unit_id": UNIT,
        "pass": True,
        "n": 30,
        "discriminating_run": n_disc,
        "ids": live_ids,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"n=30 discriminating_run={n_disc} "
        f"human={sum(1 for r in live if r['final_status']=='NEEDS-HUMAN-FRAMING')}"
    )
    print(f"SUCCESS:{UNIT}-probe1 harvest 30; >=5 discriminating RUN; artifact matches live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
