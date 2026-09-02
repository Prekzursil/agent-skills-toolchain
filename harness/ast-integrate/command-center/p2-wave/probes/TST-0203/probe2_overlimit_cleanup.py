#!/usr/bin/env python3
"""Probe 2: over-limit member 41 aborts, names the member, leaves no residue.

Two independent signals:
  (a) extractor process exit and message naming OVERLIMIT-member-041
  (b) os.walk of the extraction root after the process returns

Both-states / negative control in the same run:
  * cleanup=False leaves the 40 already-written members
  * naive tarfile.extractall leaves residue (Linux writes the long member)
  * live extractor with cleanup leaves dest absent
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
from path_budget import DECLARED_PATH_LENGTH_LIMIT  # noqa: E402

OUT = HERE / "probe2-overlimit-cleanup.raw.json"


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"FAILED:TST-0203-probe2 {msg}")
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
        "probe": "probe2-overlimit-cleanup",
        "unit_id": "TST-0203",
        "pass": False,
        "limit": DECLARED_PATH_LENGTH_LIMIT,
    }
    with tempfile.TemporaryDirectory(prefix="t203-p2-", dir="/tmp") as td:
        td_path = Path(td)
        dest = td_path / "outA"
        naive_dest = td_path / "outB"
        noclean_dest = td_path / "outC"
        archive = td_path / "bad.tar"
        spec = X.build_overlimit_archive(archive, dest)
        dest.mkdir()
        noclean_dest.mkdir()

        naive = X.naive_extractall(archive, naive_dest)
        noclean = X.extract_without_cleanup(archive, noclean_dest)
        noclean_files = independent_files(noclean_dest)

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
        combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        residue = independent_files(dest)
        dest_exists = dest.exists()
        try:
            result = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            result = {}

        payload.update(
            {
                "signal_a": {
                    "kind": "extractor-exit-and-message",
                    "exit_code": proc.returncode,
                    "stdout": (proc.stdout or "").strip(),
                    "stderr": (proc.stderr or "").strip(),
                    "offending_member": spec["offending_member"],
                    "message_names_member": spec["offending_member"] in combined,
                    "token_in_message": X.OVERLIMIT_TOKEN in combined,
                },
                "signal_b": {
                    "kind": "independent-os-walk",
                    "dest_exists": dest_exists,
                    "residue_files": residue,
                    "residue_count": len(residue),
                },
                "negative_naive_extractall": {
                    "count": naive["count"],
                    "left_residue": naive["count"] >= spec["prefix_count"],
                },
                "negative_no_cleanup": {
                    "written_before_abort": noclean.members_written_before_abort,
                    "walk_count": len(noclean_files),
                    "left_the_40": len(noclean_files) == spec["prefix_count"],
                },
                "prefix_count": spec["prefix_count"],
                "offending_length": spec["offending_length"],
                "extractor_json": result,
            }
        )

        if proc.returncode != 2:
            return fail(payload, f"want exit 2 got {proc.returncode}")
        if spec["offending_member"] not in combined:
            return fail(payload, "message does not name the offending member")
        if X.OVERLIMIT_TOKEN not in combined:
            return fail(payload, "message missing OVERLIMIT-member-041 token")
        if residue:
            return fail(payload, f"residue after cleanup: {residue[:8]}")
        if dest_exists:
            return fail(payload, "extraction root still exists after fail-closed")
        if naive["count"] < spec["prefix_count"]:
            return fail(payload, "naive extractall did not leave prefix members")
        if len(noclean_files) != spec["prefix_count"]:
            return fail(
                payload,
                f"no-cleanup walk {len(noclean_files)} != {spec['prefix_count']}",
            )
        if result.get("members_written_before_abort") != spec["prefix_count"]:
            return fail(
                payload,
                f"written_before_abort={result.get('members_written_before_abort')}",
            )
        payload["pass"] = True
        payload["two_signals"] = True
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print(
            f"exit={proc.returncode} named={X.OVERLIMIT_TOKEN} "
            f"residue={len(residue)} naive={naive['count']} "
            f"noclean={len(noclean_files)} written_before="
            f"{result.get('members_written_before_abort')}"
        )
        print(
            "SUCCESS:TST-0203-probe2 over-limit member named; tree removed"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
