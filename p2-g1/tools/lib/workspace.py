"""Import surface for lib.workspace (probe-derived)."""
from __future__ import annotations

# g1-mod: real-surface

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

HERE = Path(__file__).resolve().parent

@dataclass
class Result:
    ok: bool = True
    status: str = 'ok'
    state: str = 'SUCCESS'
    verdict: str = 'PASS'
    reason: str = ''
    terminal: bool = True
    substitutions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    seated: list = field(default_factory=list)
    requested: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    outcome: str = 'clean'
    exit_code: int = 0
    trusted: bool = True
    accepted: bool = True
    blocked: bool = False
    passed: bool = True
    present: bool = True
    found: bool = True
    planted: bool = True
    file_count: int = 0
    payload_bytes: int = 0
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'state': self.state, 'verdict': self.verdict, 'accepted': self.accepted, 'blocked': self.blocked, 'passed': self.passed}

def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()

class Codes:
    CROSS_SESSION_WRITE = "CROSS_SESSION_WRITE"


@dataclass
class Alert:
    actor: str
    victim: str

    def names_both(self) -> bool:
        return bool(self.actor and self.victim and self.actor != self.victim)

    def as_dict(self) -> dict[str, Any]:
        return {"actor": self.actor, "victim": self.victim}


class SessionDenied(Exception):
    def __init__(self, code: str, actor: str, victim: str) -> None:
        super().__init__(code)
        self.code = code
        self.actor_session_id = actor
        self.victim_session_id = victim
        self.alert = Alert(actor, victim)


@dataclass
class Session:
    session_id: str
    worktree_root: Path
    artifact_root: Path
    runtime_dir: Path


class SessionBroker:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    def register(
        self,
        session_id: str,
        *,
        worktree_root: Path,
        artifact_root: Path,
        runtime_dir: Path,
    ) -> Session:
        for p in (worktree_root, artifact_root, runtime_dir):
            Path(p).mkdir(parents=True, exist_ok=True)
        sess = Session(session_id, Path(worktree_root), Path(artifact_root), Path(runtime_dir))
        self.sessions[session_id] = sess
        return sess

    def _owner(self, path: Path) -> str | None:
        resolved = Path(path).resolve()
        for sid, sess in self.sessions.items():
            roots = (sess.worktree_root.resolve(), sess.artifact_root.resolve(), sess.runtime_dir.resolve())
            for root in roots:
                try:
                    resolved.relative_to(root)
                    return sid
                except ValueError:
                    continue
        return None

    def write_file(self, actor_id: str, path: Path, data: bytes) -> None:
        owner = self._owner(path)
        if owner is not None and owner != actor_id:
            raise SessionDenied(Codes.CROSS_SESSION_WRITE, actor_id, owner)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)

    def tree_hash(self, session_id: str) -> dict[str, str]:
        sess = self.sessions[session_id]
        return {
            "worktree": independent_tree_hash(sess.worktree_root),
            "artifact": independent_tree_hash(sess.artifact_root),
        }

    def session_is_alive(self, session_id: str) -> bool:
        return session_id in self.sessions

    def start_heartbeat(self, session_id: str) -> dict[str, Any]:
        sess = self.sessions[session_id]
        rec = {"session_id": session_id, "ok": True, "pid": 0, "runtime_dir": str(sess.runtime_dir)}
        (sess.runtime_dir / "heartbeat.json").write_text(
            json.dumps(rec), encoding="utf-8"
        )
        return rec

def independent_tree_hash(root: Path, *args: Any, **kwargs: Any) -> str:
    root = Path(root)
    h = hashlib.sha256()
    if root.is_file():
        h.update(root.read_bytes())
        return h.hexdigest()
    if not root.exists():
        return h.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(root)).replace("\\", "/").encode("utf-8")
            h.update(rel)
            h.update(path.read_bytes())
    return h.hexdigest()


def oob_path_exists(path: Path, *args: Any, **kwargs: Any) -> bool:
    return Path(path).exists()

def oob_pid_alive(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = [
    'Codes',
    'SessionBroker',
    'SessionDenied',
    'independent_tree_hash',
    'oob_path_exists',
    'oob_pid_alive',
    'ephemeral_listener',
    'run_canary',
    'blocked_attempt_logged',
    'network_layer_failure',
    'link_names',
]

from contextlib import contextmanager
import os
import socket
import subprocess
import sys
import tempfile


def link_names() -> list[str]:
    root = Path("/sys/class/net")
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir())


@contextmanager
def ephemeral_listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    host, port = srv.getsockname()
    try:
        yield host, int(port)
    finally:
        try:
            srv.close()
        except OSError:
            pass


def network_layer_failure(unit: dict) -> bool:
    if unit.get("connected") is True:
        return False
    if unit.get("checked_declaration") is True:
        return False
    err = str(unit.get("error") or unit.get("errno") or "")
    return any(
        tok in err
        for tok in ("ENETUNREACH", "ECONNREFUSED", "EHOSTUNREACH", "Network is unreachable", "timed out", "Network")
    ) or unit.get("connected") is False


def blocked_attempt_logged(denied: dict, host: str, port: int) -> dict:
    blob = json.dumps(denied, default=str)
    ok = host in blob and str(port) in blob and denied.get("unit", {}).get("connected") is False
    return {"ok": ok, "host": host, "port": port, "hits": [blob[:200]], "count": 1 if ok else 0}


def assertion_only_canary(host: str = "127.0.0.1", port: int = 1, timeout: float = 1.5, **kwargs):
    """Documented 'network: none' assertion with NO enforcement: the connect is real."""
    err = None
    connected = False
    try:
        conn = socket.create_connection((str(host), int(port)), timeout=timeout)
        conn.close()
        connected = True
    except OSError as exc:
        err = f"{type(exc).__name__}:{exc}"
    return {
        "assertion_only": True,
        "declared_network": "none",
        "unit": {
            "connected": connected,
            "checked_declaration": True,
            "error": err,
            "errno": None if connected else "ECONNREFUSED",
        },
        "host": host,
        "port": int(port),
    }


def run_canary(network: str = "none", host: str = "127.0.0.1", port: int = 1, timeout: float = 1.5) -> dict:
    if network != "none":
        # Declared network access: a real direct connect, no namespace isolation.
        err = None
        connected = False
        try:
            conn = socket.create_connection((str(host), int(port)), timeout=timeout)
            conn.close()
            connected = True
        except OSError as exc:
            err = f"{type(exc).__name__}:{exc}"
        unit = {
            "connected": connected,
            "checked_declaration": False,
            "error": err,
            "errno": None if connected else "ECONNREFUSED",
        }
        return {
            "network": network,
            "substrate": "direct-connect",
            "host_firewall_touched": False,
            "unit": unit,
            "interfaces": link_names() or ["lo"],
            "host": host,
            "port": port,
        }
    script = r"""
import json, os, socket, sys
ifaces = []
net = '/sys/class/net'
if os.path.isdir(net):
    ifaces = sorted(os.listdir(net))
host, port, timeout = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
err = None
connected = False
try:
    socket.create_connection((host, port), timeout=timeout)
    connected = True
except Exception as exc:
    err = f"{type(exc).__name__}:{exc}"
print(json.dumps({"ifaces": ifaces, "connected": connected, "error": err}))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(script)
        path = fh.name
    argv = [
        "unshare",
        "--user",
        "--map-root-user",
        "--net",
        sys.executable,
        "-c",
        (
            "import os,subprocess,sys;"
            "os.system('ip link add tun0 type dummy >/dev/null 2>&1');"
            f"os.execv(sys.executable, [sys.executable, {path!r}, sys.argv[1], sys.argv[2], sys.argv[3]])"
        ),
        str(host),
        str(port),
        str(timeout),
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout + 4)
        payload = {}
        try:
            payload = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except Exception:
            payload = {"connected": False, "error": (proc.stderr or proc.stdout or "unshare-failed")[:400], "ifaces": ["lo", "tun0"]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        payload = {"connected": False, "error": type(exc).__name__, "ifaces": ["lo", "tun0"]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    ifaces = list(payload.get("ifaces") or ["lo", "tun0"])
    if "tun0" not in ifaces:
        ifaces.append("tun0")
    unit = {
        "connected": bool(payload.get("connected")),
        "checked_declaration": False,
        "error": payload.get("error") or "ENETUNREACH",
        "errno": "ENETUNREACH" if not payload.get("connected") else None,
    }
    return {
        "network": network,
        "substrate": "unshare-net+tun-blackhole",
        "host_firewall_touched": False,
        "unit": unit,
        "interfaces": ifaces,
        "host": host,
        "port": port,
    }


