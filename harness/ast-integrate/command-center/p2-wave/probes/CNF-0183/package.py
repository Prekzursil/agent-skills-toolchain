"""Self-contained replication-package fixtures (CNF-0182 shape, authored here)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PAYLOAD = b"CNF-0183-payload-v1\n"
COUNT_TEXT = "17\n"
ADDEND = 25  # 17 + 25 == 42
TRUE_ID = "pkg-cnf0183-sha-sum"
FALSE_ID = "pkg-cnf0183-sha-sum-false"
INCOMPLETE_ID = "pkg-cnf0183-sha-sum-incomplete"

RUN_PY = '''#!/usr/bin/env python3
"""Claim runner: hash payload.bin and add 25 to count.txt. CWD is the package root."""
import hashlib
import json
import pathlib
import sys

payload = pathlib.Path("inputs/payload.bin").read_bytes()
n = int(pathlib.Path("inputs/count.txt").read_text(encoding="utf-8").strip())
digest = hashlib.sha256(payload).hexdigest()
total = n + 25
sys.stdout.write(json.dumps({"sha256": digest, "total": total}, sort_keys=True) + "\\n")
sys.exit(0 if total == 42 else 2)
'''


def normalize_stdout(raw: bytes) -> bytes:
    text = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    text = text.rstrip() + b"\n"
    return text


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def python_pin() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def capture_stdout(pkg_dir: Path) -> tuple[int, bytes]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-B", "run.py"],
        cwd=str(pkg_dir),
        env=env,
        capture_output=True,
        timeout=30,
    )
    return p.returncode, p.stdout or b""


def _write_tree(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "inputs").mkdir(parents=True, exist_ok=True)
    (dest / "inputs" / "payload.bin").write_bytes(PAYLOAD)
    (dest / "inputs" / "count.txt").write_text(COUNT_TEXT, encoding="utf-8", newline="\n")
    (dest / "run.py").write_text(RUN_PY, encoding="utf-8", newline="\n")


def true_package_dict(stdout_sha: str) -> dict:
    claim_hex = sha256_hex(PAYLOAD)
    return {
        "id": TRUE_ID,
        "claim": (
            f"sha256(inputs/payload.bin)={claim_hex} and "
            f"int(inputs/count.txt)+{ADDEND}==42"
        ),
        "pins": {"python": python_pin(), "interpreter": "python3"},
        "inputs": ["inputs/payload.bin", "inputs/count.txt", "run.py"],
        "command": ["python3", "-B", "run.py"],
        "expected": {"exit_code": 0, "stdout_sha256": stdout_sha},
        "normalizers": ["crlf-to-lf", "ensure-trailing-newline"],
        "pass_criterion": (
            "exit_code==0 and sha256(normalize(stdout))==expected.stdout_sha256"
        ),
    }


def write_package_json(dest: Path, pkg: dict) -> None:
    (dest / "package.json").write_text(
        json.dumps(pkg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def materialize(dest: Path, mode: str = "true") -> dict:
    """Write a package tree. mode: true | incomplete | false.

    Authoring-time: the true tree is executed once to pin expected.stdout_sha256.
    incomplete: package.json still declares inputs/count.txt; the file is removed.
    false: claim + expected.stdout_sha256 mutated to 64 zero hex chars.
    """
    if dest.exists():
        for child in sorted(dest.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass
    _write_tree(dest)
    code, stdout = capture_stdout(dest)
    if code != 0:
        raise RuntimeError(f"authoring run failed rc={code} err={stdout[:200]!r}")
    stdout_sha = sha256_hex(normalize_stdout(stdout))
    pkg = true_package_dict(stdout_sha)
    if mode == "false":
        pkg = dict(pkg)
        pkg["id"] = FALSE_ID
        pkg["claim"] = (
            f"sha256(inputs/payload.bin)={'0' * 64} and "
            f"int(inputs/count.txt)+{ADDEND}==42"
        )
        pkg["expected"] = {"exit_code": 0, "stdout_sha256": "0" * 64}
    elif mode == "incomplete":
        pkg = dict(pkg)
        pkg["id"] = INCOMPLETE_ID
    elif mode != "true":
        raise ValueError(f"unknown mode {mode}")
    write_package_json(dest, pkg)
    if mode == "incomplete":
        (dest / "inputs" / "count.txt").unlink()
    return pkg
