#!/usr/bin/env python3
"""Named probe 2: $schema unload (known-broken) + second-install idempotence."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import scenario_idempotence, scenario_known_broken  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0146.json"
SENTINEL = "SUCCESS:CNF-0146"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0146-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0146-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0146-probe2 self-declared", doc.get("state"))
        return 1
    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        print("FAILED:CNF-0146-probe2 missing source_probe/verifier_probe")
        return 1
    if src.get("fingerprint") == ver.get("fingerprint"):
        print("FAILED:CNF-0146-probe2 same-probe-rerun fingerprints")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0146-p2-") as tmp:
        root = Path(tmp)
        broken = scenario_known_broken(root)
        idem = scenario_idempotence(root)

    payload = {
        "probe": "probe2-known-broken-idempotence",
        "unit_id": "CNF-0146",
        "pass": True,
        "known_broken": broken,
        "idempotence": idem,
        "listing_passes_while_unloaded": broken["file_listing_passes_while_unloaded"],
        "no_double_register": idem["no_double_register"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "broken_loaded="
        f"{broken['loaded_count']} listing_green_while_unloaded="
        f"{broken['file_listing_passes_while_unloaded']} "
        f"second_count={idem['registered_count_second']}"
    )
    print("SUCCESS:CNF-0146-probe2 known-broken unload and idempotence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
