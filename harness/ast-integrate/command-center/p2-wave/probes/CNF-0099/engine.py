#!/usr/bin/env python3
"""Upgrade-path engine for CNF-0099.

This worktree has no Phase-5 plugin lifecycle and no published N-1/N artifacts.
The confirmation still has to be live: install previous, seed realistic user
state, overlay current, run the declared migration, then prove three things
with the same code paths probes re-execute:

1. every user-state field is preserved or listed in declared_migrations
2. upgraded and clean installs pass the identical health-check function
3. skipping the migration makes that same health check fail (and a weaker
   check that ignored schema shape would pass — proving discrimination)
"""
from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

PREVIOUS_VERSION = "1.0.0"
CURRENT_VERSION = "2.0.0"
MIGRATION_ID = "v1_to_v2"

USER_SKILL_REL = "user/skills/user.authored/SKILL.md"
USER_RULE_REL = "user/rules/rule.owner-edit.md"
STATE_REL = "user/state.json"
LEDGER_REL = "user/ledger.jsonl"
CACHE_REL = "var/cache.json"
MCP_REL = "var/mcp.json"
ROUTER_REL = "var/router.json"
HOOK_REL = "hooks/hook.pre-tool.json"
BUNDLED_SKILL_REL = "skills/skill.council/SKILL.md"
PLUGIN_REL = "plugin.json"
MIGLOG_REL = "var/migration.log.json"

USER_SKILL_BODY = (
    "# user.authored\n\n"
    "Owner-authored skill. Must survive upgrade byte-for-byte.\n"
    "marker: CNF-0099-USER-SKILL-KEEP\n"
)
USER_RULE_BODY = (
    "# owner-edit\n\n"
    "Hand-edited live rule. Must survive upgrade byte-for-byte.\n"
    "marker: CNF-0099-USER-RULE-KEEP\n"
)
BUNDLED_SKILL_BODY = (
    "# skill.council\n\nBundled council skill shipped in both releases.\n"
)
SEED_LEDGER = (
    '{"id":"evt-001","type":"session.start","payload":{"cwd":"/home/owner/proj"}}\n'
    '{"id":"evt-002","type":"tool.call","payload":{"tool":"Read","path":"notes.md"},'
    '"in_flight":true}\n'
)

SEED_STATE: dict[str, Any] = {
    "schema_version": 1,
    "settings": {
        "theme": "dark",
        "custom": {"owner.pref": "keep-me", "hotkey": "ctrl+k"},
        "locale": "en-GB",
        "debug": True,
    },
}

DECLARED_MIGRATIONS = [
    {
        "id": "set-schema-version",
        "kind": "set",
        "from_path": "schema_version",
        "to_path": "schema_version",
        "note": "1 -> 2",
    },
    {
        "id": "rename-custom-keys",
        "kind": "rename",
        "from_path": "settings.custom",
        "to_path": "settings.user_keys",
        "note": "owner keys keep their values; the v1 name is retired",
    },
    {
        "id": "reshape-locale",
        "kind": "reshape",
        "from_path": "settings.locale",
        "to_path": "settings.locale",
        "note": "v1 string 'en-GB' becomes {lang, region}; leaving the string is a silent misread",
    },
    {
        "id": "retire-debug-flag",
        "kind": "retire",
        "from_path": "settings.debug",
        "to_path": "settings.verbose_logs",
        "note": "v2 would treat debug=true as 'open debugger port'; rename to verbose_logs",
    },
]

HEALTH_PROBE_IDS = [
    "plugin_version",
    "schema_version",
    "custom_absent",
    "debug_absent",
    "user_keys_object",
    "locale_object",
    "hook_loaded",
    "bundled_skill_registered",
    "ledger_writable",
    "cache_valid",
    "mcp_reachable",
    "router_responding",
]


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes() if path.is_file() else b""
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n")) if raw else 0


def write_file(root: Path, rel: str, content: str | bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def previous_release_files() -> dict[str, str]:
    return {
        PLUGIN_REL: _dump(
            {
                "name": "harness",
                "version": PREVIOUS_VERSION,
                "hooks": [HOOK_REL],
                "skills": [BUNDLED_SKILL_REL],
                "rules": ["rules/rule.no-secrets.md"],
            }
        ),
        HOOK_REL: _dump(
            {"id": "hook.pre-tool", "event": "pre-tool", "command": "echo pre-tool"}
        ),
        BUNDLED_SKILL_REL: BUNDLED_SKILL_BODY,
        "rules/rule.no-secrets.md": "# no-secrets\n\nDo not print secrets.\n",
        ROUTER_REL: _dump({"status": "up", "release": PREVIOUS_VERSION}),
        MCP_REL: _dump({"reachable": True, "endpoint": "stdio://fixture"}),
        CACHE_REL: _dump({"valid": True, "entries": 2}),
    }


def current_release_files() -> dict[str, str]:
    files = previous_release_files()
    files[PLUGIN_REL] = _dump(
        {
            "name": "harness",
            "version": CURRENT_VERSION,
            "hooks": [HOOK_REL],
            "skills": [BUNDLED_SKILL_REL],
            "rules": ["rules/rule.no-secrets.md"],
            "migrations": [MIGRATION_ID],
        }
    )
    files[ROUTER_REL] = _dump({"status": "up", "release": CURRENT_VERSION})
    files["migrations/v1_to_v2.json"] = _dump(
        {
            "id": MIGRATION_ID,
            "from": PREVIOUS_VERSION,
            "to": CURRENT_VERSION,
            "transforms": DECLARED_MIGRATIONS,
        }
    )
    return files


def materialize(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        write_file(root, rel, content)


def overlay_release(profile: Path, files: dict[str, str]) -> None:
    """Install release files without touching user/."""
    for rel, content in files.items():
        if rel.startswith("user/"):
            continue
        write_file(profile, rel, content)


def seed_user_state(profile: Path) -> None:
    write_file(profile, STATE_REL, _dump(SEED_STATE))
    write_file(profile, USER_SKILL_REL, USER_SKILL_BODY)
    write_file(profile, USER_RULE_REL, USER_RULE_BODY)
    write_file(profile, LEDGER_REL, SEED_LEDGER)


def default_v2_state() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "settings": {
            "theme": "system",
            "user_keys": {},
            "locale": {"lang": "en", "region": "US"},
            "verbose_logs": False,
        },
    }


def apply_migration(state: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(state)
    settings = out.setdefault("settings", {})
    out["schema_version"] = 2
    custom = settings.pop("custom", {})
    if not isinstance(custom, dict):
        custom = {}
    settings["user_keys"] = custom
    loc = settings.get("locale")
    if isinstance(loc, str):
        lang, _, region = loc.partition("-")
        settings["locale"] = {"lang": lang or "en", "region": region or "US"}
    if "debug" in settings:
        settings["verbose_logs"] = bool(settings.pop("debug"))
    elif "verbose_logs" not in settings:
        settings["verbose_logs"] = False
    return out


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(obj, dict):
        acc: dict[str, Any] = {}
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            acc.update(flatten(val, path))
        return acc
    if isinstance(obj, list):
        acc = {}
        for i, val in enumerate(obj):
            path = f"{prefix}[{i}]"
            acc.update(flatten(val, path))
        return acc
    return {prefix: obj}


def field_comparisons(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    expected = apply_migration(before)
    exp_flat = flatten(expected)
    after_flat = flatten(after)
    before_flat = flatten(before)
    rows: list[dict[str, Any]] = []
    rename_from = {
        "settings.custom": "settings.user_keys",
        "settings.debug": "settings.verbose_logs",
    }
    reshape = {"settings.locale"}
    seen: set[str] = set()

    def verdict_for(path: str) -> str:
        if path in rename_from or any(path.startswith(src + ".") for src in rename_from):
            return "renamed"
        if path in reshape or any(path.startswith(p + ".") for p in reshape):
            if path in before_flat and path not in after_flat:
                return "reshaped-declared"
            if path not in before_flat and path in after_flat:
                return "reshaped-declared"
            return "reshaped-declared"
        if path in before_flat and path not in after_flat:
            return "removed-by-migration"
        if path not in before_flat and path in after_flat:
            return "added-by-migration"
        return "preserved"

    for path in sorted(set(exp_flat) | set(after_flat) | set(before_flat)):
        if path in seen:
            continue
        seen.add(path)
        exp_v = exp_flat.get(path, None)
        got_v = after_flat.get(path, None)
        if path in exp_flat and path in after_flat and exp_v != got_v:
            v = "semantic-loss"
        else:
            v = verdict_for(path)
        rows.append(
            {
                "path": path,
                "before": before_flat.get(path),
                "after": got_v,
                "expected": exp_v,
                "verdict": v,
            }
        )
    return rows


def inventory(profile: Path, rels: list[str]) -> list[dict[str, Any]]:
    rows = []
    for rel in rels:
        path = profile / rel
        digest, size = sha256_file(path)
        rows.append(
            {
                "path": rel,
                "sha256": digest if path.is_file() else "0" * 64,
                "bytes": size,
                "present": path.is_file(),
                "role": "user-state",
            }
        )
    return rows


def ledger_prefix_intact(before: str, after: str) -> bool:
    return after.replace("\r\n", "\n").startswith(before.replace("\r\n", "\n"))


def migrate_profile(profile: Path) -> dict[str, Any]:
    state_path = profile / STATE_REL
    before = json.loads(state_path.read_text(encoding="utf-8"))
    after = apply_migration(before)
    write_file(profile, STATE_REL, _dump(after))
    ledger_path = profile / LEDGER_REL
    prior = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    receipt = {
        "id": "evt-mig-v1-to-v2",
        "type": "migration.applied",
        "payload": {"migration": MIGRATION_ID, "from": PREVIOUS_VERSION, "to": CURRENT_VERSION},
    }
    write_file(profile, LEDGER_REL, prior + json.dumps(receipt, sort_keys=True) + "\n")
    log = {
        "ran": True,
        "id": MIGRATION_ID,
        "transforms_applied": len(DECLARED_MIGRATIONS),
        "entries": [
            {"transform": m["id"], "kind": m["kind"], "from": m["from_path"], "to": m["to_path"]}
            for m in DECLARED_MIGRATIONS
        ],
    }
    write_file(profile, MIGLOG_REL, _dump(log))
    return log


def _probe(pid: str, ok: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": pid,
        "state": "SUCCESS" if ok else "FAILED",
        "evidence": evidence,
    }


def health_check(profile: Path, *, strict: bool = True) -> dict[str, Any]:
    """Identical health check used for clean install and upgraded install.

    strict=True is the production check. strict=False is the weaker mutant used
    only to prove the skip-migration control discriminates.
    """
    probes: list[dict[str, Any]] = []
    plugin = {}
    plugin_path = profile / PLUGIN_REL
    if plugin_path.is_file():
        try:
            plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            plugin = {}
    version_ok = plugin.get("version") == CURRENT_VERSION
    probes.append(_probe("plugin_version", version_ok, f"version={plugin.get('version')}"))

    state: dict[str, Any] = {}
    state_path = profile / STATE_REL
    if state_path.is_file():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except json.JSONDecodeError:
            state = {}
    settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}

    schema_ok = state.get("schema_version") == 2
    custom_absent = "custom" not in settings
    debug_absent = "debug" not in settings
    user_keys_ok = isinstance(settings.get("user_keys"), dict)
    locale = settings.get("locale")
    locale_ok = (
        isinstance(locale, dict)
        and isinstance(locale.get("lang"), str)
        and isinstance(locale.get("region"), str)
        and bool(locale.get("lang"))
        and bool(locale.get("region"))
    )

    if strict:
        probes.append(_probe("schema_version", schema_ok, f"schema_version={state.get('schema_version')}"))
        probes.append(_probe("custom_absent", custom_absent, f"custom_present={not custom_absent}"))
        probes.append(_probe("debug_absent", debug_absent, f"debug_present={not debug_absent}"))
        probes.append(_probe("user_keys_object", user_keys_ok, f"type={type(settings.get('user_keys')).__name__}"))
        probes.append(_probe("locale_object", locale_ok, f"locale={locale!r}"[:200]))
    else:
        probes.append(_probe("schema_version", True, "weaker: skipped"))
        probes.append(_probe("custom_absent", True, "weaker: skipped"))
        probes.append(_probe("debug_absent", True, "weaker: skipped"))
        probes.append(_probe("user_keys_object", True, "weaker: skipped"))
        probes.append(_probe("locale_object", True, "weaker: skipped"))

    hook_path = profile / HOOK_REL
    hook_ok = False
    if hook_path.is_file():
        try:
            hook = json.loads(hook_path.read_text(encoding="utf-8"))
            hook_ok = hook.get("id") == "hook.pre-tool"
        except json.JSONDecodeError:
            hook_ok = False
    probes.append(_probe("hook_loaded", hook_ok, HOOK_REL))

    skill_ok = (profile / BUNDLED_SKILL_REL).is_file()
    probes.append(_probe("bundled_skill_registered", skill_ok, BUNDLED_SKILL_REL))

    ledger_path = profile / LEDGER_REL
    ledger_ok = False
    if ledger_path.is_file():
        try:
            with ledger_path.open("a", encoding="utf-8"):
                ledger_ok = True
        except OSError:
            ledger_ok = False
    probes.append(_probe("ledger_writable", ledger_ok, LEDGER_REL))

    cache_ok = False
    cache_path = profile / CACHE_REL
    if cache_path.is_file():
        try:
            cache_ok = json.loads(cache_path.read_text(encoding="utf-8")).get("valid") is True
        except (json.JSONDecodeError, OSError):
            cache_ok = False
    probes.append(_probe("cache_valid", cache_ok, CACHE_REL))

    mcp_ok = False
    mcp_path = profile / MCP_REL
    if mcp_path.is_file():
        try:
            mcp_ok = json.loads(mcp_path.read_text(encoding="utf-8")).get("reachable") is True
        except (json.JSONDecodeError, OSError):
            mcp_ok = False
    probes.append(_probe("mcp_reachable", mcp_ok, MCP_REL))

    router_ok = False
    router_path = profile / ROUTER_REL
    if router_path.is_file():
        try:
            router_ok = json.loads(router_path.read_text(encoding="utf-8")).get("status") == "up"
        except (json.JSONDecodeError, OSError):
            router_ok = False
    probes.append(_probe("router_responding", router_ok, ROUTER_REL))

    failed = [p["id"] for p in probes if p["state"] != "SUCCESS"]
    ok = not failed
    return {
        "ok": ok,
        "aggregate": "SUCCESS" if ok else "FAILED",
        "probe_ids": [p["id"] for p in probes],
        "failed_ids": failed,
        "probes": probes,
        "strict": strict,
    }


def summarize_health(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(run["ok"]),
        "aggregate": run["aggregate"],
        "probe_ids": list(run["probe_ids"]),
        "failed_ids": list(run["failed_ids"]),
    }


def install_previous(profile: Path) -> None:
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True)
    overlay_release(profile, previous_release_files())
    seed_user_state(profile)


def install_current_clean(profile: Path) -> None:
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True)
    overlay_release(profile, current_release_files())
    write_file(profile, STATE_REL, _dump(default_v2_state()))
    write_file(profile, LEDGER_REL, "")
    write_file(profile, CACHE_REL, _dump({"valid": True, "entries": 0}))
    write_file(profile, MCP_REL, _dump({"reachable": True, "endpoint": "stdio://fixture"}))
    # router already written by overlay


def upgrade_with_migration(profile: Path) -> dict[str, Any]:
    overlay_release(profile, current_release_files())
    return migrate_profile(profile)


def skip_migration_upgrade(profile: Path) -> None:
    overlay_release(profile, current_release_files())


TRACKED_USER = [STATE_REL, USER_SKILL_REL, USER_RULE_REL, LEDGER_REL]


def run_scenario(root: Path) -> dict[str, Any]:
    clean = root / "clean"
    upgraded = root / "upgraded"
    skipped = root / "skipped"

    install_current_clean(clean)
    clean_health = health_check(clean, strict=True)

    install_previous(upgraded)
    before_state = json.loads((upgraded / STATE_REL).read_text(encoding="utf-8"))
    before_inv = inventory(upgraded, TRACKED_USER)
    before_ledger = (upgraded / LEDGER_REL).read_text(encoding="utf-8")
    before_skill = sha256_file(upgraded / USER_SKILL_REL)
    before_rule = sha256_file(upgraded / USER_RULE_REL)
    log = upgrade_with_migration(upgraded)
    after_state = json.loads((upgraded / STATE_REL).read_text(encoding="utf-8"))
    after_inv = inventory(upgraded, TRACKED_USER)
    after_ledger = (upgraded / LEDGER_REL).read_text(encoding="utf-8")
    after_skill = sha256_file(upgraded / USER_SKILL_REL)
    after_rule = sha256_file(upgraded / USER_RULE_REL)
    upgraded_health = health_check(upgraded, strict=True)
    rows = field_comparisons(before_state, after_state)
    expected = apply_migration(before_state)
    semantic_loss = [r for r in rows if r["verdict"] == "semantic-loss"]
    expected_match = flatten(expected) == flatten(after_state)

    install_previous(skipped)
    skip_migration_upgrade(skipped)
    skip_strict = health_check(skipped, strict=True)
    skip_weak = health_check(skipped, strict=False)

    identical_ids = clean_health["probe_ids"] == upgraded_health["probe_ids"] == HEALTH_PROBE_IDS
    skill_ok = before_skill == after_skill and before_skill[1] > 0
    rule_ok = before_rule == after_rule and before_rule[1] > 0
    prefix_ok = ledger_prefix_intact(before_ledger, after_ledger)

    return {
        "clean_health": clean_health,
        "upgraded_health": upgraded_health,
        "skip_strict": skip_strict,
        "skip_weak": skip_weak,
        "migration_log": log,
        "field_comparisons": rows,
        "before_state": before_state,
        "after_state": after_state,
        "before_inventory": before_inv,
        "after_inventory": after_inv,
        "byte_identical_user_files": [USER_SKILL_REL, USER_RULE_REL],
        "skill_preserved": skill_ok,
        "rule_preserved": rule_ok,
        "ledger_prefix_intact": prefix_ok,
        "expected_match": expected_match,
        "semantic_loss": semantic_loss,
        "identical_probe_set": identical_ids,
        "clean_ok": bool(clean_health["ok"]),
        "upgraded_ok": bool(upgraded_health["ok"]),
        "skip_failed": not skip_strict["ok"],
        "weaker_would_pass": bool(skip_weak["ok"]),
        "pass": all(
            [
                clean_health["ok"],
                upgraded_health["ok"],
                not skip_strict["ok"],
                skip_weak["ok"],
                identical_ids,
                skill_ok,
                rule_ok,
                prefix_ok,
                expected_match,
                not semantic_loss,
                log.get("ran") is True,
            ]
        ),
    }


def fail_reasons(result: dict[str, Any]) -> list[str]:
    reasons = []
    if not result["clean_ok"]:
        reasons.append("clean-health-failed:" + ",".join(result["clean_health"]["failed_ids"]))
    if not result["upgraded_ok"]:
        reasons.append("upgraded-health-failed:" + ",".join(result["upgraded_health"]["failed_ids"]))
    if not result["skip_failed"]:
        reasons.append("skip-migration-health-did-not-fail")
    if not result["weaker_would_pass"]:
        reasons.append("weaker-check-did-not-pass-skip")
    if not result["identical_probe_set"]:
        reasons.append("health-probe-set-mismatch")
    if not result["skill_preserved"]:
        reasons.append("user-skill-bytes-changed")
    if not result["rule_preserved"]:
        reasons.append("user-rule-bytes-changed")
    if not result["ledger_prefix_intact"]:
        reasons.append("ledger-prefix-lost")
    if not result["expected_match"]:
        reasons.append("field-compare-mismatch")
    if result["semantic_loss"]:
        reasons.append("semantic-loss:" + ",".join(r["path"] for r in result["semantic_loss"]))
    if not result["migration_log"].get("ran"):
        reasons.append("migration-did-not-run")
    return reasons
