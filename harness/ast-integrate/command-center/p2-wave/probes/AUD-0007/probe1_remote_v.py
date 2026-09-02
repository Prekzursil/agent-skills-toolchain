#!/usr/bin/env python3
"""Probe 1: git remote -v URL emptiness per repo, plus url-less plant.

Does not read git config --get-regexp. That is probe 2's data field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0007-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if L.SENTINEL not in text:
        print("FAILED:AUD-0007-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:AUD-0007-probe1 self-declared {st}")
        return 1
    if doc.get("unit_id") != L.UNIT:
        print("FAILED:AUD-0007-probe1 unit_id")
        return 1
    errs = L.validate_doc(doc)
    if errs:
        print("FAILED:AUD-0007-probe1 schema", errs[0])
        return 1

    ctl = L.independence_control()
    plant = ctl["plants"]["url-less-fetch"]
    true_nr = ctl["plants"]["true-noremote"]
    url_remote = ctl["plants"]["fetch-less-url"]

    # Probe 1 claims: url-less plant has no URL; virgin repo has no URL;
    # URL-only remote DOES have a URL.
    p1_ok = (
        plant["probe1_no_remote"] is True
        and true_nr["probe1_no_remote"] is True
        and url_remote["probe1_no_remote"] is False
    )
    if not p1_ok:
        print("FAILED:AUD-0007-probe1 control plants")
        print(json.dumps({k: ctl["plants"][k]["probe1_no_remote"] for k in ctl["plants"]}))
        return 1

    inv = L.live_inventory()
    art_report = doc.get("report") or {}
    counts = art_report.get("counts") if isinstance(art_report.get("counts"), dict) else {}
    if "confirmed_worktrees" not in counts:
        print("FAILED:AUD-0007-probe1 counts.confirmed_worktrees missing")
        return 1
    art_n = int(counts["confirmed_worktrees"])
    live_n = inv["counts"]["confirmed_worktrees"]
    if art_n != live_n:
        print(f"FAILED:AUD-0007-probe1 worktree count drift art={art_n} live={live_n}")
        return 1

    live_by = {r["path"]: r for r in inv["repos"]}
    for row in art_report.get("repos") or []:
        live = live_by.get(row.get("path"))
        if live is None:
            print("FAILED:AUD-0007-probe1 missing live repo", row.get("path"))
            return 1
        if bool(row.get("probe1_no_remote")) != bool(live["probe1_no_remote"]):
            print("FAILED:AUD-0007-probe1 no_remote drift", row.get("path"))
            return 1
        if int(row.get("probe1_url_count")) != int(live["probe1_url_count"]):
            print("FAILED:AUD-0007-probe1 url_count drift", row.get("path"))
            return 1

    named = doc.get("named_probes") or []
    if len(named) < 2 or "git remote -v" not in json.dumps(named[0]):
        print("FAILED:AUD-0007-probe1 named probe 1 missing remote -v output")
        return 1

    payload = {
        "probe": "probe1-remote-v",
        "unit_id": L.UNIT,
        "confirmed_worktrees": live_n,
        "probe1_no_remote_live": sum(1 for r in inv["repos"] if r["probe1_no_remote"]),
        "url_less_plant_no_remote": plant["probe1_no_remote"],
        "fetch_less_url_no_remote": url_remote["probe1_no_remote"],
        "true_noremote": true_nr["probe1_no_remote"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0007-probe1 git remote -v URL emptiness "
        f"worktrees={live_n} url-less-plant-no-remote={plant['probe1_no_remote']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
