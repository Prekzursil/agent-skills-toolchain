"""Throwaway plugin payload fixtures for IMP-0023 install probes."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def v1_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v1\nbody-one\n",
        "hooks/post.py": "print('v1')\n",
    }


def v2_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v2\nbody-two\n",
        "hooks/post.py": "print('v2')\n",
        "skills/beta/SKILL.md": "# beta\n",
    }


def write_tree(root: Path, files: dict[str, str]) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
    return root


def expected_census(files: dict[str, str]) -> dict[str, str]:
    return {rel: _sha(body.encode("utf-8")) for rel, body in files.items()}


def projection_for(payload: Path, plugin_id: str = "demo-plugin") -> dict[str, Any]:
    payload = Path(payload)
    entries = []
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(payload).as_posix()
        entries.append(
            {
                "source": rel,
                "live": rel,
                "sha256": _sha(path.read_bytes()),
            }
        )
    return {"plugin_id": plugin_id, "entries": entries}


def write_projection(path: Path, projection: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def kill_mid_activate(home: Path, payload: Path, proj_path: Path, pause: Path) -> int:
    """Start installer subprocess, pause before live swap, SIGKILL, return nonzero."""
    pause = Path(pause)
    pause.write_text("hold\n", encoding="utf-8")
    env = os.environ.copy()
    env["IMP0023_PAUSE_BEFORE_SWAP"] = str(pause)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "import os, time, sys\n"
        "from pathlib import Path\n"
        "p = Path(os.environ['IMP0023_PAUSE_BEFORE_SWAP'])\n"
        "while p.is_file():\n"
        "    time.sleep(0.02)\n"
        "sys.exit(0)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    try:
        proc.send_signal(signal.SIGKILL)
    except Exception:
        proc.kill()
    rc = proc.wait(timeout=10)
    return rc if rc != 0 else 1
