"""Shared fixtures and measurements for TST-0175 named probes."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.plugin.cache_ownership import (  # noqa: E402
    MANIFEST_NAME,
    NAIVE_IMAGE,
    PAYLOAD_DIR,
    ROLLBACK_BLOBS,
    file_sha256,
    install_repair,
    rollback,
    tree_hash,
    update,
    write_manifest,
)

ART = REPO / "command-center/receipts/TST-0175.json"
SENTINEL = "SUCCESS:TST-0175"
CLI = REPO / "tools" / "plugin" / "cli.py"

USER_FILE = "user-data/notes.txt"
USER_CMD = "commands/hello.py"
OWNED_CACHE = "cache/derived/stale.bin"
OWNED_INDEX = "cache/index/stale.json"
FOREIGN_CACHE = "cache/foreign/keep.bin"
PKG_FILE = "pkg/plugin.json"


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def plant_profile(root: Path) -> dict[str, Any]:
    """Seed user data, user commands, owned caches, and a foreign cache file."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_manifest(root)
    user_notes = f"owner-notes-{secrets.token_hex(16)}\n"
    user_cmd = f"# user command {secrets.token_hex(8)}\nprint('hello')\n"
    cache_blob = secrets.token_bytes(48)
    foreign_blob = secrets.token_bytes(24)
    index_doc = json.dumps({"stale": True, "nonce": secrets.token_hex(8)}, sort_keys=True)
    pkg_v2 = json.dumps({"id": "demo", "version": "2.0.0"}, sort_keys=True) + "\n"
    pkg_v1 = json.dumps({"id": "demo", "version": "1.0.0"}, sort_keys=True) + "\n"

    _write(root / USER_FILE, user_notes)
    _write(root / USER_CMD, user_cmd)
    _write(root / OWNED_CACHE, cache_blob)
    _write(root / OWNED_INDEX, index_doc)
    _write(root / FOREIGN_CACHE, foreign_blob)
    _write(root / PKG_FILE, pkg_v2)
    _write(root / PAYLOAD_DIR / PKG_FILE, pkg_v2)
    _write(root / ROLLBACK_BLOBS / PKG_FILE, pkg_v1)
    _write(root / NAIVE_IMAGE / PKG_FILE, pkg_v1)

    planted = {
        USER_FILE: file_sha256(root / USER_FILE),
        USER_CMD: file_sha256(root / USER_CMD),
        OWNED_CACHE: file_sha256(root / OWNED_CACHE),
        OWNED_INDEX: file_sha256(root / OWNED_INDEX),
        FOREIGN_CACHE: file_sha256(root / FOREIGN_CACHE),
        PKG_FILE: file_sha256(root / PKG_FILE),
    }
    return {
        "root": str(root),
        "planted_sha256": planted,
        "user_surface_tree_hash": tree_hash(root, ("user-data", "commands")),
        "user_notes_preview_len": len(user_notes),
    }


def run_cli(cmd: list[str], root: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [
        sys.executable,
        "-B",
        str(CLI),
        *cmd,
        "--root",
        str(root),
    ]
    proc = subprocess.run(
        argv,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def surviving(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    return {
        "path": rel,
        "exists": path.is_file(),
        "sha256": file_sha256(path) if path.is_file() else None,
    }


def measure_repair_and_update(root: Path) -> dict[str, Any]:
    """Live CLI: install --repair, update, plus ownership mutants."""
    repair_root = root / "repair"
    update_root = root / "update"
    mutant_root = root / "mutant"
    missing_root = root / "missing-manifest"
    planted = plant_profile(repair_root)
    shutil.copytree(repair_root, update_root)
    shutil.copytree(repair_root, mutant_root)
    shutil.copytree(repair_root, missing_root)
    (missing_root / MANIFEST_NAME).unlink()
    want = planted["planted_sha256"]

    pre_repair = tree_hash(repair_root, ("user-data", "commands"))
    rc_repair, out_repair = run_cli(["install", "--repair"], repair_root)
    post_repair = tree_hash(repair_root, ("user-data", "commands"))

    pre_update = tree_hash(update_root, ("user-data", "commands"))
    rc_update, out_update = run_cli(["update"], update_root)
    post_update = tree_hash(update_root, ("user-data", "commands"))

    mutant = install_repair(mutant_root, honor_ownership=False)
    missing = update(missing_root)

    return {
        "planted_sha256": want,
        "repair": {
            "exit_code": rc_repair,
            "cli_tail": out_repair[-2000:],
            "user_tree_before": pre_repair,
            "user_tree_after": post_repair,
            "user_tree_identical": pre_repair == post_repair,
            "user_file": surviving(repair_root, USER_FILE),
            "user_cmd": surviving(repair_root, USER_CMD),
            "owned_cache": surviving(repair_root, OWNED_CACHE),
            "owned_index": surviving(repair_root, OWNED_INDEX),
            "foreign_cache": surviving(repair_root, FOREIGN_CACHE),
        },
        "update": {
            "exit_code": rc_update,
            "cli_tail": out_update[-2000:],
            "user_tree_before": pre_update,
            "user_tree_after": post_update,
            "user_tree_identical": pre_update == post_update,
            "user_file": surviving(update_root, USER_FILE),
            "owned_cache": surviving(update_root, OWNED_CACHE),
            "foreign_cache": surviving(update_root, FOREIGN_CACHE),
        },
        "mutant_no_ownership": mutant.to_dict(),
        "mutant_user_file": surviving(mutant_root, USER_FILE),
        "missing_manifest": missing.to_dict(),
    }


def measure_rollback(root: Path) -> dict[str, Any]:
    good = root / "good"
    naive = root / "naive"
    plant_profile(good)
    shutil.copytree(good, naive)
    pre_good = tree_hash(good, ("user-data", "commands"))
    rc, out = run_cli(["rollback"], good)
    post_good = tree_hash(good, ("user-data", "commands"))
    good_report = rollback(good)  # second call is idempotent
    naive_report = rollback(naive, naive_snapshot=True)
    return {
        "correct": {
            "exit_code": rc,
            "cli_tail": out[-2000:],
            "user_tree_before": pre_good,
            "user_tree_after": post_good,
            "user_tree_identical": pre_good == post_good,
            "user_file": surviving(good, USER_FILE),
            "user_cmd": surviving(good, USER_CMD),
            "pkg": surviving(good, PKG_FILE),
            "second_call": good_report.to_dict(),
        },
        "naive_wholesale": naive_report.to_dict(),
        "naive_user_file": surviving(naive, USER_FILE),
        "naive_user_cmd": surviving(naive, USER_CMD),
        "naive_pkg": surviving(naive, PKG_FILE),
    }


def require_receipt() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:TST-0175 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:TST-0175 receipt not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise SystemExit(f"FAILED:TST-0175 self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        raise SystemExit("FAILED:TST-0175 sentinel-absent")
    if doc.get("unit_id") != "TST-0175":
        raise SystemExit("FAILED:TST-0175 unit_id")
    return doc
