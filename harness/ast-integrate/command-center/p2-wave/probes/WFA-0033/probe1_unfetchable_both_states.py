#!/usr/bin/env python3
"""Probe 1: unfetchable stays UNCLASSIFIED; fetchable MIT is classified (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0033-probe1 {msg}")
    return 1


def main() -> int:
    mit_node = {
        "id": "ctrl-fetchable-mit",
        "name": "control-mit",
        "old_class": "THIRD-PARTY",
        "host_declared_spdx": "MIT",
        "host_declared_source": "host-declared-licence-metadata-field",
        "fetchable": True,
        "license_file": "SPDX-MIT.txt",
        "retrieval_anchor": "https://spdx.org/licenses/MIT.txt",
        "retrieval_date": C.RETRIEVED,
        "origin": "control://mit",
    }
    dead_node = {
        "id": "ctrl-unfetchable",
        "name": "control-dead",
        "old_class": "UNCLASSIFIED",
        "host_declared_spdx": "MIT",  # host metadata must not rescue a missing file
        "host_declared_source": "host-declared-licence-metadata-field",
        "fetchable": False,
        "license_file": None,
        "retrieval_anchor": "https://127.0.0.1:1/LICENSE",
        "retrieval_date": None,
        "origin": "https://127.0.0.1:1/LICENSE",
    }

    good = E.extract_node(mit_node, C.disk_fetcher(mit_node))
    bad = E.extract_node(dead_node, C.disk_fetcher(dead_node))

    if good["new_class"] != E.PERMISSIVE or good["spdx"] != "MIT":
        return fail(f"fetchable MIT not PERMISSIVE/MIT: {good['new_class']} {good['spdx']}")
    if not good["fetch_ok"]:
        return fail("fetchable MIT marked unfetchable")
    if bad["new_class"] != E.UNCLASSIFIED:
        return fail(f"unfetchable classified {bad['new_class']} (must stay UNCLASSIFIED)")
    if bad["new_class"] == E.PERMISSIVE:
        return fail("unfetchable defaulted to PERMISSIVE")
    if not bad["escalated"]:
        return fail("unfetchable not escalated")
    if bad["fetch_ok"]:
        return fail("unfetchable marked fetch_ok")
    # Host MIT metadata is signal B only; it must not become new_class.
    if bad["signal_b_spdx"] != "MIT":
        return fail("signal B dropped on unfetchable node")
    if bad["new_class"] == bad["signal_b_spdx"]:
        return fail("host metadata used as classification for unfetchable node")
    if good["inadmissible_signal"] != "graph-rule-based-old_class-not-used":
        return fail("old_class not tagged inadmissible")

    # Live cohort: the planted unreachable node in the 41.
    live_dead = E.extract_node(C.unclassified_node(), C.disk_fetcher(C.unclassified_node()))
    if live_dead["new_class"] != E.UNCLASSIFIED or not live_dead["escalated"]:
        return fail("cohort unreachable node not UNCLASSIFIED")

    payload = {
        "both_states": {
            "good": {
                "id": good["id"],
                "new_class": good["new_class"],
                "spdx": good["spdx"],
                "fetch_ok": True,
            },
            "bad": {
                "id": bad["id"],
                "new_class": bad["new_class"],
                "escalated": True,
                "fetch_ok": False,
                "not_permissive": bad["new_class"] != E.PERMISSIVE,
            },
        },
        "pass": True,
        "probe": "probe1-unfetchable-both-states",
        "unit_id": "WFA-0033",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:WFA-0033-probe1 unfetchable stays UNCLASSIFIED; fetchable MIT classifies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
