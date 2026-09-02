#!/usr/bin/env python3
"""Probe 2: removal of a revoked package leaves the user-data tree identical.

Signal (b) of the catalog evidence_requirement: an independent pre/post hash
of the user-data tree (os.walk + sha256 in this probe, not the SUT census).

Regression seed (_USER-PROMPTS.md:11347): wholesale restore removes existing
commands or user data. The live owned-set remover must not.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MKT = REPO / "tools" / "marketplace"
CLI = MKT / "revocation_health.py"

OUT = HERE / "probe2-removal-preserves-user-data.raw.json"
UNIT = "TST-0221"
REVOKED = "tst0221-revoked-widget"
CANARY = "TST-0221-USER-DATA-CANARY"
USER_CMD = f"plugins/{REVOKED}/commands/user-created.md"


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:TST-0221-probe2 {msg}")
    return 1


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def last_json(text: str) -> dict:
    blob = (text or "").strip()
    idx = blob.find("{")
    if idx < 0:
        return {}
    try:
        doc, _ = json.JSONDecoder().raw_decode(blob[idx:])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def independent_census(root: Path) -> dict[str, str]:
    """Probe-owned walker. Does not import revocation_health.census."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git"}]
        for name in filenames:
            path = Path(dirpath) / name
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            out[rel] = hashlib.sha256(raw).hexdigest()
    return dict(sorted(out.items()))


def independent_tree_digest(root: Path) -> tuple[str, dict[str, str]]:
    files = independent_census(root)
    blob = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(blob).hexdigest(), files


def main() -> int:
    payload: dict = {
        "probe": "probe2-removal-preserves-user-data",
        "unit_id": UNIT,
        "pass": False,
    }
    with tempfile.TemporaryDirectory(prefix="t221-p2-", dir="/tmp") as td:
        root = Path(td)
        live_root = root / "live"
        wholesale_root = root / "wholesale"
        seed = run_cli(["seed", "--root", str(live_root)])
        if seed.returncode != 0:
            return fail(payload, f"seed exit {seed.returncode}")
        paths = last_json(seed.stdout)
        home = Path(paths["home"])
        upstream = Path(paths["upstream"])
        shutil.copytree(live_root, wholesale_root)

        rev = run_cli(["revoke", "--upstream", str(upstream)])
        if rev.returncode != 0:
            return fail(payload, "revoke failed")
        hc = run_cli(
            [
                "health-check",
                "--home",
                str(home),
                "--upstream",
                str(upstream),
                "--mode",
                "live",
            ]
        )
        hc_doc = last_json(hc.stdout)
        if REVOKED not in list(hc_doc.get("named_packages") or []):
            return fail(payload, "health-check did not name revoked package before remove")

        user_data = home / "user-data"
        pre_digest, pre_files = independent_tree_digest(user_data)
        user_cmd = home / USER_CMD
        if not user_cmd.is_file():
            return fail(payload, "user-created command missing before remove")
        pre_cmd = user_cmd.read_bytes()
        notes = user_data / "notes.txt"
        if not notes.is_file() or CANARY.encode("ascii") not in notes.read_bytes():
            return fail(payload, "user-data canary missing before remove")

        payload["pre"] = {
            "user_data_digest": pre_digest,
            "user_data_files": pre_files,
            "user_command_sha256": hashlib.sha256(
                pre_cmd.replace(b"\r\n", b"\n")
            ).hexdigest(),
            "canary_present": True,
        }

        rm = run_cli(
            [
                "remove",
                "--home",
                str(home),
                "--upstream",
                str(upstream),
                "--package",
                REVOKED,
                "--mode",
                "set-difference",
            ]
        )
        rm_doc = last_json(rm.stdout)
        payload["remove"] = {
            "exit_code": rm.returncode,
            "mode": rm_doc.get("mode"),
            "removed": rm_doc.get("removed"),
            "foreign_preserved": rm_doc.get("foreign_preserved"),
            "error": rm_doc.get("error"),
            "stdout": (rm.stdout or "").strip()[-2000:],
        }
        if rm.returncode != 0:
            return fail(payload, f"remove exit {rm.returncode}")
        if rm_doc.get("mode") != "set-difference":
            return fail(payload, f"remove mode {rm_doc.get('mode')}")
        if not rm_doc.get("foreign_preserved"):
            return fail(payload, "SUT reported foreign_preserved=false")

        post_digest, post_files = independent_tree_digest(user_data)
        still_cmd = user_cmd.is_file()
        post_cmd = user_cmd.read_bytes() if still_cmd else b""
        canary_after = notes.is_file() and CANARY.encode("ascii") in notes.read_bytes()
        payload["post"] = {
            "user_data_digest": post_digest,
            "user_data_files": post_files,
            "user_command_present": still_cmd,
            "user_command_byte_identical": still_cmd and post_cmd == pre_cmd,
            "canary_present": canary_after,
            "owned_plugin_json_gone": not (
                home / f"plugins/{REVOKED}/plugin.json"
            ).exists(),
        }
        if post_digest != pre_digest:
            return fail(
                payload,
                f"user-data digest changed {pre_digest} -> {post_digest}",
            )
        if post_files != pre_files:
            return fail(payload, "user-data file map changed")
        if not still_cmd or post_cmd != pre_cmd:
            return fail(payload, "user-created command was removed or mutated")
        if not canary_after:
            return fail(payload, "user-data canary missing after remove")
        if (home / f"plugins/{REVOKED}/plugin.json").exists():
            return fail(payload, "owned plugin.json still present")

        wholesale_paths = last_json(
            # wholesale world already copied; locate home/upstream from copy
            json.dumps(
                {
                    "home": str(wholesale_root / "home"),
                    "upstream": str(wholesale_root / "upstream"),
                }
            )
        )
        w_home = Path(wholesale_paths["home"])
        w_up = Path(wholesale_paths["upstream"])
        w_pre, w_pre_files = independent_tree_digest(w_home / "user-data")
        w_cmd_before = (w_home / USER_CMD).is_file()
        w = run_cli(
            [
                "remove",
                "--home",
                str(w_home),
                "--upstream",
                str(w_up),
                "--package",
                REVOKED,
                "--mode",
                "wholesale",
            ]
        )
        w_post, w_post_files = independent_tree_digest(w_home / "user-data")
        payload["wholesale_negative_control"] = {
            "exit_code": w.returncode,
            "pre_digest": w_pre,
            "post_digest": w_post,
            "pre_files": w_pre_files,
            "post_files": w_post_files,
            "user_command_before": w_cmd_before,
            "user_command_after": (w_home / USER_CMD).is_file(),
            "home_exists_after": w_home.exists(),
            "destroyed_user_data": w_post != w_pre or not w_post_files,
        }
        if w.returncode == 0:
            return fail(payload, "wholesale mutant exited 0 (must not be delivery)")
        if w_post == w_pre and w_post_files:
            return fail(
                payload,
                "wholesale mutant preserved user-data; regression seed does not fire",
            )
        if (w_home / USER_CMD).is_file():
            return fail(payload, "wholesale mutant left the user-created command")

        payload["pass"] = True
        payload["signal_b"] = {
            "kind": "independent-user-data-tree-hash",
            "pre": pre_digest,
            "post": post_digest,
            "byte_identical": pre_digest == post_digest,
            "files": sorted(pre_files),
        }
        payload["regression_seed"] = (
            "wholesale restore deleted user-data and the user-created command; "
            "owned-set removal did not"
        )
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"user-data {pre_digest[:12]}=={post_digest[:12]} "
            f"wholesale_destroyed={payload['wholesale_negative_control']['destroyed_user_data']}"
        )
        print("SUCCESS:TST-0221-probe2 removal preserves user-data tree hash")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
