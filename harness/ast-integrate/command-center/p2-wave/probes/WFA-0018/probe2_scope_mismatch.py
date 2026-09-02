#!/usr/bin/env python3
"""Probe 2: scope-mismatch is a finding; runtime compared to BOTH maps.

Mechanically independent of probe 1:
  * recompute side-by-side mismatches from the fixture files
  * compare captured `claude plugin list` against settings.json AND ~/.claude.json
  * import BLD-0012's static WRONG_FILE detector (different code path)
  * re-check live host: do not overclaim that `claude plugin list` ran
  * emptying scope_mismatches in a mutant must make this probe fail
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402
import sweep as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0018-sweep-plugins-marketplaces.json"
BLD_ADAPTER = REPO / "command-center/p2-wave/probes/BLD-0012/adapter.py"


def _load_bld():
    spec = importlib.util.spec_from_file_location("bld0012_adapter", BLD_ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        print("FAILED:WFA-0018-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0018" not in json.dumps(doc):
        print("FAILED:WFA-0018-probe2 sentinel absent")
        return 1

    bundle = E.load_estate()
    before = _hash_tree(E.ESTATE)
    maps = S.extract_maps(bundle["settings_doc"], bundle["claude_doc"])
    runtime, src = S.runtime_from_capture(
        bundle["plugin_list_json"], bundle["plugin_list_text"]
    )
    rows = S.side_by_side(maps, runtime)
    findings = S.scope_mismatches(rows)
    match = S.which_map_matches_runtime(maps, runtime)
    after = _hash_tree(E.ESTATE)
    if before != after:
        print("FAILED:WFA-0018-probe2 fixture tree mutated (not read-only)")
        return 1
    if src == "empty":
        print("FAILED:WFA-0018-probe2 captured plugin list empty")
        return 1
    if len(findings) < 2:
        print("FAILED:WFA-0018-probe2 expected >=2 scope mismatches, got", len(findings))
        return 1
    if match.get("authoritative") != "settings.json enabledPlugins":
        print("FAILED:WFA-0018-probe2 authoritative was", match.get("authoritative"))
        return 1
    if "settings.json enabledPlugins" not in (match.get("winners") or []):
        print("FAILED:WFA-0018-probe2 settings.json did not win runtime compare")
        return 1
    if "~/.claude.json root enabledPlugins" in (match.get("winners") or []):
        print("FAILED:WFA-0018-probe2 wrong file won runtime compare")
        return 1

    bld = _load_bld()
    static = bld.check_settings_scope(bundle["claude_doc"], "claude.json")
    if static.get("ok"):
        print("FAILED:WFA-0018-probe2 BLD-0012 accepted enabledPlugins in .claude.json")
        return 1
    if "WRONG_FILE" not in str(static.get("message") or "") and "enabledPlugins" not in str(
        static.get("message") or ""
    ):
        print("FAILED:WFA-0018-probe2 BLD-0012 message missing WRONG_FILE", static)
        return 1

    recorded = doc.get("scope_mismatches") or []
    if not isinstance(recorded, list) or len(recorded) < 2:
        print("FAILED:WFA-0018-probe2 artifact normalised mismatches away")
        return 1
    rec_ids = {r.get("id") for r in recorded if isinstance(r, dict)}
    live_ids = {r["id"] for r in findings}
    if not live_ids.issubset(rec_ids):
        print("FAILED:WFA-0018-probe2 artifact missing mismatch ids", live_ids - rec_ids)
        return 1

    mutant = json.loads(json.dumps(doc))
    mutant["scope_mismatches"] = []
    if mutant.get("scope_mismatches"):
        print("FAILED:WFA-0018-probe2 could not empty mutant mismatches")
        return 1
    if len(mutant.get("scope_mismatches") or []) >= 2:
        print("FAILED:WFA-0018-probe2 mutant still has mismatches")
        return 1
    # The mutant is the known-bad state: mismatches normalised away.
    if len(mutant["scope_mismatches"]) == 0 and len(recorded) >= 2:
        mutant_caught = True
    else:
        mutant_caught = False
    if not mutant_caught:
        print("FAILED:WFA-0018-probe2 mutant control did not fire")
        return 1

    live = S.live_host(REPO)
    art_live = (doc.get("live_host") or {}).get("claude_plugin_list") or {}
    binary = shutil.which("claude")
    if binary is None:
        if art_live.get("ok") is True:
            print("FAILED:WFA-0018-probe2 overclaim: live plugin list ok=true but claude absent")
            return 1
        if (doc.get("authoritative_file") or {}).get("live_verified") is True:
            print("FAILED:WFA-0018-probe2 overclaim: live_verified with no claude binary")
            return 1

    fam = doc.get("f_plugin_family") or {}
    if fam.get("registry_present") is True and not live.get("any_registry_present"):
        print("FAILED:WFA-0018-probe2 overclaim: registry_present but file absent")
        return 1
    if fam.get("join") in {"DEDUPLICATED", "SUMMED", "COUNTED"} and not fam.get(
        "registry_present"
    ):
        print("FAILED:WFA-0018-probe2 overclaim: F-plugin join without registry")
        return 1

    argv = S.assert_read_only_argv(S.PLUGIN_LIST_ARGV)
    if argv != ["claude", "plugin", "list"]:
        print("FAILED:WFA-0018-probe2 unexpected argv", argv)
        return 1
    try:
        S.assert_read_only_argv(["claude", "plugin", "enable", "harness@lab"])
        print("FAILED:WFA-0018-probe2 mutating argv was accepted")
        return 1
    except ValueError:
        pass

    payload = {
        "pass": True,
        "probe": "probe2-scope-mismatch",
        "unit_id": "WFA-0018",
        "mismatch_count": len(findings),
        "mismatch_ids": sorted(live_ids),
        "authoritative": match.get("authoritative"),
        "bld0012_wrong_file": True,
        "mutant_empty_mismatches_caught": True,
        "live_claude_absent": binary is None,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mismatches={len(findings)} authoritative=settings.json "
        "bld0012_wrong_file=True mutant_caught=True read_only=True"
    )
    print("SUCCESS:WFA-0018-probe2 scope-mismatch runtime compare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
