#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0028.option-closure.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import close as C  # noqa: E402

OUT = C.REPO / C.OUTPUT_REL


def main() -> int:
    doc = C.close(C.REPO)
    ok, why = C.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:SYN-0028-emit schema {why}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0028-emit state={doc.get('state')} class={(doc.get('extensions') or {}).get('failure_classification')}")
        return 1
    pack = C.payload(doc)
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True)
    if C.SENTINEL not in text:
        print("FAILED:SYN-0028-emit sentinel absent")
        return 1
    if not pack.get("counts_sum_equals_selected"):
        print("FAILED:SYN-0028-emit counts do not sum to selected-set size")
        return 1
    if not pack.get("no_bare_ambiguous_token_assigned_a_state"):
        print("FAILED:SYN-0028-emit bare ambiguous token assigned a state")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    live_sha, live_bytes = C.SL.digest_file(OUT)
    doc["artifacts"][0]["sha256"] = live_sha
    doc["artifacts"][0]["bytes"] = live_bytes
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    ok2, why2 = C.validate_against_schema(json.loads(OUT.read_text(encoding="utf-8")))
    if not ok2:
        print(f"FAILED:SYN-0028-emit rewritten schema {why2}")
        return 1
    print(
        f"wrote {C.OUTPUT_REL} bytes={OUT.stat().st_size} "
        f"state={doc['state']} n={pack.get('selected_set_size')} "
        f"source={pack.get('selected_set_source')}"
    )
    print("SUCCESS:SYN-0028-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
