#!/usr/bin/env python3
"""Probe 1: artifact structure + live dual-rail re-fetch."""
from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402
import emit_teardown as E  # noqa: E402
import grade as G  # noqa: E402

ART = REPO / "command-center/research/RES-0120.json"
# Avoid api.github.com on re-run (unauthenticated 60/hr). npm + docs + raw GitHub still live.
LIVE_IDS = ("npm-registry", "docs-overview", "docs-plugins", "github-marketplace-json")


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0120-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check(doc, REPO)
    print(f"structure_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0120-probe1 structure")
        return 1

    src_by_id = {s["id"]: s for s in E.SOURCES}
    for sid in LIVE_IDS:
        src = src_by_id[sid]
        try:
            status, final, body = E.fetch(src["url"], src["accept"])
        except urllib.error.HTTPError as exc:
            print(f"FAILED:RES-0120-probe1 live {sid} HTTPError {exc.code}")
            return 1
        stored = E.strip_html(body) if src.get("strip_html") else body
        text = stored.decode("utf-8", "replace")
        print(f"live {sid} status={status} final={final} bytes={len(stored)}")
        if status != 200:
            print(f"FAILED:RES-0120-probe1 live {sid} status={status}")
            return 1
        if sid == "npm-registry" and "@anthropic-ai/claude-code" not in text:
            print("FAILED:RES-0120-probe1 npm name missing")
            return 1
        if sid == "docs-overview" and "Homebrew" not in text:
            print("FAILED:RES-0120-probe1 overview missing Homebrew")
            return 1
        if sid == "docs-plugins" and "plugin.json" not in text:
            print("FAILED:RES-0120-probe1 plugins doc missing plugin.json")
            return 1
        if sid == "github-marketplace-json" and "claude-code-plugins" not in text:
            print("FAILED:RES-0120-probe1 marketplace.json missing name")
            return 1

    e3 = next(c for c in doc["claims"] if c.get("id") == "C-E3-CONTROL")
    if G.grade_claim(e3) != G.SINGLE or G.cited_as_measured(e3):
        print("FAILED:RES-0120-probe1 E3 control misgraded")
        return 1
    print("e3_control_ok=True")
    print("SUCCESS:RES-0120-probe1 live rails and dual-rail structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
