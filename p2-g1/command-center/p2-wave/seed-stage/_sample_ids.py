#!/usr/bin/env python3
"""Build a stratified harvest-proof ID list."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
OUT = WAVE / "ovh-monitor" / "local-sample-ids.json"
DETAILS = WAVE / "ovh-monitor" / "error-pull" / "g1-fail-details.json"
LEFTOVER = json.loads((WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json").read_text(encoding="utf-8"))["remaining_ids"]
PRIOR = json.loads((WAVE / "P2-PRIOR-281_2026-08-24.json").read_text(encoding="utf-8"))["remaining_ids"]

fail58 = [r["id"] for r in json.loads(DETAILS.read_text(encoding="utf-8")).get("rows") or [] if not r.get("ok")]
ids = []
seen = set()


def add(uid: str) -> None:
    if uid and uid not in seen:
        seen.add(uid)
        ids.append(uid)


add("BLD-0055")
add("WFA-0001")
for uid in fail58:
    add(uid)

by_pref: dict[str, list[str]] = defaultdict(list)
for uid in LEFTOVER + PRIOR:
    by_pref[uid.split("-")[0]].append(uid)
for pref, group in sorted(by_pref.items()):
    n = 0
    for uid in group:
        if uid in seen:
            continue
        add(uid)
        n += 1
        if n >= 2:
            break

OUT.write_text(json.dumps({"n": len(ids), "ids": ids}, indent=2) + "\n", encoding="utf-8")
print(len(ids))
print(" ".join(ids[:20]), "...")
