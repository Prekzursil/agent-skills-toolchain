#!/usr/bin/env python3
"""Two-source curation snapshot, A4 gateway import/export, and fail-to-start rollback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scenario import (
    EXPOSED_INACTIVE_MCP,
    KNOWN_DISABLED_MCP,
    KNOWN_DISABLED_PLUGIN,
    PROJECT,
    ROOT_INERT_DISABLE,
)

SETTINGS_RELS = (
    "home/.mcp.json",
    "home/.claude.json",
    "home/.claude/settings.json",
)
LIVE_PROCESS_REL = "live/processes.json"
LIVE_TOOLS_REL = "live/tools.json"
INDEX_REL = "gateway/index.json"
START_REL = "gateway/start-status.json"


def sha256_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_record(rec: dict) -> dict:
    keys = (
        "id",
        "kind",
        "name",
        "split",
        "settings_declared",
        "effective_enabled",
        "live_active",
        "never_destroy",
        "root_disabled_inert",
        "project_disabled",
    )
    return {k: rec[k] for k in keys}


def canonical_dumps(records: list[dict]) -> str:
    recs = [canonical_record(r) for r in records]
    recs.sort(key=lambda r: r["id"])
    return json.dumps(recs, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def records_digest(records: list[dict]) -> str:
    return sha256_text(canonical_dumps(records))


def record_tuples(records: list[dict]) -> list[tuple]:
    rows = [
        (r["id"], r["kind"], r["split"], bool(r["effective_enabled"]), bool(r["live_active"]), bool(r["never_destroy"]))
        for r in records
    ]
    rows.sort()
    return rows


def split_of(effective_enabled: bool, live_active: bool) -> str:
    if not effective_enabled:
        return "disabled"
    if live_active:
        return "active"
    return "exposed-inactive"


def snapshot_settings(estate: Path) -> dict:
    mcp = read_json(estate / "home/.mcp.json")
    claude = read_json(estate / "home/.claude.json")
    settings = read_json(estate / "home/.claude/settings.json")
    project = (claude.get("projects") or {}).get(PROJECT) or {}
    return {
        "mcp_servers": dict((mcp.get("mcpServers") or {})),
        "root_disabled": dict(claude.get("disabledMcpServers") or {}),
        "project_servers": dict(project.get("mcpServers") or {}),
        "project_disabled": dict(project.get("disabledMcpServers") or {}),
        "enabled_plugins": dict(settings.get("enabledPlugins") or {}),
    }


def snapshot_live(estate: Path) -> dict:
    proc = read_json(estate / LIVE_PROCESS_REL)
    tools = read_json(estate / LIVE_TOOLS_REL)
    running = sorted({p["name"] for p in (proc.get("processes") or []) if p.get("name")})
    tool_servers = sorted({t["server"] for t in (tools.get("tools") or []) if t.get("server")})
    reachable = sorted(set(tools.get("plugin_skills_reachable") or []))
    return {
        "running_mcp": running,
        "tool_servers": tool_servers,
        "plugin_skills_reachable": reachable,
    }


def merge_records(settings: dict, live: dict) -> dict:
    """Merge two sources. Disagreement that is NOT the exposed/active split is BLOCKED."""
    disagreements: list[dict] = []
    records: list[dict] = []

    mcp_names = sorted(set(settings["mcp_servers"]) | set(settings["project_servers"]))
    running = set(live["running_mcp"])
    tool_servers = set(live["tool_servers"])

    for name in mcp_names:
        root_listed = bool((settings["root_disabled"] or {}).get(name))
        project_disabled = bool((settings["project_disabled"] or {}).get(name))
        # AUD-0015: root disabledMcpServers is inert; per-project key wins.
        effective_enabled = not project_disabled
        live_active = name in running
        # Tool inventory is a second live field. A running process without tools
        # (or tools without a process) is contradiction, not a split to preserve.
        has_tools = name in tool_servers
        if live_active != has_tools:
            disagreements.append(
                {
                    "id": f"mcp:{name}",
                    "field": "process-vs-tool-inventory",
                    "running": live_active,
                    "has_tools": has_tools,
                }
            )
        if (not effective_enabled) and live_active:
            disagreements.append(
                {
                    "id": f"mcp:{name}",
                    "field": "disabled-but-running",
                    "effective_enabled": effective_enabled,
                    "live_active": live_active,
                }
            )
        split = split_of(effective_enabled, live_active)
        records.append(
            {
                "id": f"mcp:{name}",
                "kind": "mcp",
                "name": name,
                "settings_declared": True,
                "effective_enabled": effective_enabled,
                "live_active": live_active,
                "split": split,
                "never_destroy": split == "disabled",
                "root_disabled_inert": root_listed,
                "project_disabled": project_disabled,
                "signal1_settings": {
                    "declared_in_mcp_json": name in settings["mcp_servers"],
                    "declared_in_project": name in settings["project_servers"],
                    "root_disabled_listed": root_listed,
                    "project_disabled": project_disabled,
                    "effective_enabled": effective_enabled,
                },
                "signal2_live": {
                    "process_running": live_active,
                    "tools_present": has_tools,
                },
            }
        )

    plugins = settings["enabled_plugins"]
    reachable = set(live["plugin_skills_reachable"])
    for name in sorted(plugins):
        effective_enabled = bool(plugins[name])
        live_active = name in reachable
        if (not effective_enabled) and live_active:
            disagreements.append(
                {
                    "id": f"plugin:{name}",
                    "field": "disabled-but-reachable",
                    "effective_enabled": effective_enabled,
                    "live_active": live_active,
                }
            )
        if effective_enabled and not live_active:
            # enabled-but-unreachable is green-not-live, not the exposed/active MCP split
            disagreements.append(
                {
                    "id": f"plugin:{name}",
                    "field": "enabled-but-unreachable",
                    "effective_enabled": effective_enabled,
                    "live_active": live_active,
                }
            )
        split = split_of(effective_enabled, live_active)
        records.append(
            {
                "id": f"plugin:{name}",
                "kind": "plugin",
                "name": name,
                "settings_declared": True,
                "effective_enabled": effective_enabled,
                "live_active": live_active,
                "split": split,
                "never_destroy": split == "disabled",
                "root_disabled_inert": False,
                "project_disabled": not effective_enabled,
                "signal1_settings": {
                    "enabled_plugins_value": bool(plugins[name]),
                    "file": "home/.claude/settings.json",
                },
                "signal2_live": {
                    "skills_reachable": live_active,
                },
            }
        )

    digest = records_digest(records)
    tuples = record_tuples(records)
    count = len(records)
    if count != len(tuples):
        disagreements.append(
            {
                "id": "merge",
                "field": "count-vs-tuple",
                "count": count,
                "tuple_n": len(tuples),
            }
        )
    return {
        "records": records,
        "disagreements": disagreements,
        "blocked": bool(disagreements),
        "records_sha256": digest,
        "record_count": count,
        "record_tuples": tuples,
    }


def freeze_snapshot(estate: Path) -> dict:
    """Capture settings bytes AND live inventory BEFORE any mutation."""
    files = {}
    file_sha = {}
    for rel in SETTINGS_RELS + (LIVE_PROCESS_REL, LIVE_TOOLS_REL):
        text = (estate / rel).read_text(encoding="utf-8")
        files[rel] = text
        file_sha[rel] = sha256_text(text)
    settings = snapshot_settings(estate)
    live = snapshot_live(estate)
    merged = merge_records(settings, live)
    snap = {
        "files": files,
        "file_sha256": file_sha,
        "settings": settings,
        "live": live,
        "merged": merged,
    }
    write_json(estate / "freeze/snapshot.json", {
        "file_sha256": file_sha,
        "records_sha256": merged["records_sha256"],
        "record_count": merged["record_count"],
        "blocked": merged["blocked"],
        "running_mcp": live["running_mcp"],
        "plugin_skills_reachable": live["plugin_skills_reachable"],
    })
    (estate / "freeze/files").mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        dest = estate / "freeze/files" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
    return snap


MEDIATION = {
    "disabled": "never-activate",
    "exposed-inactive": "indexed-inactive",
    "active": "indexed-active",
}
SPLIT_FROM_MED = {v: k for k, v in MEDIATION.items()}


def import_into_gateway(records: list[dict], drop_never_activate: bool = False) -> dict:
    entries = []
    for rec in records:
        mediation = MEDIATION[rec["split"]]
        if drop_never_activate and mediation == "never-activate":
            continue
        entries.append(
            {
                "id": rec["id"],
                "kind": rec["kind"],
                "name": rec["name"],
                "mediation": mediation,
                "curation": canonical_record(rec),
            }
        )
    entries.sort(key=lambda e: e["id"])
    return {
        "format": "a4-gateway-index/v1",
        "resident_floor": ["gateway-core"],
        "drop_never_activate": drop_never_activate,
        "entries": entries,
    }


def export_from_gateway(index: dict) -> list[dict]:
    out = []
    for ent in index.get("entries") or []:
        med = ent["mediation"]
        split = SPLIT_FROM_MED[med]
        cur = dict(ent.get("curation") or {})
        effective = split != "disabled"
        live_active = split == "active"
        rec = {
            "id": ent["id"],
            "kind": ent["kind"],
            "name": ent["name"],
            "split": split,
            "settings_declared": True,
            "effective_enabled": effective,
            "live_active": live_active,
            "never_destroy": split == "disabled",
            "root_disabled_inert": bool(cur.get("root_disabled_inert")),
            "project_disabled": bool(cur.get("project_disabled")),
        }
        out.append(rec)
    out.sort(key=lambda r: r["id"])
    return out


def diff_records(before: list[dict], after: list[dict]) -> dict:
    a = {r["id"]: canonical_record(r) for r in before}
    b = {r["id"]: canonical_record(r) for r in after}
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    changed = []
    for i in sorted(set(a) & set(b)):
        if a[i] != b[i]:
            changed.append({"id": i, "before": a[i], "after": b[i]})
    equal = not missing and not extra and not changed
    d1 = records_digest(before)
    d2 = records_digest(after)
    t1 = record_tuples(before)
    t2 = record_tuples(after)
    digest_equal = d1 == d2
    tuple_equal = t1 == t2
    blocked = digest_equal != tuple_equal
    return {
        "equal": equal and digest_equal and tuple_equal,
        "blocked_signal_disagreement": blocked,
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "before_sha256": d1,
        "after_sha256": d2,
        "before_count": len(before),
        "after_count": len(after),
        "digest_equal": digest_equal,
        "tuple_equal": tuple_equal,
    }


def write_index(estate: Path, index: dict) -> None:
    write_json(estate / INDEX_REL, index)


def start_gateway(estate: Path, fail: bool) -> dict:
    """Simulate gateway start. fail=True is the ARC-0028 rollback trigger."""
    status = {
        "ok": not fail,
        "reason": "simulated-start-failure" if fail else "started",
        "index_present": (estate / INDEX_REL).is_file(),
    }
    write_json(estate / START_REL, status)
    if fail:
        # Partial cut-over debris: always-on spawn stopped AND a naive cut-over
        # rewrote enablement (all plugins true, project disable map cleared).
        # Rollback must restore freeze bytes; skipping settings restore must fail.
        write_json(estate / LIVE_PROCESS_REL, {"processes": []})
        tools = read_json(estate / LIVE_TOOLS_REL)
        tools["plugin_skills_reachable"] = []
        tools["tools"] = []
        write_json(estate / LIVE_TOOLS_REL, tools)
        settings = read_json(estate / "home/.claude/settings.json")
        plugins = dict(settings.get("enabledPlugins") or {})
        for k in list(plugins):
            plugins[k] = True
        settings["enabledPlugins"] = plugins
        write_json(estate / "home/.claude/settings.json", settings)
        claude = read_json(estate / "home/.claude.json")
        claude["disabledMcpServers"] = {}
        for proj in (claude.get("projects") or {}).values():
            if isinstance(proj, dict):
                proj["disabledMcpServers"] = {}
        write_json(estate / "home/.claude.json", claude)
    return status


def rollback(estate: Path, snap: dict, skip_settings: bool = False) -> dict:
    """Restore pre-change inventory after gateway fail-to-start."""
    restored_files = []
    if not skip_settings:
        for rel in SETTINGS_RELS:
            text = snap["files"][rel]
            dest = estate / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8", newline="\n")
            restored_files.append(rel)
    for rel in (LIVE_PROCESS_REL, LIVE_TOOLS_REL):
        text = snap["files"][rel]
        dest = estate / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
        restored_files.append(rel)
    idx = estate / INDEX_REL
    failed = estate / "gateway/index.json.failed"
    if idx.is_file():
        failed.write_bytes(idx.read_bytes())
        idx.unlink()
    start = {
        "ok": False,
        "reason": "rolled-back-after-start-failure",
        "index_present": False,
        "rolled_back": True,
    }
    write_json(estate / START_REL, start)

    file_ok = {}
    for rel in SETTINGS_RELS:
        live_sha = sha256_text((estate / rel).read_text(encoding="utf-8"))
        file_ok[rel] = live_sha == snap["file_sha256"][rel]
    proc = [p["name"] for p in read_json(estate / LIVE_PROCESS_REL).get("processes") or []]
    live_set = sorted(proc)
    want_set = sorted(snap["live"]["running_mcp"])
    process_ok = live_set == want_set
    settings_ok = all(file_ok.values()) if not skip_settings else (not all(file_ok.values()))
    if skip_settings:
        settings_ok = not all(
            sha256_text((estate / rel).read_text(encoding="utf-8")) == snap["file_sha256"][rel]
            for rel in SETTINGS_RELS
        )
        # skip_settings means we DID skip; control expects restoration to be incomplete.
        settings_restored = all(
            sha256_text((estate / rel).read_text(encoding="utf-8")) == snap["file_sha256"][rel]
            for rel in SETTINGS_RELS
        )
    else:
        settings_restored = all(file_ok.values())

    settings_obj = snapshot_settings(estate)
    plugin_disabled = settings_obj["enabled_plugins"].get(KNOWN_DISABLED_PLUGIN) is False
    mcp_project_disabled = bool(
        settings_obj["project_disabled"].get(KNOWN_DISABLED_MCP)
    )
    # Two signals: file-byte sha256 vs process-name set. Disagreement => BLOCKED.
    if skip_settings:
        blocked = False
        pass_ok = False
    else:
        blocked = settings_restored != process_ok
        pass_ok = settings_restored and process_ok and plugin_disabled and mcp_project_disabled and not (estate / INDEX_REL).is_file()

    return {
        "pass": pass_ok,
        "blocked_signal_disagreement": blocked,
        "settings_bytes_restored": settings_restored,
        "live_process_set_restored": process_ok,
        "file_sha_match": file_ok,
        "live_process_set": live_set,
        "want_process_set": want_set,
        "disabled_plugin_still_disabled": plugin_disabled,
        "disabled_mcp_still_disabled": mcp_project_disabled,
        "gateway_index_not_live": not (estate / INDEX_REL).is_file(),
        "skip_settings": skip_settings,
        "restored_files": restored_files,
    }


def domain_from_artifact(doc: dict) -> dict:
    """Domain payload may live under report (receipt_core) or at top-level (legacy)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    sample = report.get("sample")
    if not isinstance(sample, list):
        sample = doc.get("sample") if isinstance(doc.get("sample"), list) else []
    tests = report.get("tests")
    if not isinstance(tests, dict):
        tests = doc.get("tests") if isinstance(doc.get("tests"), dict) else {}
    return {"report": report, "sample": sample, "tests": tests}


def sample_row(rec: dict) -> dict:
    decision = {
        "active": "INDEX-AND-KEEP-RESIDENT-UNTIL-FIRST-DEACTIVATE",
        "exposed-inactive": "INDEX-DO-NOT-SPAWN",
        "disabled": "INDEX-AS-NEVER-ACTIVATE",
    }[rec["split"]]
    return {
        "id": rec["id"],
        "kind": rec["kind"],
        "name": rec["name"],
        "split": rec["split"],
        "settings_declared": rec["settings_declared"],
        "effective_enabled": rec["effective_enabled"],
        "live_active": rec["live_active"],
        "never_destroy": rec["never_destroy"],
        "decision": decision,
        "unique_identity_preserved": True,
        "root_disabled_inert": rec["root_disabled_inert"],
        "project_disabled": rec["project_disabled"],
        "signal1_settings": rec["signal1_settings"],
        "signal2_live": rec["signal2_live"],
        "reason": (
            "per-project disable is load-bearing"
            if rec["split"] == "disabled"
            else (
                "declared in settings but no live process: preserve exposed-inactive split"
                if rec["split"] == "exposed-inactive"
                else "settings declare enabled and live inventory confirms active"
            )
        ),
    }


def expected_invariants(records: list[dict]) -> dict:
    by_id = {r["id"]: r for r in records}
    fs = by_id["mcp:filesystem"]
    mem = by_id[f"mcp:{EXPOSED_INACTIVE_MCP}"]
    mcp_ab = by_id[f"mcp:{KNOWN_DISABLED_MCP}"]
    plug_ab = by_id[f"plugin:{KNOWN_DISABLED_PLUGIN}"]
    return {
        "filesystem_root_disable_inert": fs["root_disabled_inert"] is True and fs["effective_enabled"] is True and fs["split"] == "active",
        "memory_exposed_inactive": mem["split"] == "exposed-inactive" and mem["effective_enabled"] is True and mem["live_active"] is False,
        "mcp_agentbridge_disabled": mcp_ab["split"] == "disabled" and mcp_ab["never_destroy"] is True,
        "plugin_agentbridge_disabled": plug_ab["split"] == "disabled" and plug_ab["never_destroy"] is True,
        "filesystem_not_disabled_by_root": fs["id"] == f"mcp:{ROOT_INERT_DISABLE}",
    }
