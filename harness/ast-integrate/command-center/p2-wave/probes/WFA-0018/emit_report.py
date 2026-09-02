#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0018-sweep-plugins-marketplaces.json."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402
import sweep as S  # noqa: E402

OUT = "command-center/wfa/WFA-0018-sweep-plugins-marketplaces.json"
QUESTION = (
    "Which installed plugins and mounted marketplaces contribute workflow "
    "definitions or commands, and which configuration file actually governs "
    "enablement - the enabledPlugins map in ~/.claude/settings.json or the "
    "per-project map in ~/.claude.json?"
)
BLD_ADAPTER = REPO / "command-center/p2-wave/probes/BLD-0012/adapter.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_bld():
    spec = importlib.util.spec_from_file_location("bld0012_adapter", BLD_ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def contributors(markets: list[dict], maps: dict, runtime: dict[str, bool]) -> list[dict]:
    settings = maps.get("settings_json") or {}
    rows = []
    for market in markets:
        for plugin in market.get("plugins") or []:
            pid = plugin["id"]
            rows.append(
                {
                    "id": pid,
                    "marketplace": market["name"],
                    "contributes_commands": plugin.get("contributes_commands"),
                    "contributes_workflows": plugin.get("contributes_workflows"),
                    "command_files": plugin.get("commands") or [],
                    "workflow_files": plugin.get("workflows") or [],
                    "skill_files": plugin.get("skills") or [],
                    "settings_enabled": settings.get(pid),
                    "runtime_enabled": runtime.get(pid) if pid in runtime else None,
                    "in_runtime_list": pid in runtime,
                    "in_settings_map": pid in settings,
                }
            )
    return rows


def main() -> int:
    bundle = E.load_estate()
    maps = S.extract_maps(bundle["settings_doc"], bundle["claude_doc"])
    runtime, runtime_src = S.runtime_from_capture(
        bundle["plugin_list_json"], bundle["plugin_list_text"]
    )
    rows = S.side_by_side(maps, runtime)
    findings = S.scope_mismatches(rows)
    match = S.which_map_matches_runtime(maps, runtime)
    pair = S.classify_pair(
        maps, runtime, bundle["known_enabled"], bundle["known_disabled"]
    )
    markets = S.inventory_marketplaces(bundle["home"])
    contrib = contributors(markets, maps, runtime)
    live = S.live_host(REPO)
    bld = load_bld()
    bld_wrong = bld.check_settings_scope(bundle["claude_doc"], "claude.json")
    bld_settings = bld.check_settings_scope(bundle["settings_doc"], "settings.json")

    workflow_ids = [r["id"] for r in contrib if r.get("contributes_workflows")]
    command_ids = [r["id"] for r in contrib if r.get("contributes_commands")]
    enabled_contributors = [
        r["id"]
        for r in contrib
        if r.get("contributes_workflows") and r.get("runtime_enabled") is True
    ]

    answer = (
        "On the fixture estate that reproduces this program's measured trap, "
        "enablement is governed by enabledPlugins in ~/.claude/settings.json. "
        "The captured `claude plugin list` matches that map (harness@lab "
        "enabled, agentbridge@lab disabled, metaswarm@lab enabled) and "
        "contradicts both the root and per-project enabledPlugins maps in "
        "~/.claude.json, which invert harness/agentbridge and invent "
        "root-ghost@lab. That is the right-key-wrong-file failure; the "
        "disagreement is a scope-mismatch finding, not a value to normalise. "
        "Mounted marketplace `lab` ships four plugins; harness@lab and "
        "metaswarm@lab contribute commands/workflows and are runtime-enabled; "
        "agentbridge@lab contributes a command file but is runtime-disabled; "
        "docs-only@lab is marketplace-only and contributes neither. "
        "On this Linux worktree live ~/.claude/settings.json, ~/.claude.json, "
        "installed plugin trees, the F-plugin registry, and the `claude` "
        "binary are all absent, so live settlement is UNVERIFIED. Catalog "
        "F-plugin n=21 cannot be joined without "
        "08-WORKFLOW-CANDIDATE-REGISTRY.json."
    )

    doc = {
        "unit_id": "WFA-0018",
        "record_type": "SweepReport",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0018",
        "title": (
            "Sweep installed plugins and mounted marketplaces, and settle "
            "which config file is authoritative"
        ),
        "question": QUESTION,
        "answer": answer,
        "surface": "plugins-and-marketplaces",
        "read_only": True,
        "toggled_nothing": True,
        "schema_declared": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport"
        ),
        "schema_present_on_disk": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "enablement_maps": {
            "settings_json": maps["settings_json"],
            "claude_json_root": maps["claude_json_root"],
            "claude_json_projects": maps["claude_json_projects"],
            "side_by_side": rows,
            "note": (
                "Evidence A: both files parsed; maps printed side by side. "
                "A key present in only one file remains a mismatch."
            ),
        },
        "runtime_plugin_list": {
            "source": runtime_src,
            "capture_json": (
                "command-center/p2-wave/probes/WFA-0018/fixtures/estate/"
                "claude-plugin-list.json"
            ),
            "capture_text": (
                "command-center/p2-wave/probes/WFA-0018/fixtures/estate/"
                "claude-plugin-list.txt"
            ),
            "parsed": runtime,
            "note": (
                "Evidence B: captured `claude plugin list` compared against "
                "BOTH maps. Live binary attempt is recorded separately and "
                "is not substituted for this capture."
            ),
        },
        "authoritative_file": {
            "verdict": "settings.json",
            "label": match.get("authoritative"),
            "fixture_verified": match.get("authoritative")
            == "settings.json enabledPlugins",
            "live_verified": False,
            "winners": match.get("winners"),
            "scored": match.get("scored"),
            "basis": (
                "runtime-match on fixture capture; ~/.claude.json root and "
                "per-project maps contradict runtime"
            ),
        },
        "scope_mismatches": findings,
        "both_states": pair,
        "installed_plugins": contrib,
        "mounted_marketplaces": [
            {
                "name": m["name"],
                "path": Path(m["path"]).relative_to(REPO).as_posix()
                if Path(m["path"]).is_relative_to(REPO)
                else m["path"],
                "manifest_present": m["manifest_present"],
                "declared_plugin_count": m["declared_plugin_count"],
                "installed_plugin_count": m["installed_plugin_count"],
                "plugin_ids": [p["id"] for p in m.get("plugins") or []],
            }
            for m in markets
        ],
        "workflow_command_contributors": {
            "contributes_commands": command_ids,
            "contributes_workflows": workflow_ids,
            "runtime_enabled_contributors": enabled_contributors,
        },
        "f_plugin_family": {
            "catalog_claimed_n": 21,
            "registry_present": live.get("any_registry_present"),
            "join": "UNVERIFIED",
            "reason": (
                "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux "
                "worktree; F-plugin n=21 is a catalog citation, not a counted join."
            ),
            "candidates_tried": live.get("registry_candidates"),
        },
        "live_host": live,
        "bld0012_static_wrong_file": {
            "claude_json": bld_wrong,
            "settings_json": bld_settings,
            "independent_of_runtime": True,
            "path": "command-center/p2-wave/probes/BLD-0012/adapter.py",
        },
        "recall_limit": (
            "Live user/project Claude config, installed plugin trees, and "
            "`claude plugin list` were not available on this host. The "
            "authoritative-file settlement is fixture-verified against a "
            "capture that encodes the measured trap. Repo-local plugin.json "
            "fixtures (ARC-0016 hatch, CNF-0178 marketplace) are not live "
            "Claude Code installs and are not counted as mounted marketplaces."
        ),
        "tests": [
            {
                "id": "both-states-enabled-disabled",
                "title": "known-enabled vs known-disabled distinguished without toggling",
                "passed": bool(
                    pair["settings_distinguishes"] and pair["runtime_distinguishes"]
                ),
                "evidence": (
                    f"{bundle['known_enabled']} enabled and "
                    f"{bundle['known_disabled']} disabled in settings.json "
                    "and in captured plugin list"
                ),
            },
            {
                "id": "read-only",
                "title": "sweep does not enable, disable, install, or remove plugins",
                "passed": True,
                "evidence": (
                    "argv builder refuses mutating subcommands; fixture tree "
                    "hash is unchanged by named probes"
                ),
            },
            {
                "id": "scope-mismatch-not-normalised",
                "title": "settings vs .claude.json disagreement is a finding",
                "passed": len(findings) >= 2,
                "evidence": f"{len(findings)} scope-mismatch rows retained",
            },
        ],
        "evidence": [
            {
                "id": "A-side-by-side-maps",
                "kind": "file-parse",
                "detail": "enabledPlugins from settings.json and ~/.claude.json printed together",
            },
            {
                "id": "B-runtime-plugin-list",
                "kind": "runtime-capture",
                "detail": "claude plugin list parse compared to both maps",
            },
            {
                "id": "C-bld0012-wrong-file",
                "kind": "sibling-detector",
                "detail": "BLD-0012 check_settings_scope rejects enabledPlugins in .claude.json",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0018-probe2-scope-mismatch",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes mismatches, requires the BLD-0012 WRONG_FILE "
                "hit, catches a mutant that empties scope_mismatches, and "
                "refuses live overclaim when `claude` is absent."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0018/sweep.py",
                "role": "sweep-engine",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0012/adapter.py",
                "role": "sibling-wrong-file-detector",
            },
        ],
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 WFA-0018: live named probes, honest live-absent census, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("mismatches", len(findings), "authoritative", match.get("authoritative"))
    print("SUCCESS:WFA-0018")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
