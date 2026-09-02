#!/usr/bin/env python3
"""Probe 1: every mechanism classified; two rails; needles re-hash.

Recomputes classification and capture integrity from classify.py. Compares
the live table against the emitted artifact. A table that is silent in both
'all structural' and 'all norm-dependent' states would not discriminate;
this probe requires both classes present and every claim to carry two rails
with permalink, fetch timestamp, HTTP status, and sha256.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

OUT = REPO / "command-center/research/RES-0086.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0086-probe1 {msg}")
    return 1


def main() -> int:
    caps = C.verify_captures()
    print(f"captures_ok={caps['ok']} n={caps['n']} failures={caps['failures']}")
    if not caps["ok"]:
        return fail("capture-integrity")

    live = C.attach_rails(C.mechanisms())
    eval_live = C.evaluate_table(live)
    print(
        f"live n={eval_live['n']} structural={eval_live['n_structural']} "
        f"norm={eval_live['n_norm']} silent={eval_live['silent']} "
        f"recommended_fields={eval_live['recommended_fields']}"
    )
    if not eval_live["silent"]:
        return fail(f"live-table-illegal {eval_live['violations']}")
    if eval_live["n_structural"] < 1 or eval_live["n_norm"] < 1:
        return fail("classification-not-discriminating")

    if not OUT.is_file():
        return fail("artifact-missing")
    art = json.loads(OUT.read_text(encoding="utf-8"))
    if "SUCCESS:RES-0086" not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    rows = art.get("mechanism_table") or []
    if len(rows) != len(live):
        return fail(f"table-len artifact={len(rows)} live={len(live)}")

    by_id = {r.get("id"): r for r in rows}
    for live_row in live:
        rec = by_id.get(live_row["id"])
        if not rec:
            return fail(f"missing-row {live_row['id']}")
        if rec.get("enforcement_classification") != live_row[
            "enforcement_classification"
        ]:
            return fail(f"class-drift {live_row['id']}")
        if rec.get("recommended_as_gate") != live_row["recommended_as_gate"]:
            return fail(f"gate-drift {live_row['id']}")
        if rec.get("checkable_artifact_field") != live_row[
            "checkable_artifact_field"
        ]:
            return fail(f"field-drift {live_row['id']}")
        rails = rec.get("rails") or []
        if len(rails) != 2:
            return fail(f"rails-count {live_row['id']} n={len(rails)}")
        kinds = {r.get("kind") for r in rails}
        if "structured-api-probe" not in kinds or "prose-source" not in kinds:
            return fail(f"rails-not-independent {live_row['id']} kinds={kinds}")
        for rail, expected in zip(rails, live_row["rails"]):
            for key in ("permalink", "fetched_at", "http_status", "sha256"):
                if not rail.get(key):
                    return fail(f"rail-missing {live_row['id']} {key}")
            if rail.get("sha256") != expected.get("sha256"):
                if expected.get("binding_full_file_hash") is False:
                    print(
                        f"row={live_row['id']} rail={rail.get('id')} "
                        "full-file-hash informational (not binding)"
                    )
                else:
                    return fail(
                        f"rail-sha-drift {live_row['id']} {rail.get('id')}"
                    )
            if int(rail.get("http_status") or 0) != 200:
                return fail(f"rail-http {live_row['id']} {rail.get('id')}")
        print(
            f"row={live_row['id']} class={live_row['enforcement_classification']} "
            f"field={live_row['checkable_artifact_field']} "
            f"gate={live_row['recommended_as_gate']} "
            f"rails={[r['id'] for r in rails]}"
        )

    claims = art.get("claims") or []
    if len(claims) != 8:
        return fail(f"claims-count {len(claims)}")
    for claim in claims:
        if claim.get("evidence_tier") != "E2":
            return fail(f"claim-not-e2 {claim.get('id')}")
        if len(claim.get("rails") or []) != 2:
            return fail(f"claim-single-rail {claim.get('id')}")

    hg = art.get("hard_gate") or {}
    if hg.get("artifact_field") != C.HARD_GATE_FIELD:
        return fail(f"hard-gate-field {hg.get('artifact_field')}")
    keys = hg.get("required_item_keys") or []
    if list(keys) != list(C.HARD_GATE_ITEM_KEYS):
        return fail(f"hard-gate-keys {keys}")

    unit = C.catalog_res0086()
    if unit.get("id") != "RES-0086":
        return fail("catalog-unit-absent")
    evid = str(unit.get("evidence_requirement") or "")
    if "structurally-enforced" not in evid or "norm-dependent" not in evid:
        return fail("catalog-evidence-requirement-drift")
    if not C.fixture_dissent_line_present():
        return fail("fixture-dissent-line-absent")

    print(
        "SUCCESS:RES-0086-probe1 classification, two-rail lineage, "
        "named hard-gate field"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
