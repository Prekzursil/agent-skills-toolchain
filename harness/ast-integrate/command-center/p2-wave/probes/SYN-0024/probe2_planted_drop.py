#!/usr/bin/env python3
"""Probe 2: planted drop is reported; ratios use records, not bytes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import controls as C  # noqa: E402
import overclaim as O  # noqa: E402
from paths import OUT_REL, PIN_REFUTED_ID, REPO, UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    drop = C.planted_drop()
    ratio = C.ratio_units()
    print(
        json.dumps(
            {
                "probe": "probe2-planted-drop-and-ratio-units",
                "planted_drop": {
                    "ok": drop["ok"],
                    "silent_on_full": drop["silent_on_full"],
                    "fired_on_drop": drop["fired_on_drop"],
                    "mutant_reason": drop["mutant_reason"],
                    "base_surviving": drop["base_surviving"],
                    "mutant_surviving": drop["mutant_surviving"],
                },
                "ratio_units": {
                    "ok": ratio["ok"],
                    "unit": ratio["unit"],
                    "diverges_from_bytes": ratio["diverges_from_bytes"],
                    "corpus_ratio": ratio["corpus_ratio"],
                    "byte_corpus_ratio": ratio["byte_corpus_ratio"],
                },
            },
            sort_keys=True,
        )
    )
    if not drop.get("silent_on_full"):
        return fail("full synthesis already dropped the pin; control is not both-states")
    if not drop.get("fired_on_drop"):
        return fail(f"removing {PIN_REFUTED_ID} from synthesis was not reported")
    if not drop.get("ok"):
        return fail("planted-drop control failed")
    if not ratio.get("diverges_from_bytes"):
        return fail("byte-weighted ratio equals record ratio; padding control is inert")
    if not ratio.get("ok"):
        return fail("ratio-units control failed")

    art = REPO / OUT_REL
    if not art.is_file():
        return fail("artifact missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    ok, why = O.check_overclaim(doc)
    if not ok:
        return fail(f"overclaim {why}")
    payload = O.domain(doc)
    if (payload.get("ratios") or {}).get("unit") != "record":
        return fail("artifact ratios.unit is not record")
    if (payload.get("ratios") or {}).get("byte_weighted_refused") is not True:
        return fail("artifact did not refuse byte-weighted ratios")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("planted-drop", "ratio-over-records-not-bytes"):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    nc = doc.get("negative_controls") or payload.get("controls") or []
    planted_ok = any(
        isinstance(x, dict)
        and x.get("id") == "planted-drop"
        and (
            x.get("result") == "PASS"
            or (
                x.get("fired_on_bad_state") is True
                and x.get("silent_on_good_state") is True
            )
        )
        for x in nc
    )
    if not planted_ok:
        return fail("artifact missing planted-drop PASS control")

    print(
        "fired_on_drop=True silent_on_full=True "
        f"record_ratio={ratio['corpus_ratio']} "
        f"byte_ratio={ratio['byte_corpus_ratio']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 planted drop reported; ratios are record units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
