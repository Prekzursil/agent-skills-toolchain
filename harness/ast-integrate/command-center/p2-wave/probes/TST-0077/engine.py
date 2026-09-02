#!/usr/bin/env python3
"""Versioned layout migration for TST-0077.

Fingerprints follow IMP-0048: a marker file AND a second discriminating
property. Ambiguous (two fingerprints) is reported, never silently resolved.
Unknown layouts return NO_MIGRATION_PATH rather than a skip.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

CURRENT = "CURRENT"
LEGACY = "LEGACY"
AMBIGUOUS = "AMBIGUOUS"
NO_PATH = "NO_MIGRATION_PATH"

FP_COPIED_SKILLS = "copied-skills-pre-marketplace"
FP_MCP_JSON = "mcp-json-per-project"
FP_ROOT_DISABLED = "disabledMcpServers-root-scoped"
FP_PRE_DISPATCH = "hooks-pre-dispatch"

PROFILE = "/profile"
SKILL_REL = "skills/skill.council/SKILL.md"
MARKET_REL = "marketplace/marketplace.harness.json"
PLUGIN_REL = "plugin.json"
HOOK_REL = "hooks/hook.pre-tool.json"
HOOKS_MANIFEST = "hooks/manifest.json"
DISPATCH_REL = "hooks/_dispatch/manifest.json"
MCP_JSON_REL = ".mcp.json"
SETTINGS_REL = ".claude/settings.json"
CLAUDE_ROOT_REL = "claude.json"

STEP_V1 = "v1-copied-skills-to-marketplace"
STEP_V2 = "v2-mcp-json-to-settings"
STEP_V3 = "v3-root-disabled-to-per-project"
STEP_V4 = "v4-pre-dispatch-hooks-to-hooks"


def lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def digest_text(text: str) -> str:
    return hashlib.sha256(lf(text).encode("utf-8")).hexdigest()


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def loads(text: str) -> Any:
    return json.loads(lf(text))


def lines_of(text: str) -> list[str]:
    body = lf(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def census(tree: dict[str, str]) -> dict[str, str]:
    return {k: digest_text(v) for k, v in sorted(tree.items())}


def trees_equal(a: dict[str, str], b: dict[str, str]) -> bool:
    return census(a) == census(b)


def _get_json(tree: dict[str, str], rel: str) -> dict:
    if rel not in tree:
        return {}
    doc = loads(tree[rel])
    return doc if isinstance(doc, dict) else {}


def _settings(tree: dict[str, str]) -> dict:
    return _get_json(tree, SETTINGS_REL)


def _project(settings: dict) -> dict:
    projects = settings.get("projects")
    if not isinstance(projects, dict):
        return {}
    proj = projects.get(PROFILE)
    return proj if isinstance(proj, dict) else {}


def mcp_in_settings(tree: dict[str, str]) -> bool:
    proj = _project(_settings(tree))
    servers = proj.get("mcpServers")
    return isinstance(servers, dict) and len(servers) > 0


def per_project_disabled(tree: dict[str, str]) -> bool:
    proj = _project(_settings(tree))
    disabled = proj.get("disabledMcpServers")
    return isinstance(disabled, list)


def root_disabled_present(tree: dict[str, str]) -> bool:
    doc = _get_json(tree, CLAUDE_ROOT_REL)
    return isinstance(doc.get("disabledMcpServers"), list)


def detect_fingerprints(tree: dict[str, str]) -> list[dict[str, Any]]:
    """Each hit records two signals. A single marker is not enough."""
    hits: list[dict[str, Any]] = []
    skill_present = any(
        k.startswith("skills/") and k.endswith("/SKILL.md") and tree.get(k)
        for k in tree
    )
    market_absent = MARKET_REL not in tree
    if skill_present and market_absent:
        hits.append(
            {
                "id": FP_COPIED_SKILLS,
                "marker": "skills/*/SKILL.md present",
                "discriminator": "marketplace/marketplace.harness.json absent",
            }
        )

    mcp_file = MCP_JSON_REL in tree
    if mcp_file and not mcp_in_settings(tree):
        hits.append(
            {
                "id": FP_MCP_JSON,
                "marker": ".mcp.json present",
                "discriminator": "mcpServers live in .mcp.json, not settings projects",
            }
        )

    if root_disabled_present(tree) and not per_project_disabled(tree):
        hits.append(
            {
                "id": FP_ROOT_DISABLED,
                "marker": "claude.json root disabledMcpServers",
                "discriminator": "no per-project disabledMcpServers (root key is inert on this estate)",
            }
        )

    if DISPATCH_REL in tree:
        hits.append(
            {
                "id": FP_PRE_DISPATCH,
                "marker": "hooks/_dispatch/manifest.json",
                "discriminator": "dispatch directory shape, not current hooks/manifest.json",
            }
        )
    return hits


def is_current(tree: dict[str, str]) -> bool:
    required = (
        PLUGIN_REL,
        MARKET_REL,
        SKILL_REL,
        HOOK_REL,
        HOOKS_MANIFEST,
        SETTINGS_REL,
    )
    if any(r not in tree for r in required):
        return False
    if MCP_JSON_REL in tree:
        return False
    if DISPATCH_REL in tree:
        return False
    if root_disabled_present(tree):
        return False
    return True


def classify(tree: dict[str, str]) -> dict[str, Any]:
    hits = detect_fingerprints(tree)
    ids = [h["id"] for h in hits]
    if len(hits) > 1:
        return {
            "kind": AMBIGUOUS,
            "fingerprints": ids,
            "hits": hits,
            "reason": "two-or-more-fingerprints",
        }
    if len(hits) == 1:
        return {
            "kind": LEGACY,
            "fingerprints": ids,
            "hits": hits,
            "reason": ids[0],
        }
    if is_current(tree):
        return {
            "kind": CURRENT,
            "fingerprints": [],
            "hits": [],
            "reason": "current-layout",
        }
    return {
        "kind": NO_PATH,
        "fingerprints": [],
        "hits": [],
        "reason": "no-legacy-fingerprint-and-not-current",
    }


def extract_user_data(tree: dict[str, str], clean: dict[str, str]) -> dict[str, Any]:
    clean_skill_lines = set(lines_of(clean.get(SKILL_REL, "")))
    skill_extra = [
        ln for ln in lines_of(tree.get(SKILL_REL, "")) if ln not in clean_skill_lines
    ]

    mcp: dict[str, Any] = {}
    disabled: list[str] = []
    if MCP_JSON_REL in tree:
        doc = _get_json(tree, MCP_JSON_REL)
        if isinstance(doc.get("mcpServers"), dict):
            mcp = dict(doc["mcpServers"])
        if isinstance(doc.get("disabledMcpServers"), list):
            disabled = list(doc["disabledMcpServers"])

    settings = _settings(tree)
    proj = _project(settings)
    if not mcp and isinstance(proj.get("mcpServers"), dict):
        mcp = dict(proj["mcpServers"])
    if not disabled and isinstance(proj.get("disabledMcpServers"), list):
        disabled = list(proj["disabledMcpServers"])

    if CLAUDE_ROOT_REL in tree:
        root = _get_json(tree, CLAUDE_ROOT_REL)
        if not disabled and isinstance(root.get("disabledMcpServers"), list):
            disabled = list(root["disabledMcpServers"])

    user_settings = {
        k: v
        for k, v in settings.items()
        if k not in ("enabledPlugins", "projects")
    }

    hooks_doc: dict[str, Any]
    if DISPATCH_REL in tree:
        hooks_doc = _get_json(tree, DISPATCH_REL)
    elif HOOKS_MANIFEST in tree:
        hooks_doc = _get_json(tree, HOOKS_MANIFEST)
    else:
        hooks_doc = {"hooks": ["pre-tool"], "mounts": ["fs"]}

    return {
        "skill_extra_lines": skill_extra,
        "skill_extra_lines": skill_extra,
        "mcp_servers": mcp,
        "mcp_servers": mcp,
        "disabled_mcp": disabled,
        "disabled_mcp": disabled,
        "user_settings": user_settings,
        "hooks_manifest": hooks_doc,
        "hooks_manifest": hooks_doc,
    }


def overlay_user_data(clean: dict[str, str], user: dict[str, Any]) -> dict[str, str]:
    out = dict(clean)
    skill = lf(out.get(SKILL_REL, ""))
    if skill and not skill.endswith("\n"):
        skill += "\n"
    for ln in user.get("skill_extra_lines") or []:
        if ln not in lines_of(skill):
            skill += ln + "\n"
    out[SKILL_REL] = skill

    settings = _get_json(out, SETTINGS_REL) if SETTINGS_REL in out else {}
    for k, v in (user.get("user_settings") or {}).items():
        settings[k] = v
    projects = settings.setdefault("projects", {})
    if not isinstance(projects, dict):
        projects = {}
        settings["projects"] = projects
    proj = projects.setdefault(PROFILE, {})
    if not isinstance(proj, dict):
        proj = {}
        projects[PROFILE] = proj
    if user.get("mcp_servers"):
        proj["mcpServers"] = user["mcp_servers"]
    elif "mcpServers" not in proj:
        proj["mcpServers"] = {}
    proj["disabledMcpServers"] = list(user.get("disabled_mcp") or [])
    out[SETTINGS_REL] = dump(settings)

    hooks = user.get("hooks_manifest") or {"hooks": ["pre-tool"], "mounts": ["fs"]}
    out[HOOKS_MANIFEST] = dump(hooks)
    return out


def _ensure_settings(tree: dict[str, str]) -> dict:
    settings = _settings(tree)
    if "enabledPlugins" not in settings:
        settings["enabledPlugins"] = {"harness": True}
    settings.setdefault("projects", {})
    if not isinstance(settings["projects"], dict):
        settings["projects"] = {}
    settings["projects"].setdefault(PROFILE, {})
    if not isinstance(settings["projects"][PROFILE], dict):
        settings["projects"][PROFILE] = {}
    return settings


def apply_v1(tree: dict[str, str], templates: dict[str, str]) -> dict[str, str]:
    out = dict(tree)
    if MARKET_REL not in out:
        out[MARKET_REL] = templates[MARKET_REL]
    return out


def inverse_v1(tree: dict[str, str], before_had_market: bool) -> dict[str, str]:
    out = dict(tree)
    if not before_had_market:
        out.pop(MARKET_REL, None)
    return out


def apply_v2(tree: dict[str, str], templates: dict[str, str]) -> dict[str, str]:
    out = dict(tree)
    if MCP_JSON_REL not in out:
        return out
    doc = _get_json(out, MCP_JSON_REL)
    settings = _ensure_settings(out)
    proj = settings["projects"][PROFILE]
    servers = dict(proj.get("mcpServers") or {})
    incoming = doc.get("mcpServers") if isinstance(doc.get("mcpServers"), dict) else {}
    servers.update(incoming)
    proj["mcpServers"] = servers
    if isinstance(doc.get("disabledMcpServers"), list):
        proj["disabledMcpServers"] = list(doc["disabledMcpServers"])
    elif "disabledMcpServers" not in proj:
        proj["disabledMcpServers"] = []
    out[SETTINGS_REL] = dump(settings)
    del out[MCP_JSON_REL]
    return out


def inverse_v2(tree: dict[str, str], saved_mcp: dict[str, Any] | None) -> dict[str, str]:
    out = dict(tree)
    if saved_mcp is None:
        return out
    out[MCP_JSON_REL] = dump(saved_mcp)
    settings = _ensure_settings(out)
    proj = settings["projects"][PROFILE]
    proj.pop("mcpServers", None)
    proj.pop("disabledMcpServers", None)
    out[SETTINGS_REL] = dump(settings)
    return out


def apply_v3(tree: dict[str, str], templates: dict[str, str]) -> dict[str, str]:
    out = dict(tree)
    if CLAUDE_ROOT_REL not in out:
        return out
    root = _get_json(out, CLAUDE_ROOT_REL)
    disabled = root.get("disabledMcpServers")
    settings = _ensure_settings(out)
    proj = settings["projects"][PROFILE]
    if isinstance(disabled, list):
        proj["disabledMcpServers"] = list(disabled)
    out[SETTINGS_REL] = dump(settings)
    rest = {k: v for k, v in root.items() if k != "disabledMcpServers"}
    if rest:
        out[CLAUDE_ROOT_REL] = dump(rest)
    else:
        del out[CLAUDE_ROOT_REL]
    return out


def inverse_v3(tree: dict[str, str], saved_root: dict[str, Any] | None) -> dict[str, str]:
    out = dict(tree)
    if saved_root is None:
        return out
    out[CLAUDE_ROOT_REL] = dump(saved_root)
    settings = _ensure_settings(out)
    proj = settings["projects"][PROFILE]
    proj.pop("disabledMcpServers", None)
    out[SETTINGS_REL] = dump(settings)
    return out


def apply_v4(tree: dict[str, str], templates: dict[str, str]) -> dict[str, str]:
    out = dict(tree)
    if DISPATCH_REL not in out:
        return out
    doc = _get_json(out, DISPATCH_REL)
    out[HOOKS_MANIFEST] = dump(doc if doc else {"hooks": ["pre-tool"], "mounts": ["fs"]})
    if HOOK_REL not in out:
        out[HOOK_REL] = templates[HOOK_REL]
    del out[DISPATCH_REL]
    return out


def inverse_v4(
    tree: dict[str, str],
    saved_dispatch: str | None,
    *,
    had_hook: bool = True,
) -> dict[str, str]:
    out = dict(tree)
    if saved_dispatch is None:
        return out
    out[DISPATCH_REL] = saved_dispatch
    out.pop(HOOKS_MANIFEST, None)
    if not had_hook:
        out.pop(HOOK_REL, None)
    return out


def _needed_steps(kind_reason: str) -> list[str]:
    return {
        FP_COPIED_SKILLS: [STEP_V1],
        FP_MCP_JSON: [STEP_V2],
        FP_ROOT_DISABLED: [STEP_V3],
        FP_PRE_DISPATCH: [STEP_V4],
    }.get(kind_reason, [])


def migrate(
    tree: dict[str, str],
    templates: dict[str, str],
    *,
    skip_unknown: bool = False,
) -> dict[str, Any]:
    before = classify(tree)
    if before["kind"] == CURRENT:
        return {
            "status": CURRENT,
            "tree": dict(tree),
            "steps_run": [],
            "before": before,
            "after": before,
            "reported": True,
            "skipped": False,
        }
    if before["kind"] == AMBIGUOUS:
        return {
            "status": AMBIGUOUS,
            "tree": dict(tree),
            "steps_run": [],
            "before": before,
            "after": before,
            "reported": True,
            "skipped": False,
            "reason": "ambiguous-fingerprints-must-not-be-silently-resolved",
        }
    if before["kind"] == NO_PATH:
        if skip_unknown:
            return {
                "status": "OK",
                "tree": dict(tree),
                "steps_run": [],
                "before": before,
                "after": before,
                "reported": False,
                "skipped": True,
                "reason": "mutant-skip-unknown",
            }
        return {
            "status": NO_PATH,
            "tree": dict(tree),
            "steps_run": [],
            "before": before,
            "after": before,
            "reported": True,
            "skipped": False,
            "reason": before["reason"],
        }

    out = dict(tree)
    steps_run: list[str] = []
    for step in _needed_steps(before["reason"]):
        if step == STEP_V1:
            out = apply_v1(out, templates)
        elif step == STEP_V2:
            out = apply_v2(out, templates)
        elif step == STEP_V3:
            out = apply_v3(out, templates)
        elif step == STEP_V4:
            out = apply_v4(out, templates)
        steps_run.append(step)

    after = classify(out)
    return {
            "status": after["kind"],
            "tree": out,
            "steps_run": steps_run,
            "steps_run": steps_run,
            "before": before,
            "after": after,
            "reported": True,
            "skipped": False,
        }


def migrate_idempotent(tree: dict[str, str], templates: dict[str, str]) -> dict[str, Any]:
    first = migrate(tree, templates)
    second = migrate(first["tree"], templates)
    equal = trees_equal(first["tree"], second["tree"])
    return {
        "first": first,
        "second": second,
        "idempotent": equal,
        "first_census": census(first["tree"]),
        "second_census": census(second["tree"]),
    }


def round_trip(
    tree: dict[str, str],
    templates: dict[str, str],
    *,
    broken_v1_inverse: bool = False,
) -> dict[str, Any]:
    """Apply then inverse. broken_v1_inverse deletes skills (known-bad)."""
    before = classify(tree)
    had_market = MARKET_REL in tree
    saved_mcp = _get_json(tree, MCP_JSON_REL) if MCP_JSON_REL in tree else None
    saved_root = _get_json(tree, CLAUDE_ROOT_REL) if CLAUDE_ROOT_REL in tree else None
    saved_dispatch = tree.get(DISPATCH_REL)
    had_hook = HOOK_REL in tree

    applied = migrate(tree, templates)
    out = dict(applied["tree"])
    for step in reversed(applied["steps_run"]):
        if step == STEP_V1:
            if broken_v1_inverse:
                out = {k: v for k, v in out.items() if not k.startswith("skills/")}
            else:
                out = inverse_v1(out, had_market)
        elif step == STEP_V2:
            out = inverse_v2(out, saved_mcp)
        elif step == STEP_V3:
            out = inverse_v3(out, saved_root)
        elif step == STEP_V4:
            out = inverse_v4(out, saved_dispatch, had_hook=had_hook)
    restored = trees_equal(out, tree)
    return {
        "restored": restored,
        "before": before,
        "steps": applied["steps_run"],
        "broken_v1_inverse": broken_v1_inverse,
        "original_census": census(tree),
        "restored_census": census(out),
    }


def comparison_report(
    historical: dict[str, str],
    migrated: dict[str, str],
    expected: dict[str, str],
) -> dict[str, Any]:
    mig_c = census(migrated)
    exp_c = census(expected)
    only_mig = sorted(set(mig_c) - set(exp_c))
    only_exp = sorted(set(exp_c) - set(mig_c))
    differ = sorted(p for p in set(mig_c) & set(exp_c) if mig_c[p] != exp_c[p])
    return {
        "byte_equivalent": mig_c == exp_c,
        "historical_paths": sorted(historical),
        "migrated_census": mig_c,
        "expected_census": exp_c,
        "only_in_migrated": only_mig,
        "only_in_expected": only_exp,
        "sha_mismatch_paths": differ,
        "only_in_migrated": only_mig,
        "only_in_expected": only_exp,
        "sha_mismatch_paths": differ,
    }
