#!/usr/bin/env python3
"""Probe 2: semantic unique-line read of the 3 live-larger files and the 25 repo-larger.

Timestamps alone cannot tell a deploy artefact from authored content. This
probe reads the unique lines and checks the catalog-pinned byte deltas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adjudicate import adjudicate
from corpus import build
from paths import LIVE_LARGER, REPO_RULES, LIVE_RULES, UNIT


def main() -> int:
    build()
    adj = adjudicate()
    live_names = [p for p, _, _ in LIVE_LARGER]
    want_delta = {p: d for p, d, _ in LIVE_LARGER}
    live_rows = [r for r in adj["content_differing"] if r["path"] in set(live_names)]
    repo_rows = [r for r in adj["content_differing"] if r["path"] not in set(live_names)]

    live_ok = []
    for r in live_rows:
        rel = r["path"]
        delta = r["size_delta_live_minus_repo"]
        unique = r["live_unique_lines"]
        tag = rel.split("/")[-1].replace(".md", "")
        has_unique = any("LIVE-UNIQUE:" in line for line in unique)
        live_ok.append(
            {
                "path": rel,
                "shape": r["shape"],
                "authoritative": r["authoritative"],
                "delta": delta,
                "want_delta": want_delta[rel],
                "delta_ok": delta == want_delta[rel],
                "unique_line_count": len(unique),
                "has_live_unique_marker": has_unique,
                "unique_preview": [u[:96] for u in unique[:3]],
                "ok": (
                    r["shape"] == "LIVE-SUPERSET"
                    and r["authoritative"] == "LIVE"
                    and delta == want_delta[rel]
                    and has_unique
                ),
            }
        )

    repo_ok = []
    for r in repo_rows:
        unique = r["repo_unique_lines"]
        has_unique = any("REPO-UNIQUE:" in line for line in unique)
        repo_ok.append(
            {
                "path": r["path"],
                "shape": r["shape"],
                "authoritative": r["authoritative"],
                "repo_bytes": r["repo_bytes"],
                "live_bytes": r["live_bytes"],
                "unique_line_count": len(unique),
                "has_repo_unique_marker": has_unique,
                "unique_preview": [u[:96] for u in unique[:2]],
                "ok": (
                    r["shape"] == "REPO-SUPERSET"
                    and r["authoritative"] == "REPO"
                    and has_unique
                    and (r["repo_bytes"] or 0) > (r["live_bytes"] or 0)
                ),
            }
        )

    windows = next((x for x in repo_ok if x["path"] == "common/windows-shell.md"), None)
    windows_mentions_drive = False
    if windows:
        text = (REPO_RULES / "common/windows-shell.md").read_text(encoding="utf-8")
        windows_mentions_drive = "C:\\Users\\Prekzursil" in text

    ok = (
        len(live_ok) == 3
        and all(x["ok"] for x in live_ok)
        and len(repo_ok) == 25
        and all(x["ok"] for x in repo_ok)
        and windows_mentions_drive
        and [x["path"] for x in live_ok] == live_names
    )
    doc = {
        "probe": "probe2-semantic-hunks",
        "unit_id": UNIT,
        "ok": ok,
        "live_larger": live_ok,
        "repo_larger_count": len(repo_ok),
        "repo_larger_sample": repo_ok[:8],
        "repo_larger_all_ok": all(x["ok"] for x in repo_ok),
        "windows_shell_drive_qualified_in_repo_unique": windows_mentions_drive,
        "note": (
            "Byte deltas are recorded as a catalog pin, not as the authority "
            "signal. Authority is unique-line direction plus newer timestamp."
        ),
    }
    print(json.dumps(doc, indent=2, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe2 semantic hunks")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 semantic hunks of 3 live-larger and 25 repo-larger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
