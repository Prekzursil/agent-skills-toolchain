#!/usr/bin/env python3
"""Probe 1: re-grep the frozen corpus and match the artifact's adoption counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

ART = REPO / "command-center/research/RES-0043.json"
SENTINEL_PHRASE = (
    "SUCCESS:RES-0043 in the receipt AND a per-capability code-level "
    "adoption count with the sample size and the README-only count stated"
)


def main() -> int:
    measured = S.scan()
    summary = measured["summary"]
    per = summary["per_capability"]
    print(
        "sample_servers="
        f"{summary['sample_size_servers']} "
        "sample_clients="
        f"{summary['sample_size_clients']} "
        "readme_only_sum="
        f"{summary['readme_only_count_sum']}"
    )
    for cap in S.CAPS:
        row = per[cap]
        print(
            f"code[{cap}] servers={row['code_level_servers']}/"
            f"{row['sample_size_servers']} "
            f"clients={row['code_level_clients']}/"
            f"{row['sample_size_clients']} "
            f"readme_only={row['readme_only_count']}"
        )
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0043-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0043-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0043" not in text or SENTINEL_PHRASE not in text:
        print("FAILED:RES-0043-probe1 sentinel absent")
        return 1
    art_counts = doc.get("per_capability_code_level_adoption") or {}
    if not isinstance(art_counts, dict):
        print("FAILED:RES-0043-probe1 adoption block missing")
        return 1
    if art_counts.get("sample_size_servers") != summary["sample_size_servers"]:
        print("FAILED:RES-0043-probe1 sample_size_servers mismatch")
        return 1
    if art_counts.get("sample_size_clients") != summary["sample_size_clients"]:
        print("FAILED:RES-0043-probe1 sample_size_clients mismatch")
        return 1
    for cap in S.CAPS:
        want = per[cap]
        got = art_counts.get(cap) or {}
        if got.get("code_level_servers") != want["code_level_servers"]:
            print(f"FAILED:RES-0043-probe1 {cap} server count mismatch")
            return 1
        if got.get("code_level_clients") != want["code_level_clients"]:
            print(f"FAILED:RES-0043-probe1 {cap} client count mismatch")
            return 1
        if got.get("readme_only_count") != want["readme_only_count"]:
            print(f"FAILED:RES-0043-probe1 {cap} readme-only mismatch")
            return 1
    everything = next(
        s for s in measured["subjects"] if s["id"] == "server.everything"
    )
    if everything["capabilities"]["sampling"]["class"] != "code":
        print("FAILED:RES-0043-probe1 everything sampling not code-level")
        return 1
    this_prog = next(
        s for s in measured["subjects"] if s["id"] == "client.this-program"
    )
    if any(this_prog["capabilities"][c]["class"] == "code" for c in S.CAPS):
        print("FAILED:RES-0043-probe1 this-program unexpectedly implements")
        return 1
    print(
        "SUCCESS:RES-0043-probe1 code-level hits match artifact "
        f"n={summary['sample_size']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
