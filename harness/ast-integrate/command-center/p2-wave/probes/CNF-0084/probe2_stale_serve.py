#!/usr/bin/env python3
"""Named probe 2: detector controls on known-broken cache fixtures.

Must fire on:
  1. not-in-key sidecar mutation -> stale serve
  2. path-derived key after content mutation -> unsound + stale serve
  3. empty store reporting a hit
Live flags are compared to the confirmation artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL


def by_id(rows: list) -> dict:
    return {r["id"]: r for r in rows if isinstance(r, dict) and r.get("id")}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0084-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != H.UNIT:
        print("FAILED:CNF-0084-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0084-probe2 self-declared {doc.get('state')}")
        return 1

    stale = H.not_in_key_stale_serve()
    path_key = H.path_key_unsound()
    empty = H.empty_cache_hit()
    payload = H.domain_from_doc(doc)
    recorded = by_id(list(payload.get("detector_controls") or []))

    failures = []
    if not stale["fired"]:
        failures.append("not-in-key-did-not-fire")
    if not path_key["fired"] or not path_key["reported_unsound"]:
        failures.append("path-key-did-not-fire")
    if not empty["fired"]:
        failures.append("empty-hit-did-not-fire")

    rec_stale = recorded.get("not-in-key-stale-serve") or {}
    rec_path = recorded.get("path-not-content-key") or {}
    rec_empty = recorded.get("empty-cache-hit") or {}
    if rec_stale.get("fired") is not True:
        failures.append("artifact-stale-not-recorded")
    if rec_path.get("fired") is not True:
        failures.append("artifact-path-not-recorded")
    if rec_empty.get("fired") is not True:
        failures.append("artifact-empty-not-recorded")
    if rec_stale.get("cold_sha256") != stale["cold_sha256"]:
        failures.append("stale-cold-sha-drift")
    if rec_stale.get("warm_sha256") != stale["warm_sha256"]:
        failures.append("stale-warm-sha-drift")
    if rec_path.get("cold_cache_key") != path_key["cold_cache_key"]:
        failures.append("path-key-drift")

    findings = payload.get("findings") or {}
    if findings.get("stale_serve_on_not_in_key_recorded") is not True:
        failures.append("findings-stale-missing")
    if findings.get("path_key_reported_unsound") is not True:
        failures.append("findings-path-missing")
    if findings.get("empty_cache_hit_probed") is not True:
        failures.append("findings-empty-missing")

    out = {
        "probe": "probe2-detector-controls",
        "unit_id": H.UNIT,
        "stale_serve_detected": stale["stale_serve_detected"],
        "path_key_unsound": path_key["reported_unsound"],
        "empty_hit_fired": empty["fired"],
        "failures": failures,
        "pass": not failures,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"not-in-key fired={stale['fired']} keys_unchanged={stale['keys_unchanged']} "
        f"stale={stale['stale_serve_detected']}"
    )
    print(
        f"path-key fired={path_key['fired']} unsound={path_key['reported_unsound']} "
        f"stale={path_key['stale_serve_detected']}"
    )
    print(f"empty-hit fired={empty['fired']} broken_hit={empty['broken_claimed_hit']}")
    if failures:
        print("FAILED:CNF-0084-probe2", ",".join(failures))
        return 1
    print("SUCCESS:CNF-0084-probe2 detector controls fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
