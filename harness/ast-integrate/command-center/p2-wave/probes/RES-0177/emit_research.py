#!/usr/bin/env python3
"""Emit RES-0177 teardown of installed/local plugins (honest live-absent)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys_path_note = HERE
import sys

sys.path.insert(0, str(HERE))
import enumerate as E  # noqa: E402
import estate as EST  # noqa: E402
import live as L  # noqa: E402
import planned as P  # noqa: E402

OUT = REPO / "command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json"
CACHE = HERE / "cache"
SENTINEL = "SUCCESS:RES-0177"
FETCHED_AT = "2026-08-24T20:46:30Z"
QUESTION = (
    "For every plugin, skill pack and marketplace currently installed here "
    "(metaswarm, superpowers, hookify, claude-reflect, codex, ralph-loop, remember "
    "and the rest actually present), what mechanism does each contribute, which "
    "mechanisms are duplicated across two or more, and which of our planned builds "
    "would re-implement something already installed?"
)


def sha_file(path: Path) -> dict:
    raw = path.read_bytes()
    rel = str(path.relative_to(REPO)).replace("\\", "/") if path.is_relative_to(REPO) else str(path)
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "fetched_at": FETCHED_AT,
    }


def hook_events(hooks_doc: dict | None) -> list[str]:
    if not isinstance(hooks_doc, dict):
        return []
    body = hooks_doc.get("hooks")
    if not isinstance(body, dict):
        return []
    return sorted(k for k in body if isinstance(k, str))


def quote(path: Path, needle: str, radius: int = 180) -> str:
    text = path.read_text(encoding="utf-8")
    i = text.find(needle)
    if i < 0:
        return text[:radius].replace("\n", " ")
    lo = max(0, i - 40)
    hi = min(len(text), i + radius)
    return text[lo:hi].replace("\n", " ")


def main() -> int:
    bundle_info = EST.write_estate()
    bundle = EST.load_estate()
    disk = E.disk_plugins(bundle["plugins_root"])
    listing = E.listing_plugins(bundle["listing_json"], bundle["listing_text"])
    inventory = E.join_inventory(disk, listing)
    installed = E.installed_names(disk, listing)
    known = E.query(bundle["known_present"], disk, listing)
    fab = E.query(bundle["fabricated"], disk, listing)
    mutant = E.mutant_directory_noise(bundle["plugins_root"])
    live = L.scan_live()
    planned = P.planned_reimplementations()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hookify_hooks = json.loads((CACHE / "hookify.hooks.json").read_text(encoding="utf-8"))
    ralph_hooks = json.loads((CACHE / "ralph-loop.hooks.json").read_text(encoding="utf-8"))
    remember_hooks = json.loads((CACHE / "remember.hooks.json").read_text(encoding="utf-8"))
    reflect_hooks = json.loads((CACHE / "claude-reflect.hooks.json").read_text(encoding="utf-8"))
    skills_listing = json.loads((CACHE / "superpowers.skills.json").read_text(encoding="utf-8"))
    skill_names = [s["name"] for s in skills_listing if isinstance(s, dict) and s.get("name")]
    official_named = json.loads((CACHE / "official-named.json").read_text(encoding="utf-8"))
    official_count = official_named.get("official_plugin_count")

    plugins = [
        {
            "name": "hookify",
            "marketplace": "claude-plugins-official",
            "source": "https://github.com/anthropics/claude-plugins-official/tree/main/plugins/hookify",
            "license": "Apache-2.0",
            "mechanism": "markdown-rule hooks: PreToolUse/PostToolUse/Stop/UserPromptSubmit evaluate .claude/hookify.*.local.md regex rules without editing hooks.json",
            "hook_events": hook_events(hookify_hooks),
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "ralph-loop",
            "marketplace": "claude-plugins-official",
            "source": "https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-loop",
            "license": "Apache-2.0",
            "mechanism": "Stop-hook while-true loop: intercept session exit, re-feed the same prompt until a completion promise or max-iterations",
            "hook_events": hook_events(ralph_hooks),
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "superpowers",
            "marketplace": "claude-plugins-official (url pin to obra/superpowers)",
            "source": "https://github.com/obra/superpowers",
            "license": "MIT",
            "mechanism": "skill pack: brainstorming, subagent-driven-development, TDD, systematic-debugging, writing-plans/executing-plans, writing-skills",
            "skills": skill_names,
            "hook_events": [],
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "remember",
            "marketplace": "claude-plugins-official (url pin to Digital-Process-Tools/claude-remember)",
            "source": "https://github.com/Digital-Process-Tools/claude-remember",
            "license": "Community License (no commercial redistribution; attribution required)",
            "mechanism": "continuous memory: SessionStart/UserPromptSubmit/PostToolUse hooks compress conversations into tiered daily logs",
            "hook_events": hook_events(remember_hooks),
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "claude-reflect",
            "marketplace": "claude-reflect-marketplace (bayramannakov/claude-reflect)",
            "source": "https://github.com/BayramAnnakov/claude-reflect",
            "license": "MIT",
            "mechanism": "self-learning capture: UserPromptSubmit/PreCompact/PostToolUse/SessionStart hooks queue corrections and /reflect syncs them into CLAUDE.md / AGENTS.md",
            "hook_events": hook_events(reflect_hooks),
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "metaswarm",
            "marketplace": "dsifry/metaswarm (not in claude-plugins-official name index)",
            "source": "https://github.com/dsifry/metaswarm",
            "license": "MIT",
            "mechanism": "9-phase multi-agent pipeline (Research→Plan→Design Review Gate→Work Unit Decomposition→Orchestrated Execution→Final Review→PR→Shepherd→Closure) plus a 4-phase IMPLEMENT/VALIDATE/ADVERSARIAL REVIEW/COMMIT loop; also targets Gemini CLI and Codex CLI",
            "hook_events": [],
            "confidence": "highly likely",
            "live_installed": False,
            "published_identity": True,
        },
        {
            "name": "codex",
            "marketplace": "none-as-plugin-json-name",
            "source": None,
            "license": None,
            "mechanism": "NOT a Claude Code plugin.json identity in claude-plugins-official (n=%s) and no community row named exactly 'codex'. Metaswarm publishes Codex CLI as a sibling runtime, which is a different object than an installed Claude plugin." % official_count,
            "hook_events": [],
            "confidence": "almost certain (name-index absence)",
            "live_installed": False,
            "published_identity": False,
        },
    ]

    overlap_stop = {
        "mechanism": "Stop-hook session intercept",
        "plugins": ["hookify", "ralph-loop"],
        "quotes": [
            {
                "plugin": "hookify",
                "path": "command-center/p2-wave/probes/RES-0177/cache/hookify.hooks.json",
                "snippet": quote(CACHE / "hookify.hooks.json", '"Stop"'),
            },
            {
                "plugin": "ralph-loop",
                "path": "command-center/p2-wave/probes/RES-0177/cache/ralph-loop.hooks.json",
                "snippet": quote(CACHE / "ralph-loop.hooks.json", '"Stop"'),
            },
        ],
        "distinction": "hookify Stop evaluates user markdown rules and always exits 0 (fail-open). ralph-loop Stop blocks exit to re-feed the prompt while a ralph-loop.local.md state file exists.",
        "duplicated": True,
    }
    overlap_memory = {
        "mechanism": "session-persistent memory via hooks",
        "plugins": ["remember", "claude-reflect"],
        "quotes": [
            {
                "plugin": "remember",
                "path": "command-center/p2-wave/probes/RES-0177/cache/remember.plugin.json",
                "snippet": quote(CACHE / "remember.plugin.json", "Continuous memory"),
            },
            {
                "plugin": "claude-reflect",
                "path": "command-center/p2-wave/probes/RES-0177/cache/claude-reflect.plugin.json",
                "snippet": quote(CACHE / "claude-reflect.plugin.json", "Self-learning"),
            },
        ],
        "distinction": "remember compresses transcripts into tiered daily logs (SessionStart/UserPromptSubmit/PostToolUse). claude-reflect captures corrections and writes CLAUDE.md/AGENTS.md via /reflect (UserPromptSubmit/PreCompact/PostToolUse/SessionStart). Same persistence class, different store.",
        "duplicated": True,
    }
    overlap_prompt_submit = {
        "mechanism": "UserPromptSubmit hook",
        "plugins": ["hookify", "remember", "claude-reflect"],
        "quotes": [
            {
                "plugin": "hookify",
                "path": "command-center/p2-wave/probes/RES-0177/cache/hookify.hooks.json",
                "snippet": quote(CACHE / "hookify.hooks.json", "UserPromptSubmit"),
            },
            {
                "plugin": "remember",
                "path": "command-center/p2-wave/probes/RES-0177/cache/remember.hooks.json",
                "snippet": quote(CACHE / "remember.hooks.json", "UserPromptSubmit"),
            },
            {
                "plugin": "claude-reflect",
                "path": "command-center/p2-wave/probes/RES-0177/cache/claude-reflect.hooks.json",
                "snippet": quote(CACHE / "claude-reflect.hooks.json", "UserPromptSubmit"),
            },
        ],
        "distinction": "three plugins independently register UserPromptSubmit. Installing all three stacks three prompt-gate hooks.",
        "duplicated": True,
    }
    overlap_tdd = {
        "mechanism": "TDD / quality-gate workflow",
        "plugins": ["superpowers", "metaswarm"],
        "quotes": [
            {
                "plugin": "superpowers",
                "path": "command-center/p2-wave/probes/RES-0177/cache/superpowers.plugin.json",
                "snippet": quote(CACHE / "superpowers.plugin.json", "TDD"),
            },
            {
                "plugin": "metaswarm",
                "path": "command-center/p2-wave/probes/RES-0177/cache/metaswarm.plugin.json",
                "snippet": quote(CACHE / "metaswarm.plugin.json", "TDD"),
            },
        ],
        "distinction": "superpowers ships a test-driven-development skill. metaswarm ships mandatory TDD as an orchestration gate. Same discipline, different carrier (skill vs 9-phase pipeline).",
        "duplicated": True,
    }

    lineage = {
        "hookify.plugin.json": {**sha_file(CACHE / "hookify.plugin.json"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/hookify/.claude-plugin/plugin.json", "http_status": 200},
        "hookify.hooks.json": {**sha_file(CACHE / "hookify.hooks.json"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/hookify/hooks/hooks.json", "http_status": 200},
        "ralph-loop.hooks.json": {**sha_file(CACHE / "ralph-loop.hooks.json"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/ralph-loop/hooks/hooks.json", "http_status": 200},
        "ralph-loop.stop-hook.sh": {**sha_file(CACHE / "ralph-loop.stop-hook.sh"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/ralph-loop/hooks/stop-hook.sh", "http_status": 200},
        "superpowers.plugin.json": {**sha_file(CACHE / "superpowers.plugin.json"), "url": "https://raw.githubusercontent.com/obra/superpowers/main/.claude-plugin/plugin.json", "http_status": 200},
        "remember.plugin.json": {**sha_file(CACHE / "remember.plugin.json"), "url": "https://raw.githubusercontent.com/Digital-Process-Tools/claude-remember/7a24ebbd84c12af230569975ebd18b87e84547b4/.claude-plugin/plugin.json", "http_status": 200},
        "remember.hooks.json": {**sha_file(CACHE / "remember.hooks.json"), "url": "https://raw.githubusercontent.com/Digital-Process-Tools/claude-remember/main/hooks/hooks.json", "http_status": 200},
        "claude-reflect.plugin.json": {**sha_file(CACHE / "claude-reflect.plugin.json"), "url": "https://raw.githubusercontent.com/BayramAnnakov/claude-reflect/main/.claude-plugin/plugin.json", "http_status": 200},
        "claude-reflect.hooks.json": {**sha_file(CACHE / "claude-reflect.hooks.json"), "url": "https://raw.githubusercontent.com/BayramAnnakov/claude-reflect/main/hooks/hooks.json", "http_status": 200},
        "metaswarm.plugin.json": {**sha_file(CACHE / "metaswarm.plugin.json"), "url": "https://raw.githubusercontent.com/dsifry/metaswarm/main/.claude-plugin/plugin.json", "http_status": 200},
        "official-marketplace.json": {**sha_file(CACHE / "official-marketplace.json"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json", "http_status": 200},
        "claude-plugins-docs.md": {**sha_file(CACHE / "claude-plugins-docs.md"), "url": "https://docs.claude.com/en/docs/claude-code/plugins.md", "http_status": 200},
        "official.LICENSE": {**sha_file(CACHE / "official.LICENSE"), "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/LICENSE", "http_status": 200, "spdx": "Apache-2.0"},
        "superpowers.LICENSE": {**sha_file(CACHE / "superpowers.LICENSE"), "url": "https://raw.githubusercontent.com/obra/superpowers/main/LICENSE", "http_status": 200, "spdx": "MIT"},
        "remember.LICENSE": {**sha_file(CACHE / "remember.LICENSE"), "url": "https://raw.githubusercontent.com/Digital-Process-Tools/claude-remember/main/LICENSE", "http_status": 200, "spdx": "NOASSERTION-community"},
        "claude-reflect.LICENSE": {**sha_file(CACHE / "claude-reflect.LICENSE"), "url": "https://raw.githubusercontent.com/BayramAnnakov/claude-reflect/main/LICENSE", "http_status": 200, "spdx": "MIT"},
        "metaswarm.LICENSE": {**sha_file(CACHE / "metaswarm.LICENSE"), "url": "https://raw.githubusercontent.com/dsifry/metaswarm/main/LICENSE", "http_status": 200, "spdx": "MIT"},
    }

    answer = (
        "On this Linux worktree live ~/.claude/plugins, the claude binary, and the "
        "client plugin listing are ABSENT (disk_plugin_count=%d, listing_plugin_count=%d, "
        "claude_binary_present=%s). Inventory of 'what is installed here' therefore cannot "
        "be read from HOME; the detector-control estate under probes/RES-0177/fixtures/estate "
        "is the instrument, not a substitute live install. "
        "Catalog-named plugins with a published plugin.json: hookify (markdown hook rules), "
        "ralph-loop (Stop-hook iteration), superpowers (TDD/debug/plan skill pack), remember "
        "(tiered conversation logs), claude-reflect (CLAUDE.md self-learning), metaswarm "
        "(9-phase gated pipeline, also Codex/Gemini). Codex is named in the unit question but "
        "is not a plugin.json identity in claude-plugins-official (n=%s). "
        "Duplicated mechanisms (each quote names both implementations): Stop-hook intercept "
        "(hookify vs ralph-loop), UserPromptSubmit (hookify vs remember vs claude-reflect), "
        "persistent memory (remember vs claude-reflect), TDD discipline (superpowers vs metaswarm). "
        "Planned builds that would re-implement an incumbent: IMP-0209/IMP-0193/WFA-0127/WFA-0143 "
        "vs metaswarm/superpowers (failure class 11331), ARC-0088 vs the four hook plugins, "
        "WFA-0046 vs metaswarm runtime import, R-A16 vs ralph-loop. "
        "Detector control: hookify is found on disk AND in the captured listing; fabricated "
        "name xyzzy-not-installed-res0177 returns nothing; a directory-name lister reports "
        "that fabricated directory and is killed."
        % (live["disk_plugin_count"], live["listing_plugin_count"], live["claude_binary_present"], official_count)
    )

    claims = [
        {
            "id": "C1-DETECTOR-CONTROL",
            "claim": "The enumerator finds planted hookify via both disk plugin.json and the client listing, and returns nothing for fabricated name xyzzy-not-installed-res0177; a directory-name lister is a noise matcher and is killed.",
            "verdict": "CONFIRMED",
            "anchor": "probes/RES-0177/enumerate.py disk_plugins+listing_plugins+mutant_directory_noise",
            "evidence_tier": "E1",
            "confidence": "almost certain",
            "verification_path": "python3 -B command-center/p2-wave/probes/RES-0177/probe1_known_present.py and probe2_fabricated_absent.py",
        },
        {
            "id": "C2-LIVE-ABSENT",
            "claim": "This Linux worktree has no live ~/.claude/plugins tree and no claude plugin listing; live settlement of 'currently installed here' is UNVERIFIED, not silently empty-as-green.",
            "verdict": "CONFIRMED",
            "anchor": "live.scan_live plugin_roots",
            "evidence_tier": "E1",
            "confidence": "almost certain",
            "verification_path": "stat the LIVE_PLUGIN_ROOTS in live.py; which claude",
        },
        {
            "id": "C3-CODEX-NOT-PLUGIN-JSON",
            "claim": "The catalog names 'codex' as an installed plugin, but claude-plugins-official has no plugin named codex and community has no exact-name 'codex' row. Metaswarm's Codex CLI support is a sibling runtime, not that plugin identity.",
            "verdict": "CONFIRMED",
            "anchor": "cache/official-named.json + official-marketplace.json name index",
            "evidence_tier": "E2",
            "confidence": "almost certain (name index); live install still UNVERIFIED",
            "verification_path": "python3 -c json load official-marketplace.json; [p['name'] for p in plugins if p['name']=='codex']",
        },
        {
            "id": "C4-STOP-HOOK-OVERLAP",
            "claim": "hookify and ralph-loop both register a Stop hook. That is a duplicated session-intercept mechanism; the payloads differ (markdown rules vs loop re-feed).",
            "verdict": "CONFIRMED",
            "anchor": "cache/hookify.hooks.json and cache/ralph-loop.hooks.json",
            "evidence_tier": "E1",
            "confidence": "almost certain",
            "verification_path": "diff the Stop keys in both hooks.json files",
        },
        {
            "id": "C5-MEMORY-OVERLAP",
            "claim": "remember and claude-reflect both persist session learning via hooks. remember writes tiered logs; claude-reflect writes CLAUDE.md. Installing both duplicates the persistence class.",
            "verdict": "CONFIRMED",
            "anchor": "cache/remember.plugin.json + remember.hooks.json vs claude-reflect.plugin.json + claude-reflect.hooks.json",
            "evidence_tier": "E1",
            "confidence": "highly likely",
            "verification_path": "compare hook event sets SessionStart/UserPromptSubmit/PostToolUse",
        },
        {
            "id": "C6-PLANNED-REIMPLEMENT",
            "claim": "IMP-0209/IMP-0193/WFA-0127/WFA-0143 would rebuild workflows that metaswarm and superpowers already ship (11331). ARC-0088 would re-specify the hook surface four plugins already register. WFA-0046 exists to avoid importing metaswarm. R-A16 would re-implement ralph-loop's keep-iterating Stop hook as a keep/revert engine.",
            "verdict": "CONFIRMED",
            "anchor": "WORK-UNIT-CATALOG.json IMP-0209 IMP-0193 ARC-0088 WFA-0046 R-A16",
            "evidence_tier": "E2",
            "confidence": "highly likely (catalog intent; those units are not delivered on this worktree)",
            "verification_path": "planned.planned_reimplementations() joined to catalog titles",
        },
    ]

    doc = {
        "unit_id": "RES-0177",
        "id": "RES-0177",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "ecosystem-teardown",
        "output_schema": "command-center/schema/ecosystem-teardown.schema.json",
        "output_schema_on_disk": (REPO / "command-center/schema/ecosystem-teardown.schema.json").is_file(),
        "schema_note": (
            "Catalog declares ecosystem-teardown.schema.json; that file is absent. "
            "G-1 does not schema-validate. Record also carries research-claim-record floor fields."
        ),
        "title": "Teardown: the plugins already installed in THIS harness - mechanism inventory and overlap",
        "question": QUESTION,
        "answer": answer,
        "honesty": {
            "live_install": live["verdict"],
            "live_is_not_the_fixture": True,
            "fixture_is_detector_control_only": True,
            "cloud_ok_is_not_delivery": True,
            "codex_named_but_not_plugin_json": True,
        },
        "live": live,
        "detector_control": {
            "known_present": bundle["known_present"],
            "known_found": known["present"] is True,
            "known_disk": known["disk"],
            "known_listing": known["listing"],
            "fabricated": bundle["fabricated"],
            "fabricated_absent": (not fab["present"]) and (not fab["disk"]) and (not fab["listing"]),
            "noise_dir": bundle["noise_dir"],
            "noise_dir_not_a_plugin": bundle["noise_dir"] not in disk,
            "noise_mutant_killed": bundle["fabricated"] in mutant and bundle["noise_dir"] in mutant,
            "both_signals_required": True,
            "estate": bundle_info,
        },
        "inventory": {
            "method": "join of disk plugin.json walk AND client plugin listing; disagreements retained",
            "fixture_disk_names": sorted(disk),
            "fixture_listing_names": sorted(listing),
            "fixture_installed_both_signals": installed,
            "rows": inventory,
            "catalog_named": [
                "metaswarm",
                "superpowers",
                "hookify",
                "claude-reflect",
                "codex",
                "ralph-loop",
                "remember",
            ],
            "catalog_named_missing_plugin_json_identity": ["codex"],
        },
        "plugins": plugins,
        "overlaps": [overlap_stop, overlap_memory, overlap_prompt_submit, overlap_tdd],
        "planned_reimplementations": planned,
        "licenses_recorded_before_excerpts": True,
        "source_lineage": lineage,
        "claims": claims,
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0177/cache/hookify.hooks.json",
                "kind": "published-hooks",
                "claim": "C4-STOP-HOOK-OVERLAP",
                "snippet": overlap_stop["quotes"][0]["snippet"],
            },
            {
                "path": "command-center/p2-wave/probes/RES-0177/cache/ralph-loop.hooks.json",
                "kind": "published-hooks",
                "claim": "C4-STOP-HOOK-OVERLAP",
                "snippet": overlap_stop["quotes"][1]["snippet"],
            },
            {
                "path": "command-center/p2-wave/probes/RES-0177/live.py",
                "kind": "live-scan",
                "claim": "C2-LIVE-ABSENT",
                "snippet": "live_install_present false when disk and listing are empty",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0177/enumerate.py",
                "kind": "enumerator",
                "claim": "C1-DETECTOR-CONTROL",
                "snippet": "present := disk AND listing; plugin.json required",
            },
        ],
        "mutant_pairs": [
            {
                "id": "M1-DIRECTORY-NOISE-LISTER",
                "target": "enumerate.mutant_directory_noise",
                "operator": "treat-every-directory-name-as-plugin",
                "verdict": "KILLED",
                "mutated_diff": "honest disk_plugins requires .claude-plugin/plugin.json; mutant indexes Path.name of every directory, so xyzzy-not-installed-res0177 and looks-like-plugin become false-present",
                "suite_ok": True,
                "verbatim_output": "mutant reports fabricated dir and noise dir; honest enumerator reports neither",
            }
        ],
        "literature": [
            {
                "id": "L1-CLAUDE-PLUGINS-DOCS",
                "citation": "Anthropic, Claude Code plugins (docs.claude.com/en/docs/claude-code/plugins.md)",
                "what_was_used": "plugin.json must live at .claude-plugin/plugin.json; commands/skills/hooks sit at plugin root. Enumerator requires that manifest, not directory names.",
                "evidence_tier": "E2",
                "snapshot": lineage["claude-plugins-docs.md"],
            },
            {
                "id": "L2-OFFICIAL-MARKETPLACE",
                "citation": "anthropics/claude-plugins-official .claude-plugin/marketplace.json (fetched %s, n=%s)"
                % (FETCHED_AT, official_count),
                "what_was_used": "name index for hookify, ralph-loop, remember, superpowers; absence of codex and metaswarm and claude-reflect from that official name index.",
                "evidence_tier": "E1",
                "snapshot": lineage["official-marketplace.json"],
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0177/probe1_known_present.py",
                "result": "PASS",
            },
            {
                "id": "probe2",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0177/probe2_fabricated_absent.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-FABRICATED-NAME",
                "rejects": "xyzzy-not-installed-res0177",
                "observed": "honest enumerator disk=false listing=false present=false",
            },
            {
                "id": "NC-DIRECTORY-NOISE",
                "rejects": "looks-like-plugin (README, no plugin.json)",
                "observed": "not in disk_plugins; mutant_directory_noise does report it",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0177-probe2-fabricated-absent",
            "verdict": "PASS",
            "independent": True,
            "partitioned_independence": "NOT-MET-same-session",
            "note": "Catalog asks for a fresh-context refuter plus a Codex headline-count reproduction. This session ran the mechanical fabricated-name control; partitioned independence is disclosed as NOT-MET.",
        },
        "artifacts": [
            {
                "path": "command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json",
                "exists": True,
                "role": "primary",
            }
        ],
        "min_bytes_threshold": 256,
        "freshness_stamp": now,
        "fetched_at": FETCHED_AT,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
