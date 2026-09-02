#!/usr/bin/env python3
"""Probe 1: recompute Cohen kappa from committed corpus + both rating sheets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import score as S  # noqa: E402
from rubric import published_sha256  # noqa: E402

ART = REPO / "command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json"
SHEET_A = HERE / "sheets" / "rater_a.json"
SHEET_B = HERE / "sheets" / "rater_b.json"
PUB = HERE / "fixtures" / "rubric.published.json"
UNIT = "RES-0144"
SENTINEL = "SUCCESS:RES-0144"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0144-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("unit_id") or "") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if not SHEET_A.is_file() or not SHEET_B.is_file():
        return fail("rating-sheets-absent")

    live = S.run()
    if live["sample_size"] != 40:
        return fail(f"sample_size={live['sample_size']}")
    meas = doc.get("measurements") or {}
    if int(meas.get("sample_size") or 0) != 40:
        return fail(f"artifact-sample-size {meas.get('sample_size')}")

    for axis, key in (
        ("authority", "kappa_authority"),
        ("independence", "kappa_independence"),
        ("joint", "kappa_joint"),
    ):
        live_k = float(live[key]["kappa"])
        rec_k = float(meas.get(key) if not isinstance(meas.get(key), dict) else meas[key].get("kappa"))
        # measurements stores the float; full objects live under calibration
        rec = meas.get(key)
        if isinstance(rec, dict):
            rec_k = float(rec.get("kappa"))
        else:
            rec_k = float(rec)
        if abs(live_k - rec_k) > 1e-9:
            return fail(f"{axis}-kappa-drift live={live_k} rec={rec_k}")

    cal = doc.get("calibration") or {}
    if int(cal.get("authority_disagree_n") or -1) != live["kappa_authority"]["disagree_n"]:
        return fail("authority-disagree-count-drift")
    if int(cal.get("independence_disagree_n") or -1) != live["kappa_independence"]["disagree_n"]:
        return fail("independence-disagree-count-drift")
    if live["kappa_authority"]["disagree_n"] < 1 and live["kappa_independence"]["disagree_n"] < 1:
        return fail("perfect-agreement-on-both-axes-suspicious")

    sa = json.loads(SHEET_A.read_text(encoding="utf-8"))
    sb = json.loads(SHEET_B.read_text(encoding="utf-8"))
    if len(sa.get("rows") or []) != 40 or len(sb.get("rows") or []) != 40:
        return fail("sheet-row-count")
    live_a = {r["id"]: r for r in live["rater_a"]}
    live_b = {r["id"]: r for r in live["rater_b"]}
    for row in sa["rows"]:
        lr = live_a[row["id"]]
        if row["authority"] != lr["authority"] or row["independence"] != lr["independence"]:
            return fail(f"sheet-a-drift {row['id']}")
    for row in sb["rows"]:
        lr = live_b[row["id"]]
        if row["authority"] != lr["authority"] or row["independence"] != lr["independence"]:
            return fail(f"sheet-b-drift {row['id']}")

    rec_sha = str((doc.get("rubric") or {}).get("published_sha256") or "")
    live_sha = published_sha256()
    if rec_sha != live_sha:
        return fail(f"rubric-sha-mismatch rec={rec_sha} live={live_sha}")
    if PUB.is_file():
        pub = json.loads(PUB.read_text(encoding="utf-8"))
        from rubric import published_sha256 as psha  # noqa: WPS433

        if psha(pub) != live_sha:
            return fail("published-file-diverged")

    claims = doc.get("claims") or []
    if len(claims) < 2:
        return fail("claims-thin")
    for claim in claims:
        sigs = claim.get("signals") or []
        if len(sigs) < 2:
            return fail(f"claim-single-signal {claim.get('id')}")
        lin = claim.get("lineage") or {}
        if len(str(lin.get("sha256") or "")) != 64:
            return fail(f"claim-lineage {claim.get('id')}")

    print(
        "kappa_authority={a} kappa_independence={i} "
        "auth_disagree={ad} ind_disagree={id_} rubric_sha={s}".format(
            a=live["kappa_authority"]["kappa"],
            i=live["kappa_independence"]["kappa"],
            ad=live["kappa_authority"]["disagree_n"],
            id_=live["kappa_independence"]["disagree_n"],
            s=live_sha,
        )
    )
    print(
        "authority_levels_causing_disagreement="
        + json.dumps(live["authority_disagreement_levels"], sort_keys=True)
    )
    print(
        "independence_levels_causing_disagreement="
        + json.dumps(live["independence_disagreement_levels"], sort_keys=True)
    )
    print("SUCCESS:RES-0144-probe1 kappa recomputed from both committed rating sheets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
