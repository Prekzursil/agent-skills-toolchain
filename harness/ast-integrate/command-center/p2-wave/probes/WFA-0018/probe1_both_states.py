#!/usr/bin/env python3
"""Probe 1: both-states enablement, toggle nothing.

Read a plugin known-enabled (harness@lab) and one known-disabled
(agentbridge@lab). Settings.json + captured `claude plugin list` must
distinguish them. The same key in ~/.claude.json inverts the pair — that
is the right-key-wrong-file trap, not a normalisation target.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402
import sweep as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0018-sweep-plugins-marketplaces.json"


def _hash_tree(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0018-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0018" not in json.dumps(doc):
        print("FAILED:WFA-0018-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0018-probe1 self-declared", doc.get("state"))
        return 1

    bundle = E.load_estate()
    before = _hash_tree(E.ESTATE)
    maps = S.extract_maps(bundle["settings_doc"], bundle["claude_doc"])
    runtime, src = S.runtime_from_capture(
        bundle["plugin_list_json"], bundle["plugin_list_text"]
    )
    pair = S.classify_pair(
        maps, runtime, bundle["known_enabled"], bundle["known_disabled"]
    )
    after = _hash_tree(E.ESTATE)
    if before != after:
        print("FAILED:WFA-0018-probe1 fixture tree mutated (not read-only)")
        return 1
    if not pair["settings_distinguishes"]:
        print("FAILED:WFA-0018-probe1 settings.json did not distinguish enabled/disabled")
        return 1
    if not pair["runtime_distinguishes"]:
        print("FAILED:WFA-0018-probe1 runtime list did not distinguish enabled/disabled")
        return 1
    if not pair["settings_matches_runtime"]:
        print("FAILED:WFA-0018-probe1 settings.json does not match runtime")
        return 1
    if not pair["wrong_file_inverts"]:
        print("FAILED:WFA-0018-probe1 wrong-file map did not invert the pair")
        return 1
    if pair["wrong_file_matches_runtime"]:
        print("FAILED:WFA-0018-probe1 ~/.claude.json matched runtime; trap not reproduced")
        return 1
    if src == "empty":
        print("FAILED:WFA-0018-probe1 captured plugin list parsed empty")
        return 1

    recorded = doc.get("both_states") or {}
    if recorded.get("settings_distinguishes") is not True:
        print("FAILED:WFA-0018-probe1 artifact missing both-states distinguish")
        return 1
    if recorded.get("wrong_file_inverts") is not True:
        print("FAILED:WFA-0018-probe1 artifact did not record wrong-file invert")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "WFA-0018",
        "runtime_parse": src,
        "pair": pair,
        "toggled_nothing": True,
        "fixture_hash_unchanged": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "enabled="
        + bundle["known_enabled"]
        + " disabled="
        + bundle["known_disabled"]
        + " settings_distinguishes=True runtime_distinguishes=True"
        + " wrong_file_inverts=True toggled_nothing=True"
    )
    print("SUCCESS:WFA-0018-probe1 both-states read-only enablement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
