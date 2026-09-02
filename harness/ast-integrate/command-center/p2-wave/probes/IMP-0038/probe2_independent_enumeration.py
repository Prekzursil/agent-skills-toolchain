#!/usr/bin/env python3
"""Probe 2: independent enumeration (manifest parse vs filesystem walk).

Mechanically different from the reconciler's enumerate_* helpers: this file
walks SKILL.md / hook.*.json / *.md itself and parses only the four kind
manifests. Those two sets must reproduce the reconciler's repo_only and
live_only on the complete-manifest fixture.

NEGATIVE CONTROL: when one skill is omitted from the repo manifest, the
parse misses it and the walk still finds it — a manifest-only census cannot
see a file the manifest forgot.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0038.json"
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import registration_fixture as fx  # noqa: E402
import registration_reconciler as rr  # noqa: E402


def _walk_ids(root: Path) -> set[str]:
    """Independent filesystem census. Does not call rr.enumerate_fs."""
    ids: set[str] = set()
    skills = root / "skills"
    if skills.is_dir():
        for dirpath, dirnames, filenames in os.walk(skills):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            if "SKILL.md" in filenames:
                parent = Path(dirpath)
                rel = parent.relative_to(skills).as_posix()
                ids.add(f"skill:{rel}")
    hooks = root / "hooks"
    if hooks.is_dir():
        for dirpath, dirnames, filenames in os.walk(hooks):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                if not name.endswith(".json"):
                    continue
                low = name.lower()
                if low == "manifest.json" or low.endswith("-manifest.json"):
                    continue
                stem = Path(name).stem
                if stem.startswith("hook."):
                    stem = stem[5:]
                ids.add(f"hook:{stem}")
    rules = root / "rules"
    if rules.is_dir():
        for dirpath, dirnames, filenames in os.walk(rules):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                if name.endswith(".md"):
                    rel = (Path(dirpath) / name).relative_to(rules).as_posix()
                    ids.add(f"rule:{rel}")
    commands = root / "commands"
    if commands.is_dir():
        for dirpath, dirnames, filenames in os.walk(commands):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                low = name.lower()
                if low.endswith("-manifest.json") or low == "manifest.json":
                    continue
                rel = (Path(dirpath) / name).relative_to(commands).as_posix()
                ids.add(f"command:{rel}")
    return ids


def _load(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _parse_ids(root: Path) -> set[str]:
    """Independent manifest census. Does not call rr.enumerate_manifest.

    Reads only the four kind manifests (not plugin.json), so agreement with
    the reconciler on a complete fixture proves both listings, not a shared
    parser.
    """
    ids: set[str] = set()
    skills = _load(root / "skills" / "DEPLOYED-MANIFEST.json").get("skills") or []
    for item in skills:
        if isinstance(item, str):
            ids.add(f"skill:{item}")
    hooks = _load(root / "hooks" / "_dispatch" / "manifest.json").get("hooks") or []
    for item in hooks:
        if isinstance(item, str):
            ids.add(f"hook:{item}")
    rules = _load(root / "rules" / "RULES-MANIFEST.json").get("rules") or []
    for item in rules:
        if isinstance(item, str):
            ids.add(f"rule:{item}")
    commands = _load(root / "commands" / "COMMANDS-MANIFEST.json").get("commands") or []
    for item in commands:
        if isinstance(item, str):
            ids.add(f"command:{item}")
    return ids


def _diff(repo: set[str], live: set[str]) -> tuple[list[str], list[str]]:
    return sorted(repo - live), sorted(live - repo)


def main() -> int:
    complete = S.run_scenario(omit_forgotten=False)
    repo = Path(complete["repo_root"])
    live = Path(complete["live_root"])
    rec = complete["report"]

    walk_repo, walk_live = _walk_ids(repo), _walk_ids(live)
    parse_repo, parse_live = _parse_ids(repo), _parse_ids(live)
    walk_only_repo, walk_only_live = _diff(walk_repo, walk_live)
    parse_only_repo, parse_only_live = _diff(parse_repo, parse_live)

    agree_walk = walk_only_repo == rec["repo_only"] and walk_only_live == rec["live_only"]
    agree_parse = parse_only_repo == rec["repo_only"] and parse_only_live == rec["live_only"]
    walk_eq_parse = walk_only_repo == parse_only_repo and walk_only_live == parse_only_live

    gap = S.run_scenario(omit_forgotten=True)
    gap_repo = Path(gap["repo_root"])
    gap_live = Path(gap["live_root"])
    forgotten = fx.PLANTED["forgotten_skill"]
    gap_walk_repo = _walk_ids(gap_repo)
    gap_parse_repo = _parse_ids(gap_repo)
    gap_walk_live = _walk_ids(gap_live)
    gap_parse_live = _parse_ids(gap_live)
    gap_walk_only_repo, _ = _diff(gap_walk_repo, gap_walk_live)
    gap_parse_only_repo, _ = _diff(gap_parse_repo, gap_parse_live)
    forgotten_on_walk = forgotten in set(gap_walk_only_repo)
    forgotten_on_parse = forgotten in set(gap_parse_only_repo)

    out = {
        "walk_repo_only": walk_only_repo,
        "walk_live_only": walk_only_live,
        "parse_repo_only": parse_only_repo,
        "parse_live_only": parse_only_live,
        "reconciler_repo_only": rec["repo_only"],
        "reconciler_live_only": rec["live_only"],
        "walk_matches_reconciler": agree_walk,
        "parse_matches_reconciler": agree_parse,
        "walk_equals_parse": walk_eq_parse,
        "forgotten_skill": forgotten,
        "forgotten_found_by_walk": forgotten_on_walk,
        "forgotten_found_by_parse": forgotten_on_parse,
        "manifest_only_blind": forgotten_on_walk and not forgotten_on_parse,
    }
    print(json.dumps(out, sort_keys=True))

    if not (agree_walk and agree_parse and walk_eq_parse):
        print("FAILED:IMP-0038-probe2 independent sets do not reproduce reconciler")
        return 1
    if not out["manifest_only_blind"]:
        print("FAILED:IMP-0038-probe2 forgotten skill was not a parse-blind/walk-hit")
        return 1
    if rec["live_only_assumed_empty"] is not False:
        print("FAILED:IMP-0038-probe2 live-only was assumed empty")
        return 1
    if not ART.is_file() or "SUCCESS:IMP-0038" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0038-probe2 receipt sentinel-absent")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    meas = doc.get("measurement") or {}
    if set(meas.get("repo_only") or []) != set(rec["repo_only"]):
        print("FAILED:IMP-0038-probe2 receipt repo_only != live")
        return 1
    if set(meas.get("live_only") or []) != set(rec["live_only"]):
        print("FAILED:IMP-0038-probe2 receipt live_only != live")
        return 1
    # Confirm the module's two methods still agree on the complete fixture.
    module_fs_repo = rr.flatten(rr.enumerate_fs(repo))
    module_fs_live = rr.flatten(rr.enumerate_fs(live))
    if module_fs_repo != walk_repo or module_fs_live != walk_live:
        print("FAILED:IMP-0038-probe2 module fs walk != probe walk")
        return 1
    print(
        f"walk_eq_parse={walk_eq_parse} matches_reconciler={agree_walk} "
        f"manifest_blind={out['manifest_only_blind']}"
    )
    print("SUCCESS:IMP-0038-probe2 independent filesystem-vs-manifest enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
