#!/usr/bin/env python3
"""Probe 1: live three-route comparison + LF-normalisation control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import blobread as br  # noqa: E402

ART = REPO / "command-center/receipts/TST-0334.json"
OUT = HERE / "probe1-three-routes.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0334-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0334" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    live = br.live_measure()
    by = {row["route"]: row for row in live["byte_table"]}
    for name in ("git archive", "git cat-file", "worktree"):
        if name not in by:
            return fail(f"missing route {name}")

    arch, cat, tree = by["git archive"], by["git cat-file"], by["worktree"]
    print(
        f"archive bytes={arch['bytes']} crlf={arch['crlf_count']} "
        f"cat-file bytes={cat['bytes']} crlf={cat['crlf_count']} "
        f"worktree bytes={tree['bytes']} crlf={tree['crlf_count']} "
        f"lines={cat['line_count']}"
    )
    if arch["crlf_count"] <= 0:
        return fail("git archive did not return CRLF")
    if cat["crlf_count"] != 0:
        return fail("cat-file blob is not LF")
    if tree["crlf_count"] <= 0:
        return fail("eol=crlf worktree did not materialise CRLF")
    if cat["line_count"] != br.KNOWN_LINE_COUNT:
        return fail(f"line_count={cat['line_count']} want {br.KNOWN_LINE_COUNT}")
    if not live["cat_file_equals_git_show"]:
        return fail("git show disagrees with git cat-file")
    if not live["eol_normalisation"]["routes_identical_after_lf"]:
        return fail("routes differ after LF normalisation")
    if arch["sha256_lf"] != cat["sha256_lf"] or tree["sha256_lf"] != cat["sha256_lf"]:
        return fail("LF-normalised hashes disagree")
    if not live["stable_routes_byte_identical"]:
        return fail("stable.txt routes are not byte-identical (control failed)")

    art_table = {
        row["route"]: row for row in (doc.get("byte_table") or []) if isinstance(row, dict)
    }
    for name in ("git archive", "git cat-file", "worktree"):
        a, b = art_table.get(name) or {}, by[name]
        if a.get("bytes") != b["bytes"] or a.get("crlf_count") != b["crlf_count"]:
            return fail(f"receipt table mismatch on {name} art={a} live={b}")
        if a.get("sha256") != b["sha256"]:
            return fail(f"receipt sha256 mismatch on {name}")

    if live["content_bytes_route"] != "git cat-file":
        return fail(f"content_bytes route {live['content_bytes_route']}")

    payload = {
        "probe": "probe1-three-routes",
        "unit_id": "TST-0334",
        "pass": True,
        "byte_table": live["byte_table"],
        "eol_normalisation": live["eol_normalisation"],
        "stable_routes_byte_identical": live["stable_routes_byte_identical"],
        "content_bytes_route": live["content_bytes_route"],
        "receipt_matches_live": True,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(
        "identical_after_lf=True archive_crlf>0 cat_file_crlf=0 "
        "stable_byte_identical=True"
    )
    print("SUCCESS:TST-0334-probe1 three-route table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
