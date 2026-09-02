#!/usr/bin/env python3
"""Health checks for the disposable install target.

coherence: files, manifest, cache blob, hook, and user data must agree.
file_count: counts plugin files only — the weak check that reports a
hybrid as healthy. The unit names that false-healthy as the worst outcome.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hashes import sha256_bytes
from scenario import PLUGIN_RELS, USER_RELS, read_core_version


def _probe(pid: str, state: str, evidence: str) -> dict[str, str]:
    return {"id": pid, "state": state, "evidence": evidence}


def file_count_health(root: Path, expected_plugin_files: int = 3) -> dict[str, Any]:
    present = [rel for rel in PLUGIN_RELS if (root / rel).is_file()]
    ok = len(present) >= expected_plugin_files
    return {
        "ok": ok,
        "kind": "file-count-only",
        "plugin_files_present": len(present),
        "expected_plugin_files": expected_plugin_files,
        "probes": [
            _probe(
                "file-count",
                "SUCCESS" if ok else "FAILED",
                f"plugin files present={len(present)} expected>={expected_plugin_files}",
            )
        ],
    }


def coherence_health(root: Path, expected_version: str, user_sha256: dict[str, str]) -> dict[str, Any]:
    probes: list[dict[str, str]] = []

    def add(pid: str, ok: bool, evidence: str, blocked: bool = False) -> None:
        if blocked:
            state = "BLOCKED"
        else:
            state = "SUCCESS" if ok else "FAILED"
        probes.append(_probe(pid, state, evidence))

    try:
        files_ver = read_core_version(root)
        add("files-version", True, f"plugin/core.py VERSION={files_ver}")
    except (OSError, ValueError) as exc:
        files_ver = None
        add("files-version", False, f"unreadable: {type(exc).__name__}")

    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        man_ver = manifest.get("version")
        add("manifest-version", True, f"manifest.json version={man_ver}")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        man_ver = None
        add("manifest-version", False, f"unreadable: {type(exc).__name__}")

    try:
        resolved = json.loads((root / "cache" / "resolved.json").read_text(encoding="utf-8"))
        cache_ver = resolved.get("version")
        add("cache-resolved", True, f"cache/resolved.json version={cache_ver}")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        cache_ver = None
        add("cache-resolved", False, f"unreadable: {type(exc).__name__}")

    blob_ok = False
    blob_evidence = "cache blob missing"
    if cache_ver:
        blob_path = root / "cache" / "blobs" / f"{cache_ver}.json"
        try:
            blob = json.loads(blob_path.read_text(encoding="utf-8"))
            core = (root / "plugin" / "core.py").read_bytes()
            want = blob.get("core_sha256")
            got = sha256_bytes(core)
            blob_ok = want == got and blob.get("version") == cache_ver
            blob_evidence = f"blob version={blob.get('version')} sha match={want == got}"
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            blob_evidence = f"unreadable: {type(exc).__name__}"
    add("cache-blob-matches-files", blob_ok, blob_evidence)

    hook_ok = False
    try:
        hook = json.loads((root / "plugin" / "hook.json").read_text(encoding="utf-8"))
        hook_ok = hook.get("fires") is True and hook.get("version") == files_ver
        add(
            "hook-loadable",
            hook_ok,
            f"hook version={hook.get('version')} fires={hook.get('fires')}",
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        add("hook-loadable", False, f"unreadable: {type(exc).__name__}")

    versions = [v for v in (files_ver, man_ver, cache_ver) if v is not None]
    hybrid = len(set(versions)) > 1
    agree = (
        files_ver == expected_version
        and man_ver == expected_version
        and cache_ver == expected_version
        and not hybrid
    )
    add(
        "version-coherence",
        agree,
        (
            f"files={files_ver} manifest={man_ver} cache={cache_ver} "
            f"expected={expected_version} hybrid={hybrid}"
        ),
    )

    user_ok = True
    for rel, want in user_sha256.items():
        path = root / rel
        if not path.is_file():
            user_ok = False
            add("user-data", False, f"missing {rel}")
            continue
        got = sha256_bytes(path.read_bytes())
        match = got == want
        user_ok = user_ok and match
        add("user-data-" + rel.replace("/", "."), match, f"{rel} byte-identical={match}")

    any_blocked = any(p["state"] == "BLOCKED" for p in probes)
    any_failed = any(p["state"] == "FAILED" for p in probes)
    # Aggregate refuses healthy if any probe is BLOCKED or FAILED.
    ok = (not any_blocked) and (not any_failed) and agree and blob_ok and hook_ok and user_ok
    return {
        "ok": ok,
        "kind": "coherence",
        "expected_version": expected_version,
        "hybrid": hybrid,
        "files_version": files_ver,
        "manifest_version": man_ver,
        "cache_version": cache_ver,
        "probes": probes,
        "aggregate_refuses_blocked": True,
        "user_rels_checked": list(USER_RELS),
    }
