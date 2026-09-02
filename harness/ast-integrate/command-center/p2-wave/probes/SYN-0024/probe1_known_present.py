#!/usr/bin/env python3
"""Probe 1: a recorded REFUTED claim must be found by the extractor at source."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import controls as C  # noqa: E402
import jsonschema  # noqa: E402
import overclaim as O  # noqa: E402
from paths import CATALOG_SENTINEL, OUT_REL, PIN_REFUTED_ID, REPO, SCHEMA_REL, UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    kp = C.known_present()
    print(
        json.dumps(
            {
                "probe": "probe1-known-present",
                "ok": kp["ok"],
                "id": kp["id"],
                "found": kp["found"],
                "hit_raw": kp["hit_raw"],
                "source_negative_ids": kp["source_negative_ids"],
            },
            sort_keys=True,
        )
    )
    if not kp["ok"]:
        return fail(f"extractor missed {PIN_REFUTED_ID} REFUTED at source")

    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    ok, why = O.check_overclaim(doc)
    if not ok:
        return fail(f"overclaim {why}")

    src_ids = {
        r.get("id")
        for r in (doc.get("source_negatives") or [])
        if isinstance(r, dict)
    }
    if PIN_REFUTED_ID not in src_ids:
        return fail("artifact source_negatives missing pin REFUTED id")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("known-present-refuted", {}).get("result") != "PASS":
        return fail("artifact test known-present-refuted not PASS")

    print(
        f"found={PIN_REFUTED_ID} raw=REFUTED "
        f"source_negatives={kp['source_count']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 known-present REFUTED extracted at source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
