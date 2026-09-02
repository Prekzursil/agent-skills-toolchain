#!/usr/bin/env python3
"""Probe 2: unrecoverable-count control (mechanically different from probe 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from recover import (  # noqa: E402
    after_claim_synthetic_rejected,
    build_recovery_table,
    live_control_ok,
    load_artifact,
    load_corpus,
    unrecoverable_rows,
)

PLANTED_URL = "https://res-0117-never-archived.invalid/deleted-prior-art"
LIVE_CTRL = "https://code.claude.com/docs/en/overview"


def main() -> int:
    corpus = load_corpus()
    table = build_recovery_table(corpus)
    doc = load_artifact()
    dead = unrecoverable_rows(table)
    art_count = doc.get("unrecoverable_link_count")
    errs: list[str] = []

    if art_count != len(dead):
        errs.append(f"count mismatch artifact={art_count} recomputed={len(dead)}")
    if len(dead) < 1:
        errs.append("control failed: zero unrecoverable rows")

    planted_ids = [
        r.get("id")
        for r in dead
        if r.get("planted_control") is True and r.get("url") == PLANTED_URL
    ]
    if not planted_ids:
        errs.append("planted never-archived URL not in unrecoverable set")

    if any(r.get("url") == LIVE_CTRL for r in dead):
        errs.append("live control counted unrecoverable")
    if not live_control_ok(corpus):
        errs.append("live control fixture not 200")

    ctrl = corpus.get("live_control") or {}
    if str((ctrl.get("live") or {}).get("final_url") or "") != LIVE_CTRL:
        errs.append("live control URL drift")
    if LIVE_CTRL in {r.get("url") for r in table}:
        errs.append("live control leaked into dead/moved recovery table")

    if not after_claim_synthetic_rejected():
        errs.append("mutant post-claim snapshot was treated as usable read-proof")

    if doc.get("recovered_artifact_changes_any_conclusion") is True:
        errs.append("artifact overclaims a conclusion change")

    hub = next((r for r in table if r.get("id") == "DL-HUB-001"), None)
    if hub is None or hub.get("unrecoverable") is True:
        errs.append("hub row missing or already unrecoverable")
    else:
        mutant_links = []
        for link in corpus["links"]:
            item = dict(link)
            if item.get("id") == "DL-HUB-001":
                item["cdx"] = []
            mutant_links.append(item)
        mutant_table = build_recovery_table(
            {"links": mutant_links, "live_control": ctrl}
        )
        mutant_hub = next(r for r in mutant_table if r.get("id") == "DL-HUB-001")
        if mutant_hub.get("unrecoverable") is not True:
            errs.append("hub without CDX was not counted unrecoverable")
        if len(unrecoverable_rows(mutant_table)) <= len(dead):
            errs.append("stripping hub CDX did not raise unrecoverable count")

    payload = {
        "unrecoverable_ids": [r.get("id") for r in dead],
        "unrecoverable_link_count": len(dead),
        "planted": planted_ids,
        "after_claim_mutant_rejected": after_claim_synthetic_rejected(),
        "errors": errs,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if errs:
        print("FAILED:RES-0117-probe2 " + "; ".join(errs[:8]))
        return 1
    print(
        "SUCCESS:RES-0117-probe2 unrecoverable="
        f"{len(dead)} planted=1 post-claim-mutant-rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
