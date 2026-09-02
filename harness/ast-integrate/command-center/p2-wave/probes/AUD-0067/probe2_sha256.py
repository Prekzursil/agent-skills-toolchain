#!/usr/bin/env python3
"""Named probe 2: sha256 compare for names present in both trees.

A divergent duplicate must not be counted as one artifact. The control
estate plants one overlapping name with different bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import live_census, probe2_payload  # noqa: E402
from common import OUT, UNIT  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = live_census()
    ctl = live["control"]
    if ctl["divergent_dual"] < 1:
        return fail("control planted divergence was not detected", ctl)
    if ctl["identical_dual"] < 1:
        return fail("control identical overlap was not detected; hasher is inert", ctl)
    if ctl["dual_present"] != ctl["identical_dual"] + ctl["divergent_dual"]:
        return fail("control dual accounting broken", ctl)

    if doc.get("divergent_dual") != live["divergent_dual"]:
        return fail("artifact divergent_dual != live")
    if doc.get("identical_dual") != live["identical_dual"]:
        return fail("artifact identical_dual != live")
    if doc.get("dual_present") != live["dual_present"]:
        return fail("artifact dual_present != live")

    art_div = ((doc.get("control") or {}).get("divergent_dual"))
    if art_div != ctl["divergent_dual"]:
        return fail("artifact control divergent_dual mismatch", doc.get("control"))

    live_rows = {row["name"]: row for row in live["rows"]}
    for art_row in doc.get("rows") or []:
        name = art_row.get("name")
        live_row = live_rows.get(name)
        if live_row is None:
            return fail(f"artifact row not in live census: {name}")
        if bool(art_row.get("divergent")) != bool(live_row["divergent"]):
            return fail(f"divergent flag drift {name}")
        if art_row.get("identical") != live_row["identical"]:
            return fail(f"identical flag drift {name}")

    payload = probe2_payload(live)
    (HERE / "probe2-sha256.raw.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:AUD-0067-probe2 sha256 divergence for dual-present names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
