#!/usr/bin/env python3
"""Live both-states + listing matrix for TST-0200."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from fixtures import PACKAGE, dest_report, make_deep_dest, make_short_dest  # noqa: E402
from installer import (  # noqa: E402
    EXIT_MAX_PATH,
    EXIT_OK,
    EXIT_PARTIAL_NAIVE,
    LIMIT_NAME,
    POLICY_NAME,
    WIN32_MAX_PATH,
    install,
)
from listing import classify  # noqa: E402

INSTALLER = HERE / "installer.py"
LISTING = HERE / "listing.py"


def _cli(
    dest: Path,
    package_path: Path,
    *,
    long_paths_enabled: bool,
    naive_partial: bool = False,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str(INSTALLER),
        "--dest",
        str(dest),
        "--package",
        str(package_path),
        "--long-paths-enabled",
        "true" if long_paths_enabled else "false",
    ]
    if naive_partial:
        cmd.append("--naive-partial")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(HERE.parents[3]),
        capture_output=True,
        text=True,
        env=env,
    )
    stdout = (proc.stdout or "").strip()
    try:
        parsed = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        parsed = {"parse_error": True, "stdout": stdout[-2000:]}
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "stderr": (proc.stderr or "").strip(),
        "stdout_json": parsed,
        "message": (proc.stderr or "").strip()
        or (parsed.get("message") if isinstance(parsed, dict) else ""),
    }


def _list_cli(dest: Path, package_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(LISTING),
            "--dest",
            str(dest),
            "--package",
            str(package_path),
        ],
        cwd=str(HERE.parents[3]),
        capture_output=True,
        text=True,
        env=env,
    )
    stdout = (proc.stdout or "").strip()
    try:
        parsed = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        parsed = {"parse_error": True, "stdout": stdout[-2000:]}
    return {"exit_code": proc.returncode, "report": parsed}


def names_limit(text: str) -> bool:
    t = text or ""
    return (
        LIMIT_NAME in t
        and str(WIN32_MAX_PATH) in t
        and POLICY_NAME in t
    )


def run_matrix(tmp: Path | None = None) -> dict[str, Any]:
    own = tmp is None
    root = Path(tmp) if tmp else Path(tempfile.mkdtemp(prefix="tst0200-"))
    package_path = root / "package.json"
    package_path.write_text(json.dumps(PACKAGE, indent=1) + "\n", encoding="utf-8")

    short = make_short_dest(root / "s")
    deep = make_deep_dest(root / "d")
    naive_dest = root / "naive"

    short_meta = dest_report(short)
    deep_meta = dest_report(deep)

    short_cli = _cli(short, package_path, long_paths_enabled=False)
    short_list = classify(short, PACKAGE)
    short_list_cli = _list_cli(short, package_path)

    deep_off_cli = _cli(deep, package_path, long_paths_enabled=False)
    deep_off_list = classify(deep, PACKAGE)
    deep_off_list_cli = _list_cli(deep, package_path)
    # In-process API must agree with the CLI (same refusal, still no writes).
    deep_off_api = install(deep, PACKAGE, long_paths_enabled=False)

    deep_on = make_deep_dest(root / "on")
    deep_on_cli = _cli(deep_on, package_path, long_paths_enabled=True)
    deep_on_list = classify(deep_on, PACKAGE)

    naive_cli = _cli(
        naive_dest, package_path, long_paths_enabled=False, naive_partial=True
    )
    naive_list = classify(naive_dest, PACKAGE)

    message = str(deep_off_cli.get("message") or "")
    contract = {
        "short_succeeds": short_cli["exit_code"] == EXIT_OK
        and short_list["complete"]
        and short_list["state"] == "COMPLETE",
        "deep_off_refuses": deep_off_cli["exit_code"] == EXIT_MAX_PATH
        and deep_off_api["exit_code"] == EXIT_MAX_PATH,
        "deep_off_names_limit": names_limit(message)
        and names_limit(str(deep_off_api.get("message") or "")),
        "deep_off_not_partial": deep_off_list["state"] in {"ABSENT", "EMPTY"}
        and not deep_off_list["partial"]
        and deep_off_list["file_count"] == 0,
        "deep_on_complete": deep_on_cli["exit_code"] == EXIT_OK
        and deep_on_list["complete"],
        "listing_detects_naive_partial": naive_list["partial"]
        and naive_list["state"] == "PARTIAL"
        and naive_cli["exit_code"] == EXIT_PARTIAL_NAIVE,
        "listing_cli_agrees_short": (short_list_cli.get("report") or {}).get("state")
        == "COMPLETE",
        "listing_cli_agrees_deep_off": (deep_off_list_cli.get("report") or {}).get(
            "state"
        )
        in {"ABSENT", "EMPTY"},
        "short_in_budget": int(short_meta["longest_measured_chars"]) <= WIN32_MAX_PATH,
        "deep_over_budget": int(deep_meta["longest_measured_chars"]) > WIN32_MAX_PATH,
    }
    contract["holds"] = all(contract.values())

    out = {
        "package_files": sorted(PACKAGE),
        "short": {
            "meta": short_meta,
            "cli": {
                "exit_code": short_cli["exit_code"],
                "message": short_cli["message"],
            },
            "listing": {
                "state": short_list["state"],
                "file_count": short_list["file_count"],
                "complete": short_list["complete"],
                "partial": short_list["partial"],
            },
        },
        "deep_long_paths_false": {
            "meta": deep_meta,
            "cli": {
                "exit_code": deep_off_cli["exit_code"],
                "message": deep_off_cli["message"],
            },
            "api_exit_code": deep_off_api["exit_code"],
            "listing": {
                "state": deep_off_list["state"],
                "file_count": deep_off_list["file_count"],
                "complete": deep_off_list["complete"],
                "partial": deep_off_list["partial"],
                "empty_or_absent": deep_off_list["empty_or_absent"]
                or deep_off_list["state"] == "ABSENT",
            },
        },
        "deep_long_paths_true": {
            "cli": {
                "exit_code": deep_on_cli["exit_code"],
                "message": deep_on_cli["message"],
            },
            "listing": {
                "state": deep_on_list["state"],
                "file_count": deep_on_list["file_count"],
                "complete": deep_on_list["complete"],
                "partial": deep_on_list["partial"],
            },
        },
        "naive_partial_control": {
            "cli": {
                "exit_code": naive_cli["exit_code"],
                "message": naive_cli["message"],
            },
            "listing": {
                "state": naive_list["state"],
                "file_count": naive_list["file_count"],
                "complete": naive_list["complete"],
                "partial": naive_list["partial"],
                "wrote_rels": (naive_cli.get("stdout_json") or {}).get("wrote_rels"),
            },
        },
        "contract": contract,
    }
    if own:
        # Leave trees for debugging only when the caller owns tmp; default is
        # TemporaryDirectory in probes. Best-effort cleanup of our mkdtemp.
        try:
            import shutil

            shutil.rmtree(root, ignore_errors=True)
        except OSError:
            pass
    return out
