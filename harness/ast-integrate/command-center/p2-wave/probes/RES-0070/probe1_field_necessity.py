#!/usr/bin/env python3
"""Probe 1: every cache-key field is justified and omitting it collides two distinct steps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rails import verify_all  # noqa: E402
from spec import FIELD_IDS  # noqa: E402
from suite import field_necessity  # noqa: E402

ART = REPO / "command-center/research/RES-0070.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
P1_RAILS = [
    "bazel-remote-caching",
    "bazel-hermeticity",
    "gh-bazel-spawn-action-raw",
    "gh-bazel-abstract-action-raw",
    "nix-input-address",
    "gh-nix-derivations-raw",
]


def main() -> int:
    nec = field_necessity()
    print(json.dumps({k: nec[k] for k in ("pass", "field_count", "stable_across_calls")}, sort_keys=True))
    if not nec["pass"]:
        print("FAILED:RES-0070-probe1 field-necessity")
        print(json.dumps(nec, indent=2)[:4000])
        return 1
    for row in nec["fields"]:
        print(
            f"  field {row['id']} differ={row['keys_differ_when_field_present']} "
            f"omit_collides={row['keys_collide_when_field_omitted']}"
        )
        if not row["ok"]:
            print("FAILED:RES-0070-probe1 field did not prove necessity:", row["id"])
            return 1

    rails = verify_all(P1_RAILS)
    bad = [r for r in rails if not r.get("ok")]
    if bad:
        print("FAILED:RES-0070-probe1 rails", json.dumps(bad)[:2000])
        return 1
    print(f"rails_ok={len(rails)}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print(f"FAILED:RES-0070-probe1 self-declared {doc.get('state')}")
            return 1
        spec = doc.get("cache_key_specification") or {}
        ids = [f.get("id") for f in (spec.get("fields") or []) if isinstance(f, dict)]
        missing = [i for i in FIELD_IDS if i not in ids]
        if missing:
            print("FAILED:RES-0070-probe1 artifact missing fields", missing)
            return 1
        for f in spec.get("fields") or []:
            just = str(f.get("justification") or "")
            if len(just) < 24:
                print("FAILED:RES-0070-probe1 unjustified field", f.get("id"))
                return 1
        sent = str(doc.get("sentinel") or "")
        if "SUCCESS:RES-0070" not in sent and "SUCCESS:RES-0070" not in json.dumps(doc):
            print("FAILED:RES-0070-probe1 sentinel absent")
            return 1
        blob = json.dumps(doc)
        if "field-by-field cache-key specification" not in blob:
            print("FAILED:RES-0070-probe1 specification phrase absent")
            return 1
    print("SUCCESS:RES-0070-probe1 field-by-field cache-key necessity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
