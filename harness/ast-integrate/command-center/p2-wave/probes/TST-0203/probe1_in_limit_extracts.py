#!/usr/bin/env python3
"""Probe 1: in-limit archive extracts fully (both-states control).

Signal: extractor process exit 0 plus an independent listing of the
destination proving every member is present.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import extract as X  # noqa: E402

OUT = HERE / "probe1-in-limit.raw.json"


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"FAILED:TST-0203-probe1 {msg}")
    return 1


def independent_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, name), root))
    return sorted(found)


def main() -> int:
    payload: dict = {
        "probe": "probe1-in-limit-extracts",
        "unit_id": "TST-0203",
        "pass": False,
    }
    with tempfile.TemporaryDirectory(prefix="t203-p1-", dir="/tmp") as td:
        td_path = Path(td)
        dest = td_path / "out"
        archive = td_path / "ok.tar"
        spec = X.build_in_limit_archive(archive, dest)
        dest.mkdir()
        cmd = [
            sys.executable,
            "-B",
            str(PLUGIN / "extract.py"),
            "--archive",
            str(archive),
            "--dest",
            str(dest),
        ]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        listing = independent_files(dest)
        payload.update(
            {
                "command": cmd[-6:],
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "").strip(),
                "stderr": (proc.stderr or "").strip(),
                "independent_file_count": len(listing),
                "expected_count": spec["count"],
                "independent_names": listing,
                "archive_names": spec["names"],
            }
        )
        if proc.returncode != 0:
            return fail(payload, f"in-limit extract exit {proc.returncode}")
        try:
            result = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as exc:
            return fail(payload, f"unparseable extractor stdout: {exc}")
        payload["extractor_ok"] = bool(result.get("ok"))
        if not result.get("ok"):
            return fail(payload, f"extractor ok=false: {result}")
        if len(listing) != spec["count"]:
            return fail(
                payload,
                f"listing {len(listing)} != expected {spec['count']}",
            )
        if sorted(listing) != sorted(spec["names"]):
            return fail(payload, "independent listing != archive members")
        payload["pass"] = True
        payload["both_states_control"] = "in-limit archive extracts fully"
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print(
            f"extracted={len(listing)} exit={proc.returncode} "
            f"ok={result.get('ok')}"
        )
        print("SUCCESS:TST-0203-probe1 in-limit archive extracts fully")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
