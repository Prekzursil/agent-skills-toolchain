#!/usr/bin/env python3
"""Probe 2: git config --get-regexp ^remote. plus independence vs probe 1.

Does not treat git remote -v emptiness as sufficient. The url-less plant must
be visible here and invisible as a URL under probe 1. If both report the same
on that plant, the pair is not independent.
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
        print("FAILED:AUD-0007-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if L.SENTINEL not in text:
        print("FAILED:AUD-0007-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:AUD-0007-probe2 self-declared {st}")
        return 1
    errs = L.validate_doc(doc)
    if errs:
        print("FAILED:AUD-0007-probe2 schema", errs[0])
        return 1

    ctl = L.independence_control()
    if not ctl["pass"]:
        print("FAILED:AUD-0007-probe2 independence control")
        print(json.dumps({k: {
            "p1": v["probe1_no_remote"],
            "p2": v["probe2_has_remote_config"],
            "class": v["classification"],
        } for k, v in ctl["plants"].items()}, sort_keys=True))
        return 1
    if ctl["same_fingerprint_on_url_less_plant"]:
        print("FAILED:AUD-0007-probe2 both probes report the same on url-less plant")
        return 1

    plant = ctl["plants"]["url-less-fetch"]
    if not (plant["probe1_no_remote"] and plant["probe2_has_remote_config"]):
        print("FAILED:AUD-0007-probe2 url-less plant did not disagree")
        return 1
    if "remote.origin.fetch" not in plant["probe2_raw"]:
        print("FAILED:AUD-0007-probe2 expected fetch key in config output")
        return 1

    inv = L.live_inventory()
    art_report = doc.get("report") or {}
    counts = art_report.get("counts") if isinstance(art_report.get("counts"), dict) else {}
    if "probe1_empty_probe2_config" not in counts:
        print("FAILED:AUD-0007-probe2 counts.probe1_empty_probe2_config missing")
        return 1
    art_dis = int(counts["probe1_empty_probe2_config"])
    live_dis = inv["counts"]["probe1_empty_probe2_config"]
    if art_dis != live_dis:
        print(
            f"FAILED:AUD-0007-probe2 disagreement count drift art={art_dis} live={live_dis}"
        )
        return 1

    live_by = {r["path"]: r for r in inv["repos"]}
    for row in art_report.get("repos") or []:
        live = live_by.get(row.get("path"))
        if live is None:
            print("FAILED:AUD-0007-probe2 missing live repo", row.get("path"))
            return 1
        if bool(row.get("probe2_has_remote_config")) != bool(live["probe2_has_remote_config"]):
            print("FAILED:AUD-0007-probe2 config drift", row.get("path"))
            return 1
        live_class = L.classify(
            {"no_remote": live["probe1_no_remote"]},
            {"has_remote_config": live["probe2_has_remote_config"]},
        )
        if row.get("classification") != live_class:
            print(
                "FAILED:AUD-0007-probe2 classification drift",
                row.get("path"),
                row.get("classification"),
                live_class,
            )
            return 1

    named = doc.get("named_probes") or []
    blob = json.dumps(named)
    if "get-regexp" not in blob and r"^remote" not in blob:
        print("FAILED:AUD-0007-probe2 named probe 2 missing config regexp output")
        return 1

    no_remote = [r for r in inv["repos"] if r["classification"] == "no-remote"]
    payload = {
        "probe": "probe2-config-regexp",
        "unit_id": L.UNIT,
        "independent": ctl["independent"],
        "url_less_p1_no_remote": plant["probe1_no_remote"],
        "url_less_p2_has_config": plant["probe2_has_remote_config"],
        "live_no_remote": len(no_remote),
        "live_disagreement": live_dis,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0007-probe2 git config --get-regexp remote "
        f"independent={ctl['independent']} disagreement={live_dis}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
