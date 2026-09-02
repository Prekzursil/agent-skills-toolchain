#!/usr/bin/env python3
"""IMP-0468 probe 1: planted-collision control and nested-object coverage.

Loads fixtures from disk (not only in-memory dicts) so a detector that only
walks a hand-built object cannot pass. A zero shipped-scan is untrusted until
this probe exits 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import case_collision as cc  # noqa: E402

FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0468-probe1 {msg}")
    return 1


def main() -> int:
    planted = cc.detect_file(FIX / "planted-collision.json", repo=HERE)
    if not planted["parse_ok"]:
        return fail(f"planted unreadable {planted['error']}")
    if not planted["signals_agree"]:
        return fail("planted walk/pairs signal disagreement")
    hits = planted["walk_hits"]
    if len(hits) != 1:
        return fail(f"planted hit_count={len(hits)} want=1 {hits}")
    if set(hits[0]["keys"]) != {"Name", "name"}:
        return fail(f"planted keys={hits[0]['keys']}")
    if hits[0]["json_path"] != "$":
        return fail(f"planted path={hits[0]['json_path']}")
    if "producer-kept-title-case" not in hits[0]["values"]["Name"]:
        return fail(f"planted Name value missing {hits[0]['values']}")
    if "producer-kept-lower-case" not in hits[0]["values"]["name"]:
        return fail(f"planted name value missing {hits[0]['values']}")

    consumer = cc.simulate_casefold_consumer(
        json.loads((FIX / "planted-collision.json").read_text(encoding="utf-8"))
    )
    if not consumer["silent_loss"]:
        return fail("casefold consumer did not drop a key — detector has no hazard")
    if consumer["input_key_count"] != 3 or consumer["kept_count"] != 2:
        return fail(f"consumer counts {consumer}")

    nested = cc.detect_file(FIX / "nested-collision.json", repo=HERE)
    if not nested["parse_ok"] or not nested["signals_agree"]:
        return fail(f"nested parse/signals {nested}")
    nh = nested["walk_hits"]
    if len(nh) != 1:
        return fail(f"nested hit_count={len(nh)} want=1 (top-level-only detector?) {nh}")
    if not str(nh[0]["json_path"]).endswith("inner"):
        return fail(f"nested path not inner: {nh[0]['json_path']}")
    if set(nh[0]["keys"]) != {"Host", "host"}:
        return fail(f"nested keys={nh[0]['keys']}")
    if "title-case-host" not in nh[0]["values"]["Host"]:
        return fail(f"nested Host value {nh[0]['values']}")
    if "lower-case-host" not in nh[0]["values"]["host"]:
        return fail(f"nested host value {nh[0]['values']}")

    clean = cc.detect_file(FIX / "clean.json", repo=HERE)
    if not clean["parse_ok"]:
        return fail(f"clean unreadable {clean['error']}")
    if clean["walk_hits"]:
        return fail(f"clean should be silent {clean['walk_hits']}")

    id_hit = cc.detect_file(FIX / "id-case-collision.json", repo=HERE)
    if len(id_hit["walk_hits"]) != 1 or set(id_hit["walk_hits"][0]["keys"]) != {"ID", "id"}:
        return fail(f"ID/id must fire {id_hit['walk_hits']}")

    print(
        json.dumps(
            {
                "planted_hits": 1,
                "nested_path": nh[0]["json_path"],
                "consumer_silent_loss": True,
                "clean_silent": True,
                "id_id_fires": True,
                "signals_agree": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0468-probe1 planted-collision and nested-object coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
