#!/usr/bin/env python3
"""Probe 1: every salvage row quotes the LICENSE identifying line.

Recomputes file SPDX vs classifier from captures. Live disagreement
count must match the artifact. EXTRACT rows must quote a line that
actually appears in the captured LICENSE bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import salvage as S  # noqa: E402

ART = REPO / S.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0109-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {type(exc).__name__}")
    if S.SENTINEL not in text:
        return fail("completion sentinel absent")
    if "SUCCESS:RES-0109" not in text:
        return fail("SUCCESS:RES-0109 absent")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")

    live = S.build_register()
    ok, reason = S.check_register(live)
    if not ok:
        return fail(reason)

    rows = doc.get("salvage_register") or []
    if len(rows) != live["quoted_license_rows"]:
        return fail(
            f"artifact salvage_register {len(rows)} != live {live['quoted_license_rows']}"
        )
    raw_count = doc.get("license_label_vs_file_disagreement_count")
    if raw_count is None:
        return fail("disagreement_count missing")
    art_count = int(raw_count)
    if art_count != live["disagreement_count"]:
        return fail(
            f"disagreement_count artifact={art_count} live={live['disagreement_count']}"
        )

    live_by_id = {r["row_id"]: r for r in live["salvage_register"]}
    quoted = 0
    for row in rows:
        rid = row.get("row_id")
        line = row.get("license_identifying_line") or ""
        if not line:
            return fail(f"{rid} missing license_identifying_line")
        live_row = live_by_id.get(rid)
        if not live_row:
            return fail(f"{rid} not in live register")
        cap = None
        for cl in live_row["claims"]:
            if str(cl.get("id") or "").endswith("-license"):
                for rail in cl.get("rails") or []:
                    if rail.get("kind") == "prose_source" and rail.get("capture_path"):
                        cap = rail["capture_path"]
                        break
        if not cap:
            return fail(f"{rid} no LICENSE capture path")
        body = (S.CAPTURES / cap).read_text(encoding="utf-8", errors="replace")
        if line not in body:
            return fail(f"{rid} identifying line not in LICENSE bytes")
        if line != live_row["license_identifying_line"]:
            return fail(f"{rid} identifying line drifted from live parse")
        quoted += 1

    extract = [r for r in rows if r.get("disposition") == "EXTRACT"]
    if len(extract) < 1:
        return fail("no EXTRACT row")
    for r in extract:
        if r.get("license_file_spdx") not in {"MIT", "Apache-2.0"}:
            return fail(f"{r.get('row_id')} EXTRACT with non-permissive file SPDX")

    payload = {
        "probe": "probe1-license-quotes",
        "unit_id": "RES-0109",
        "quoted_rows": quoted,
        "disagreement_count": live["disagreement_count"],
        "extract_ids": [r["row_id"] for r in extract],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"quoted_rows={quoted} disagreements={live['disagreement_count']} "
        f"extract={','.join(r['row_id'] for r in extract)}"
    )
    print(
        "SUCCESS:RES-0109-probe1 LICENSE identifying lines quoted; "
        "disagreement count matches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
