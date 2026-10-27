"""LANE B / R-M09 (adjacent) probe: does monitorcore.bak-20260727-091532 hold unique bytes?

Read-only. For every file in the bak dir:
  * compare against the same-named file in the LIVE deployed monitorcore;
  * if it differs, ask git whether that exact blob exists in this repo's object DB
    (raw AND CRLF-normalised), i.e. whether the content is recoverable from history.
A file that is neither identical-to-live nor present-in-git is UNIQUE = deletion would lose it.

Detector control: a synthetic never-committed buffer must be reported as NOT-in-git.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

HOME = pathlib.Path(os.path.expanduser("~"))
REPO = pathlib.Path(__file__).resolve().parents[1]
BAK = HOME / ".agents/skills/workflow-monitor/monitorcore.bak-20260727-091532"
LIVE = HOME / ".agents/skills/workflow-monitor/monitorcore"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_blob_sha(data: bytes) -> str:
    p = subprocess.run(
        ["git", "hash-object", "-t", "blob", "--stdin"],
        input=data,
        capture_output=True,
        cwd=REPO,
    )
    return p.stdout.decode().strip()


def in_git(data: bytes) -> bool:
    s = git_blob_sha(data)
    if not s:
        return False
    p = subprocess.run(["git", "cat-file", "-e", s], capture_output=True, cwd=REPO)
    return p.returncode == 0


bak_files = sorted(p for p in BAK.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
live_names = {p.name for p in LIVE.glob("*.py")}

out: dict = {
    "bak": str(BAK),
    "bak_exists": BAK.is_dir(),
    "bak_file_count": len(bak_files),
    "bak_py_count": sum(1 for p in bak_files if p.suffix == ".py"),
    "live_py_count": len(live_names),
    "name_subset_of_live": sorted({p.name for p in bak_files if p.suffix == ".py"} - live_names),
    "identical_to_live": [],
    "differs_but_in_git": [],
    "differs_and_in_git_after_crlf_norm": [],
    "UNIQUE_not_in_live_and_not_in_git": [],
}

for p in bak_files:
    data = p.read_bytes()
    twin = LIVE / p.name
    if twin.is_file() and sha(twin.read_bytes()) == sha(data):
        out["identical_to_live"].append(p.name)
        continue
    if in_git(data):
        out["differs_but_in_git"].append(p.name)
        continue
    if in_git(data.replace(b"\r\n", b"\n")):
        out["differs_and_in_git_after_crlf_norm"].append(p.name)
        continue
    out["UNIQUE_not_in_live_and_not_in_git"].append(p.name)

out["counts"] = {k: len(v) for k, v in out.items() if isinstance(v, list)}
out["control_synthetic_buffer_reported_in_git"] = in_git(
    b"# lane-b synthetic control buffer never committed anywhere\n" + os.urandom(16).hex().encode()
)
# control 2: a definitely-committed blob must be found
committed = (REPO / "tools/monitorcore/monitorcore/monitors.py").read_bytes()
out["control_committed_blob_found_in_git"] = in_git(committed) or in_git(
    committed.replace(b"\r\n", b"\n")
)
# import-shadowing check: is the bak dir importable as `monitorcore`?
out["bak_dir_is_importable_as_monitorcore"] = BAK.name == "monitorcore"

print(json.dumps(out, indent=2))
