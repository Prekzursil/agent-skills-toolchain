"""Allowlisted argv-only script runner with userspace intercept."""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]
BOOT = HERE / "boot.py"
DENY_EXIT = 78
WINDOWS_LIMITATION = (
    "Windows has no native OS-level process sandbox; IMP-0064 uses a "
    "userspace intercept that refuses disallowed spawn, write, and network "
    "and records FORBIDDEN_* codes. It is not a kernel jail."
)


def default_containment() -> dict:
    return {
        "os_process_sandbox": False,
        "windows_kernel_sandbox": False,
        "mechanism": "userspace-intercept",
        "limitation": WINDOWS_LIMITATION,
    }


class PolicyDenied(Exception):
    """Raised when a spawn/write/network check is outside the allowlist."""


@dataclass
class Policy:
    policy_id: str
    allowed_executables: list[str]
    allowed_write_roots: list[str]
    network_mode: str = "deny"
    endpoints: list = field(default_factory=list)
    description: str = ""


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    refused: bool = False

    def codes(self) -> list[str]:
        blob = f"{self.stderr}\n{self.stdout}"
        out = []
        for code in ("FORBIDDEN_SPAWN", "FORBIDDEN_WRITE", "FORBIDDEN_NETWORK"):
            if code in blob:
                out.append(code)
        return out


class CountingListener:
    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = 0
        self.accepted = 0
        self._srv: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def endpoint(self) -> list:
        return [self.host, self.port]

    def start(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, 0))
        srv.listen(8)
        srv.settimeout(0.2)
        self._srv = srv
        self.port = int(srv.getsockname()[1])

        def _loop() -> None:
            while not self._stop.is_set() and self._srv is not None:
                try:
                    conn, _addr = self._srv.accept()
                    self.accepted += 1
                    conn.close()
                except (TimeoutError, socket.timeout, OSError):
                    continue

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1)


def existing_executable(*candidates: str) -> str:
    for c in candidates:
        if c and (os.path.isfile(c) or shutil.which(c)):
            found = c if os.path.isfile(c) else shutil.which(c)
            if found:
                return found
    return sys.executable


def build_policy(
    policy_id: str,
    allowed_executables: list[str],
    allowed_write_roots: list[str],
    network_mode: str = "deny",
    endpoints: list | None = None,
    description: str = "",
    **_kwargs,
) -> Policy:
    return Policy(
        policy_id=policy_id,
        allowed_executables=list(allowed_executables),
        allowed_write_roots=list(allowed_write_roots),
        network_mode=network_mode,
        endpoints=list(endpoints or []),
        description=description,
    )


def _policy_obj(policy: Policy | dict | None) -> Policy:
    if isinstance(policy, Policy):
        return policy
    if isinstance(policy, dict):
        return build_policy(
            policy_id=str(policy.get("policy_id") or "anon"),
            allowed_executables=list(policy.get("allowed_executables") or []),
            allowed_write_roots=list(policy.get("allowed_write_roots") or []),
            network_mode=str(policy.get("network_mode") or "deny"),
            endpoints=list(policy.get("endpoints") or []),
        )
    return build_policy("empty", [], [])


def check_spawn(argv, policy=None) -> bool:
    pol = _policy_obj(policy)
    exe = str((argv or [""])[0] if argv else "")
    allowed = {os.path.normcase(os.path.abspath(x)) for x in pol.allowed_executables}
    if exe and os.path.normcase(os.path.abspath(exe)) not in allowed and exe not in pol.allowed_executables:
        if sys.executable not in pol.allowed_executables and exe != sys.executable:
            raise PolicyDenied(f"spawn denied: {exe}")
    return True


def check_write(path, policy=None) -> bool:
    pol = _policy_obj(policy)
    target = os.path.abspath(str(path))
    roots = [os.path.abspath(r) for r in pol.allowed_write_roots]
    if roots and not any(target == r or target.startswith(r.rstrip("\\/") + os.sep) for r in roots):
        raise PolicyDenied(f"write denied: {path}")
    return True


def check_network(host, port, policy=None) -> bool:
    pol = _policy_obj(policy)
    if str(pol.network_mode).lower() == "deny":
        raise PolicyDenied(f"network denied: {host}:{port}")
    return True


_POLICY_SCHEMA = {
    "type": "object",
    "required": ["schema_version"],
    "properties": {
        "schema_version": {"type": "integer"},
        "allow_spawn": {"type": "array"},
        "allow_write": {"type": "array"},
        "allow_connect": {"type": "array"},
        "windows_limitation": {"type": "string"},
    },
}


def validate_policy(policy: dict) -> dict:
    if jsonschema is None:
        raise RuntimeError("jsonschema is required to validate exec policy")
    jsonschema.validate(policy, _POLICY_SCHEMA)
    return policy


def write_script(path: Path | str, body: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8", newline="\n")
    return p


def write_canary(root: Path | str) -> tuple[Path, Path]:
    root_p = Path(root)
    root_p.mkdir(parents=True, exist_ok=True)
    marker = root_p / "canary.marker"
    script = root_p / "canary.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('CANARY\\n', encoding='utf-8')\n"
        "import time; time.sleep(8)\n",
        encoding="utf-8",
        newline="\n",
    )
    return script, marker


def oob_path_exists(path: Path | str) -> bool:
    return Path(path).exists()


def oob_canary_pids(canary: Path | str) -> list[int]:
    needle = str(canary)
    pids: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return pids
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        cmdline = entry / "cmdline"
        try:
            blob = cmdline.read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        if needle in blob.replace("\x00", " "):
            pids.append(int(entry.name))
    return pids


def run_script(
    policy: Policy,
    script: Path | str,
    args: Sequence[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> RunResult:
    env = os.environ.copy()
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    payload = {
        "policy_id": policy.policy_id,
        "allowed_executables": list(policy.allowed_executables),
        "allowed_write_roots": list(policy.allowed_write_roots),
        "network_mode": policy.network_mode,
        "endpoints": list(policy.endpoints),
    }
    env["IMP0064_POLICY_JSON"] = json.dumps(payload)
    argv = [sys.executable, "-B", str(BOOT), str(script), *(args or ())]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env)
    stdout = p.stdout or ""
    stderr = p.stderr or ""
    refused = p.returncode == DENY_EXIT or any(
        code in (stderr + stdout)
        for code in ("FORBIDDEN_SPAWN", "FORBIDDEN_WRITE", "FORBIDDEN_NETWORK")
    )
    return RunResult(
        exit_code=p.returncode,
        stdout=stdout,
        stderr=stderr,
        refused=refused,
    )
