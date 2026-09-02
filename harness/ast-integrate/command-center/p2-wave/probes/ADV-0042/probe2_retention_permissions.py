#!/usr/bin/env python3
"""Probe 2: on-disk retention, permissions, extra-surface occupancy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:ADV-0042-probe2 {msg}")
    return 1


def main() -> int:
    m = L.live_measurement()
    report = L.probe2_report(m)
    print(report, end="")
    cap = m["capture"]
    if not cap["world_readable_mutant_fires"]:
        return fail("0644 planted capture was not flagged")
    if not cap["extra_surface_mutant_fires"]:
        return fail("extra-surface file labeled window-scoped was not flagged")
    if not cap["owner_only_good_files"]:
        return fail("a non-mutant capture was group/other-readable")
    if cap["personal_application_captured"]:
        return fail("a personal application was captured")
    payload = L.probe2_payload(m)
    window_file = None
    screen_file = None
    world_file = None
    extra_file = None
    for row in payload["files"]:
        name = row["path"].rsplit("/", 1)[-1]
        if name == "S2_printwindow_full_occlusion.png":
            window_file = row
        elif name == "S2_copyfromscreen_full_occlusion.png":
            screen_file = row
        elif name == "world_readable.png":
            world_file = row
        elif name == "extra_surface_labeled_window.png":
            extra_file = row
    if window_file is None or screen_file is None:
        return fail("expected capture pngs missing from disk enumerate")
    if window_file["occluder_pixel_share"] > 0.02:
        return fail("window-scoped file stored occluder pixels", window_file)
    if window_file["target_pixel_share"] < 0.98:
        return fail("window-scoped file is not the synthetic target", window_file)
    if screen_file["occluder_pixel_share"] < 0.98:
        return fail("screen-scoped file did not store the occluder", screen_file)
    if world_file is None or not world_file["world_or_group_readable"]:
        return fail("world-readable mutant missing or not readable")
    if extra_file is None or extra_file["occluder_pixel_share"] < 0.98:
        return fail("extra-surface mutant missing or not occluder-majority")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if L.SENTINEL not in text:
        return fail("sentinel-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer-gate", reviewer)
    controls = {c["id"]: c for c in doc.get("negative_controls") or []}
    for cid in (
        "planted-world-readable-capture",
        "planted-extra-surface-labeled-window",
    ):
        row = controls.get(cid)
        if not row or not row.get("fired_on_bad_state") or not row.get("silent_on_good_state"):
            return fail(f"control-not-both-states:{cid}", row)
    print("SUCCESS:ADV-0042-probe2 retention-permissions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
