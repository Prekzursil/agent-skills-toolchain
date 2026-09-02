#!/usr/bin/env python3
"""Probe 2: detector controls for CNF-0101 (read-only of compared trees).

- EOL-only pair is not content drift; CRLF-LF byte delta equals CR count.
- Identical pair is IDENTICAL (classifier is not flagging everything).
- DIVERGED pair is DIVERGED two-way and REPO_AHEAD one-way (the miss).
- One-character content change remains content after LF normalisation.
- Census trees are fingerprinted before/after; any write fails the unit.
- Catalog-named sync script is not executed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare as C  # noqa: E402
import hosts as H  # noqa: E402

CTRL_S = HERE / "fixtures" / "control" / "shipped"
CTRL_L = HERE / "fixtures" / "control" / "live"
CENSUS_S = HERE / "fixtures" / "census" / "shipped"
CENSUS_L = HERE / "fixtures" / "census" / "live"
OUT = HERE / "probe2-controls.raw.json"


def _pair(name: str) -> tuple[bytes, bytes]:
    return (CTRL_S / name).read_bytes(), (CTRL_L / name).read_bytes()


def main() -> int:
    if not CTRL_S.is_dir() or not CTRL_L.is_dir():
        print("FAILED:CNF-0101-probe2 control fixtures absent")
        return 1

    before_cs = C.fingerprint_tree(CENSUS_S)
    before_cl = C.fingerprint_tree(CENSUS_L)
    before_ts = C.fingerprint_tree(CTRL_S)
    before_tl = C.fingerprint_tree(CTRL_L)

    ident = C.classify_pair(*_pair("identical.md"))
    eol = C.classify_pair(*_pair("eol-only.md"))
    content = C.classify_pair(*_pair("content.md"))
    diverged = C.classify_pair(*_pair("diverged.md"))
    repo_ahead = C.classify_pair(*_pair("repo-ahead.md"))
    live_ahead = C.classify_pair(*_pair("live-ahead.md"))

    d_repo, d_live = _pair("diverged.md")
    one_way_diverged = C.classify_one_directional(d_repo, d_live)
    e_repo, e_live = _pair("eol-only.md")
    cr_count = e_live.count(b"\r\n")
    eol_delta = abs(len(e_live) - len(e_repo))

    after_cs = C.fingerprint_tree(CENSUS_S)
    after_cl = C.fingerprint_tree(CENSUS_L)
    after_ts = C.fingerprint_tree(CTRL_S)
    after_tl = C.fingerprint_tree(CTRL_L)
    wrote = (
        before_cs != after_cs
        or before_cl != after_cl
        or before_ts != after_ts
        or before_tl != after_tl
    )

    sync = H.sync_script_census()
    executed = bool(sync.get("fixture_stand_in", {}).get("executed"))

    checks = {
        "identical_is_identical": ident["class"] == "IDENTICAL",
        "eol_separated_from_content": eol["class"] == "EOL_ONLY",
        "eol_raw_sha_differs": ident["class"] == "IDENTICAL"
        and eol["repo_sha256"] != eol["live_sha256"],
        "eol_lf_sha_matches": eol["repo_sha256_lf"] == eol["live_sha256_lf"],
        "eol_delta_equals_cr_count": eol_delta == cr_count and cr_count > 0,
        "content_not_eol": content["class"] in {"CONTENT_DIFFER", "REPO_AHEAD", "LIVE_AHEAD", "DIVERGED"}
        and content["repo_sha256_lf"] != content["live_sha256_lf"],
        "diverged_two_way": diverged["class"] == "DIVERGED"
        and diverged["repo_unique_line_count"] > 0
        and diverged["live_unique_line_count"] > 0,
        "one_directional_misses_diverged": one_way_diverged == "REPO_AHEAD",
        "repo_ahead_control": repo_ahead["class"] == "REPO_AHEAD",
        "live_ahead_control": live_ahead["class"] == "LIVE_AHEAD",
        "trees_unwritten": not wrote,
        "sync_not_executed": executed is False,
        "both_directions_on_diverged": diverged["in_repo"] and diverged["in_live"],
    }
    failed = [k for k, v in checks.items() if not v]
    doc = {
        "checks": checks,
        "failed": failed,
        "identical_class": ident["class"],
        "eol_class": eol["class"],
        "eol_delta_bytes": eol_delta,
        "eol_cr_count": cr_count,
        "content_class": content["class"],
        "diverged_class": diverged["class"],
        "one_directional_diverged_class": one_way_diverged,
        "repo_ahead_class": repo_ahead["class"],
        "live_ahead_class": live_ahead["class"],
        "trees_written": wrote,
        "sync_script": sync["fixture_stand_in"],
        "pass": not failed,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:CNF-0101-probe2 " + ",".join(failed))
        return 1
    print(
        "identical=IDENTICAL eol=EOL_ONLY eol_delta==cr_count="
        + str(eol_delta)
        + " content_lf_differs=True diverged=DIVERGED one_way_miss=REPO_AHEAD"
        + " trees_written=False sync_executed=False"
    )
    print("SUCCESS:CNF-0101-probe2 detector controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
