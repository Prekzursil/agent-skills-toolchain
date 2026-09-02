"""Workspace isolation primitives: session-scoped writes and network:none enforcement.

Two independent surfaces live here because both answer the same question --
is a declared workspace boundary *enforced* by the substrate, or merely
asserted in a document?

Session broker (TST-0227)
    :class:`SessionBroker` registers per-session roots (worktree, artifact,
    runtime) and mediates writes.  Containment is physical: the destination is
    resolved through every existing symlink and ``..`` segment before it is
    compared with the resolved roots, so relative traversal and symlink hops
    into another session's tree are refused with :class:`SessionDenied`
    carrying ``Codes.CROSS_SESSION_WRITE`` and an :class:`Alert` that names
    both session ids.  A refused write never touches the disk.
    :meth:`SessionBroker.start_heartbeat` spawns a real child process that
    keeps a heartbeat file fresh under the session's runtime dir (outside the
    hashed worktree), so a "live victim session" is a live pid under ``/proc``.

    The out-of-band checks :func:`independent_tree_hash`, :func:`oob_path_exists`
    and :func:`oob_pid_alive` deliberately bypass the broker so a probe can
    verify its verdicts against the filesystem and the kernel directly.

Network canary (TST-0225)
    :func:`run_canary` runs a connect attempt either on the host stack
    (``network`` != ``"none"``) or inside a throwaway user+network namespace
    whose only uplink is a TUN device owned by this process
    (``unshare --user --map-root-user --net``).  A sidecar thread reads every
    frame the namespace emits on that TUN: a TCP SYN is logged out-of-band and
    answered with an injected RST, so the unit's ``socket.connect`` fails at
    the network layer (``ECONNREFUSED``) without any in-process declaration
    check and without touching the host firewall.  :func:`assertion_only_canary`
    is the negative control -- the declaration exists only as an environment
    flag, and the connect goes through.

    Run as a script this module is the in-namespace unit
    (``workspace.py netns-unit HOST PORT TIMEOUT``) and the env-flag mutant
    (``workspace.py env-unit HOST PORT TIMEOUT``); both print one JSON object.
"""
from __future__ import annotations

import ctypes
import errno as _errno
import fcntl
import hashlib
import json
import os
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "Alert",
    "Codes",
    "HeartbeatRecord",
    "NETWORK_LAYER_ERRNOS",
    "SUBSTRATE_HOST",
    "SUBSTRATE_NONE",
    "Session",
    "SessionBroker",
    "SessionDenied",
    "TUN_ADDR",
    "assertion_only_canary",
    "blocked_attempt_logged",
    "connect_canary",
    "ephemeral_listener",
    "independent_tree_hash",
    "link_names",
    "network_layer_failure",
    "oob_path_exists",
    "oob_pid_alive",
    "primary_host_address",
    "run_canary",
]

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Session broker
# ---------------------------------------------------------------------------


class Codes:
    """Denial codes raised by :class:`SessionBroker`."""

    CROSS_SESSION_WRITE = "CROSS_SESSION_WRITE"
    OUTSIDE_SESSION_ROOTS = "OUTSIDE_SESSION_ROOTS"
    UNKNOWN_SESSION = "UNKNOWN_SESSION"


@dataclass(frozen=True)
class Alert:
    """What the broker reports when it refuses a write."""

    actor: str
    victim: str | None
    code: str
    path: str

    def names_both(self) -> bool:
        return bool(self.actor) and bool(self.victim) and self.actor != self.victim

    def as_dict(self) -> dict[str, Any]:
        return {"actor": self.actor, "victim": self.victim, "code": self.code, "path": self.path}


class SessionDenied(PermissionError):
    """A mediated write was refused before any byte reached the disk."""

    def __init__(self, code: str, actor: str, victim: str | None, path: Path) -> None:
        super().__init__(f"{code}: session {actor!r} may not write {str(path)!r} (owner={victim!r})")
        self.code = code
        self.actor_session_id = actor
        self.victim_session_id = victim
        self.path = Path(path)
        self.alert = Alert(actor=actor, victim=victim, code=code, path=str(path))


@dataclass
class Session:
    session_id: str
    worktree_root: Path
    artifact_root: Path
    runtime_dir: Path

    @property
    def heartbeat_path(self) -> Path:
        return self.runtime_dir / "heartbeat.json"

    def roots(self) -> tuple[Path, Path, Path]:
        return (self.worktree_root, self.artifact_root, self.runtime_dir)


@dataclass
class HeartbeatRecord:
    """Handle on a live heartbeat child; ``pid`` is a real kernel pid."""

    session_id: str
    pid: int
    path: Path
    interval_sec: float
    started_monotonic: float
    process: subprocess.Popen[bytes] = field(repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "path": str(self.path),
            "interval_sec": self.interval_sec,
        }


_HEARTBEAT_CHILD = r"""
import json, os, sys, time
path, sid, interval = sys.argv[1], sys.argv[2], float(sys.argv[3])
seq = 0
while True:
    seq += 1
    rec = {"session_id": sid, "pid": os.getpid(), "seq": seq,
           "monotonic": time.monotonic(), "wall": time.time()}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    os.replace(tmp, path)
    time.sleep(interval)
"""


def _physical(path: Path | str) -> Path:
    """Resolve symlinks in every existing ancestor and collapse ``..`` afterwards."""
    return Path(os.path.realpath(os.fspath(path)))


def _contains(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


class SessionBroker:
    """Mediates writes so one session can never land bytes in another's tree."""

    def __init__(self, *, heartbeat_interval_sec: float = 0.1) -> None:
        self.sessions: dict[str, Session] = {}
        self._resolved_roots: dict[str, tuple[Path, ...]] = {}
        self._heartbeats: dict[str, HeartbeatRecord] = {}
        self.heartbeat_interval_sec = float(heartbeat_interval_sec)
        self.alerts: list[Alert] = []

    # -- registration -------------------------------------------------------

    def register(
        self,
        session_id: str,
        *,
        worktree_root: Path | str,
        artifact_root: Path | str,
        runtime_dir: Path | str,
    ) -> Session:
        if session_id in self.sessions:
            raise ValueError(f"session {session_id!r} is already registered")
        sess = Session(
            session_id,
            Path(worktree_root).absolute(),
            Path(artifact_root).absolute(),
            Path(runtime_dir).absolute(),
        )
        for root in sess.roots():
            root.mkdir(parents=True, exist_ok=True)
        resolved = tuple(_physical(root) for root in sess.roots())
        for other_id, other_roots in self._resolved_roots.items():
            for mine in resolved:
                for theirs in other_roots:
                    if _contains(theirs, mine) or _contains(mine, theirs):
                        raise ValueError(
                            f"session {session_id!r} root {mine} overlaps session {other_id!r} root {theirs}"
                        )
        self.sessions[session_id] = sess
        self._resolved_roots[session_id] = resolved
        return sess

    def owner_of(self, path: Path | str) -> str | None:
        """Session id whose (resolved) roots contain the physical ``path``."""
        target = _physical(path)
        for session_id, roots in self._resolved_roots.items():
            if any(_contains(root, target) for root in roots):
                return session_id
        return None

    # -- mediated writes ----------------------------------------------------

    def write_file(self, actor_id: str, path: Path | str, data: bytes) -> Path:
        target = _physical(path)
        if actor_id not in self.sessions:
            raise self._deny(Codes.UNKNOWN_SESSION, actor_id, None, target)
        owner = self.owner_of(target)
        if owner is None:
            raise self._deny(Codes.OUTSIDE_SESSION_ROOTS, actor_id, None, target)
        if owner != actor_id:
            raise self._deny(Codes.CROSS_SESSION_WRITE, actor_id, owner, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(data))
        return target

    def _deny(self, code: str, actor: str, victim: str | None, target: Path) -> SessionDenied:
        exc = SessionDenied(code, actor, victim, target)
        self.alerts.append(exc.alert)
        return exc

    # -- evidence -----------------------------------------------------------

    def tree_hash(self, session_id: str) -> dict[str, str]:
        sess = self.sessions[session_id]
        return {
            "worktree": independent_tree_hash(sess.worktree_root),
            "artifact": independent_tree_hash(sess.artifact_root),
        }

    # -- liveness -----------------------------------------------------------

    def start_heartbeat(self, session_id: str, *, ready_timeout_sec: float = 10.0) -> HeartbeatRecord:
        """Spawn a child that keeps ``heartbeat.json`` fresh under the runtime dir."""
        sess = self.sessions[session_id]
        if session_id in self._heartbeats and self.session_is_alive(session_id):
            return self._heartbeats[session_id]
        sess.runtime_dir.mkdir(parents=True, exist_ok=True)
        interval = self.heartbeat_interval_sec
        proc = subprocess.Popen(
            [
                sys.executable,
                "-S",
                "-B",
                "-c",
                _HEARTBEAT_CHILD,
                str(sess.heartbeat_path),
                session_id,
                repr(interval),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        rec = HeartbeatRecord(
            session_id=session_id,
            pid=proc.pid,
            path=sess.heartbeat_path,
            interval_sec=interval,
            started_monotonic=time.monotonic(),
            process=proc,
        )
        deadline = time.monotonic() + ready_timeout_sec
        while not sess.heartbeat_path.exists():
            if proc.poll() is not None:
                raise RuntimeError(f"heartbeat child for {session_id!r} exited rc={proc.returncode} before first beat")
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=5)
                raise TimeoutError(f"heartbeat child for {session_id!r} produced no beat in {ready_timeout_sec}s")
            time.sleep(0.01)
        self._heartbeats[session_id] = rec
        return rec

    def session_is_alive(self, session_id: str) -> bool:
        """Live pid *and* a fresh heartbeat file; a registered-but-idle session is not alive."""
        rec = self._heartbeats.get(session_id)
        if rec is None or rec.process.poll() is not None:
            return False
        if not oob_pid_alive(rec.pid):
            return False
        try:
            beat = json.loads(rec.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        stale_after = max(2.0, 20 * rec.interval_sec)
        return (time.monotonic() - float(beat.get("monotonic", 0.0))) < stale_after

    def stop_heartbeat(self, session_id: str, *, timeout_sec: float = 5.0) -> int | None:
        rec = self._heartbeats.pop(session_id, None)
        if rec is None:
            return None
        proc = rec.process
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=timeout_sec)
        return proc.returncode

    def stop_all(self) -> dict[str, int | None]:
        return {sid: self.stop_heartbeat(sid) for sid in list(self._heartbeats)}

    def __enter__(self) -> SessionBroker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop_all()


def independent_tree_hash(root: Path | str) -> str:
    """sha256 over (relative path, content) of every entry under ``root``, no broker involved.

    Symlinks contribute their link target and are never followed, so a link
    planted inside one tree cannot pull another tree's bytes into the digest.
    A missing or empty root hashes to the digest of nothing.
    """
    root = Path(root)
    digest = hashlib.sha256()
    if root.is_file() or root.is_symlink():
        entries = [(root.name, root)]
    else:
        entries = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames.sort()
            for name in dirnames + filenames:
                full = Path(dirpath) / name
                if full.is_dir() and not full.is_symlink():
                    continue
                entries.append((full.relative_to(root).as_posix(), full))
        entries.sort()
    for rel, full in entries:
        digest.update(rel.encode("utf-8") + b"\0")
        if full.is_symlink():
            digest.update(b"L" + os.readlink(full).encode("utf-8", "surrogateescape") + b"\0")
            continue
        try:
            data = full.read_bytes()
        except OSError:
            digest.update(b"?\0")
            continue
        digest.update(b"F" + struct.pack("!Q", len(data)) + data)
    return digest.hexdigest()


def oob_path_exists(path: Path | str) -> bool:
    """Filesystem truth about ``path`` (a dangling symlink counts), no broker involved."""
    return os.path.lexists(os.fspath(path))


def oob_pid_alive(pid: Any) -> bool:
    """Kernel truth about ``pid``: present under ``/proc`` and not a zombie."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    stat = Path("/proc") / str(pid) / "stat"
    if Path("/proc/self").exists():
        try:
            text = stat.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        state = text.rsplit(")", 1)[-1].split()[0] if ")" in text else ""
        return state not in {"Z", "X", "x"}
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------------------
# Network canary
# ---------------------------------------------------------------------------

SUBSTRATE_NONE = "unshare-net+tun-blackhole"
SUBSTRATE_HOST = "host"
TUN_NAME = "tun0"
TUN_ADDR = "10.254.0.2"
TUN_NETMASK = "255.255.255.0"

NETWORK_LAYER_ERRNOS = frozenset(
    {
        _errno.ECONNREFUSED,
        _errno.ECONNRESET,
        _errno.ENETUNREACH,
        _errno.ENETDOWN,
        _errno.EHOSTUNREACH,
        _errno.EHOSTDOWN,
        _errno.ETIMEDOUT,
    }
)
_NETWORK_LAYER_ERRNO_NAMES = frozenset(_errno.errorcode[e] for e in NETWORK_LAYER_ERRNOS)

# <linux/if_tun.h>, <linux/sockios.h>, <net/if.h>, <linux/route.h>
_TUNSETIFF = 0x400454CA
_IFF_TUN = 0x0001
_IFF_NO_PI = 0x1000
_SIOCGIFFLAGS = 0x8913
_SIOCSIFFLAGS = 0x8914
_SIOCGIFADDR = 0x8915
_SIOCSIFADDR = 0x8916
_SIOCSIFNETMASK = 0x891C
_SIOCADDRT = 0x890B
_IFF_UP = 0x0001
_IFF_RUNNING = 0x0040
_RTF_UP = 0x0001
_TCP_SYN = 0x02
_TCP_RST = 0x04
_TCP_ACK = 0x10


class _SockAddr(ctypes.Structure):
    _fields_ = [("sa_family", ctypes.c_ushort), ("sa_data", ctypes.c_char * 14)]


class _RtEntry(ctypes.Structure):
    """``struct rtentry`` for the legacy ``SIOCADDRT`` ioctl (IPv4 only)."""

    _fields_ = [
        ("rt_pad1", ctypes.c_ulong),
        ("rt_dst", _SockAddr),
        ("rt_gateway", _SockAddr),
        ("rt_genmask", _SockAddr),
        ("rt_flags", ctypes.c_ushort),
        ("rt_pad2", ctypes.c_short),
        ("rt_pad3", ctypes.c_ulong),
        ("rt_pad4", ctypes.c_void_p),
        ("rt_metric", ctypes.c_short),
        ("rt_dev", ctypes.c_char_p),
        ("rt_mtu", ctypes.c_ulong),
        ("rt_window", ctypes.c_ulong),
        ("rt_irtt", ctypes.c_ushort),
    ]


def _sockaddr_in(ip: str) -> _SockAddr:
    sa = _SockAddr()
    sa.sa_family = socket.AF_INET
    sa.sa_data = struct.pack("!H4s8x", 0, socket.inet_aton(ip))
    return sa


def _ifreq_addr(name: str, ip: str) -> bytes:
    return struct.pack("16sH2s4s8s", name.encode(), socket.AF_INET, b"\0\0", socket.inet_aton(ip), b"\0" * 8)


def link_names() -> list[str]:
    """Interface names of the *calling process's* network namespace.

    ``/proc/self/net/dev`` is per-namespace; ``/sys/class/net`` is not (it shows
    the namespace sysfs was mounted in), so sysfs is only a fallback.
    """
    try:
        lines = Path("/proc/self/net/dev").read_text(encoding="utf-8").splitlines()[2:]
        names = [line.split(":", 1)[0].strip() for line in lines if ":" in line]
        if names:
            return sorted(names)
    except OSError:
        pass
    root = Path("/sys/class/net")
    if root.is_dir():
        return sorted(p.name for p in root.iterdir())
    return []


def _interface_ipv4(name: str) -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            res = fcntl.ioctl(sock.fileno(), _SIOCGIFADDR, struct.pack("16sH14s", name.encode(), socket.AF_INET, b"\0" * 14))
        except OSError:
            return None
    return socket.inet_ntoa(res[20:24])


def primary_host_address() -> str:
    """The host's primary non-loopback IPv4 address (loopback only if there is none).

    A network:none unit can only be shown to *egress* toward an address that is
    not local inside its namespace, so the canary listener binds here.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("192.0.2.1", 9))  # TEST-NET-1; UDP connect sends nothing
            addr = sock.getsockname()[0]
            if addr and not addr.startswith("127."):
                return addr
        except OSError:
            pass
    for name in link_names():
        if name == "lo":
            continue
        addr = _interface_ipv4(name)
        if addr and not addr.startswith("127."):
            return addr
    return "127.0.0.1"


@contextmanager
def ephemeral_listener(host: str | None = None, *, backlog: int = 8) -> Iterator[tuple[str, int]]:
    """A real TCP listener on an ephemeral port; the kernel completes handshakes into the backlog."""
    bind_host = host or primary_host_address()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((bind_host, 0))
        srv.listen(backlog)
        bound_host, port = srv.getsockname()[:2]
        yield bound_host, int(port)
    finally:
        try:
            srv.close()
        except OSError:
            pass


def connect_canary(host: str, port: int, timeout: float = 1.5) -> dict[str, Any]:
    """The unit: one TCP connect, no declaration consulted, kernel errno reported verbatim."""
    unit: dict[str, Any] = {
        "host": host,
        "port": int(port),
        "connected": False,
        "checked_declaration": False,
        "errno": None,
        "error": None,
        "result": None,
        "peer": None,
    }
    started = time.monotonic()
    try:
        conn = socket.create_connection((host, int(port)), timeout=timeout)
    except OSError as exc:
        unit["errno"] = getattr(exc, "errno", None)
        unit["error"] = str(exc)
        unit["result"] = type(exc).__name__
    else:
        try:
            peer = conn.getpeername()
            unit["peer"] = [peer[0], int(peer[1])]
        except OSError:
            pass
        conn.close()
        unit["connected"] = True
        unit["errno"] = 0
        unit["result"] = "connected"
    unit["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return unit


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def _rst_for_syn(pkt: bytes) -> bytes:
    """Build the IPv4/TCP RST|ACK that refuses the SYN in ``pkt``."""
    ihl = (pkt[0] & 0x0F) * 4
    src, dst = pkt[12:16], pkt[16:20]
    sport, dport, seq = struct.unpack("!HHI", pkt[ihl : ihl + 8])
    ack = (seq + 1) & 0xFFFFFFFF
    tcp = struct.pack("!HHIIBBHHH", dport, sport, 0, ack, 5 << 4, _TCP_RST | _TCP_ACK, 0, 0, 0)
    pseudo = dst + src + struct.pack("!BBH", 0, socket.IPPROTO_TCP, len(tcp))
    tcp = tcp[:16] + struct.pack("!H", _checksum(pseudo + tcp)) + tcp[18:]
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0x4000, 64, socket.IPPROTO_TCP, 0, dst, src)
    ip = ip[:10] + struct.pack("!H", _checksum(ip)) + ip[12:]
    return ip + tcp


def _describe_frame(pkt: bytes) -> dict[str, Any]:
    entry: dict[str, Any] = {"raw_len": len(pkt), "hex_head": pkt[:48].hex()}
    if not pkt or pkt[0] >> 4 != 4:
        entry.update({"action": "DROP", "non_ipv4": True})
        return entry
    ihl = (pkt[0] & 0x0F) * 4
    entry.update(
        {
            "ihl": ihl,
            "len": struct.unpack("!H", pkt[2:4])[0],
            "proto": pkt[9],
            "src": socket.inet_ntoa(pkt[12:16]),
            "dst": socket.inet_ntoa(pkt[16:20]),
        }
    )
    if pkt[9] == socket.IPPROTO_TCP and len(pkt) >= ihl + 20:
        sport, dport, seq = struct.unpack("!HHI", pkt[ihl : ihl + 8])
        flags = pkt[ihl + 13]
        entry.update({"sport": sport, "dport": dport, "seq": seq, "flags": flags, "doff": (pkt[ihl + 12] >> 4) * 4})
    return entry


class _TunBlackhole:
    """The namespace's only uplink: a TUN device this process reads and answers itself."""

    def __init__(self, name: str = TUN_NAME, addr: str = TUN_ADDR, netmask: str = TUN_NETMASK) -> None:
        self.name = name
        self.addr = addr
        self.netmask = netmask
        self.fd = -1
        self.log: list[dict[str, Any]] = []
        self.setup: dict[str, Any] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def open(self) -> None:
        self.fd = os.open("/dev/net/tun", os.O_RDWR)
        fcntl.ioctl(self.fd, _TUNSETIFF, struct.pack("16sH14s", self.name.encode(), _IFF_TUN | _IFF_NO_PI, b"\0" * 14))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ctl:
            fcntl.ioctl(ctl.fileno(), _SIOCSIFADDR, _ifreq_addr(self.name, self.addr))
            fcntl.ioctl(ctl.fileno(), _SIOCSIFNETMASK, _ifreq_addr(self.name, self.netmask))
            self._bring_up(ctl, "lo")
            self._bring_up(ctl, self.name)
            route = _RtEntry()
            route.rt_dst = _sockaddr_in("0.0.0.0")
            route.rt_genmask = _sockaddr_in("0.0.0.0")
            route.rt_gateway = _sockaddr_in("0.0.0.0")
            route.rt_flags = _RTF_UP
            route.rt_dev = self.name.encode()
            fcntl.ioctl(ctl.fileno(), _SIOCADDRT, bytes(route))
        self.setup = {"device": self.name, "addr": self.addr, "netmask": self.netmask, "default_route": f"dev {self.name}"}

    @staticmethod
    def _bring_up(ctl: socket.socket, name: str) -> None:
        req = struct.pack("16sH14s", name.encode(), 0, b"\0" * 14)
        flags = struct.unpack("16sH14s", fcntl.ioctl(ctl.fileno(), _SIOCGIFFLAGS, req))[1]
        fcntl.ioctl(ctl.fileno(), _SIOCSIFFLAGS, struct.pack("16sH14s", name.encode(), flags | _IFF_UP | _IFF_RUNNING, b"\0" * 14))

    def start_sidecar(self) -> None:
        self._thread = threading.Thread(target=self._pump, name="tun-sidecar", daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        while not self._stop.is_set():
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if not ready:
                continue
            try:
                pkt = os.read(self.fd, 65535)
            except OSError as exc:
                self.log.append({"action": "READ-ERROR", "error": str(exc)})
                break
            entry = _describe_frame(pkt)
            if entry.get("proto") == socket.IPPROTO_TCP and "flags" in entry:
                flags = entry["flags"]
                if flags & _TCP_SYN and not flags & _TCP_ACK:
                    os.write(self.fd, _rst_for_syn(pkt))
                    entry["action"] = "RST"
                else:
                    entry["action"] = "DROP"
            else:
                entry.setdefault("action", "DROP")
            self.log.append(entry)

    def close(self, *, settle_sec: float = 0.1) -> None:
        time.sleep(settle_sec)
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _netns_unit(host: str, port: int, timeout: float) -> dict[str, Any]:
    """Runs inside the fresh namespace: build the blackhole, then let the unit connect."""
    tun = _TunBlackhole()
    tun.open()
    tun.start_sidecar()
    try:
        unit = connect_canary(host, port, timeout)
        # The TUN is not persistent: it vanishes with its fd, so list links now.
        interfaces = link_names()
    finally:
        tun.close()
    return {
        "substrate": SUBSTRATE_NONE,
        "tun_addr": tun.addr,
        "setup": tun.setup,
        "interfaces": interfaces,
        "unit": unit,
        "oob_log": tun.log,
    }


def _env_unit(host: str, port: int, timeout: float) -> dict[str, Any]:
    """The assertion-only mutant: reads the declaration, documents it, connects anyway."""
    declared = os.environ.get("NETWORK")
    unit = connect_canary(host, port, timeout)
    unit["checked_declaration"] = True
    unit["declaration"] = declared
    unit["enforced"] = False
    return {"substrate": SUBSTRATE_HOST, "interfaces": link_names(), "unit": unit, "oob_log": []}


def _run_child(argv: list[str], *, timeout: float, env: dict[str, str] | None = None) -> tuple[dict[str, Any] | None, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return None, f"rc={proc.returncode}: {(proc.stderr or proc.stdout or '').strip()[-600:]}"
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line), ""
            except ValueError:
                break
    return None, f"no JSON on stdout: {(proc.stdout or '')[-300:]!r} stderr={(proc.stderr or '')[-300:]!r}"


def _substrate_error(network: str, substrate: str, host: str, port: int, reason: str) -> dict[str, Any]:
    return {
        "network": network,
        "substrate": substrate,
        "substrate_error": reason,
        "host_firewall_touched": False,
        "host": host,
        "port": int(port),
        "interfaces": [],
        "oob_log": [],
        "unit": {
            "host": host,
            "port": int(port),
            "connected": None,
            "checked_declaration": False,
            "errno": None,
            "error": f"substrate-unavailable: {reason}",
            "result": "SubstrateError",
        },
    }


def run_canary(network: str = "none", host: str = "127.0.0.1", port: int = 1, timeout: float = 1.5) -> dict[str, Any]:
    """Connect to ``host:port`` under the declared ``network`` policy and report what the kernel did.

    ``network != "none"`` connects on the host stack.  ``"none"`` re-executes
    this module inside ``unshare --user --map-root-user --net`` where the only
    uplink is a TUN blackhole; the returned ``oob_log`` is the sidecar's
    frame-by-frame record.  When the namespace cannot be built the result says
    so (``substrate_error``, ``unit.connected is None``) instead of guessing.
    """
    host = str(host)
    port = int(port)
    if network != "none":
        return {
            "network": network,
            "substrate": SUBSTRATE_HOST,
            "host_firewall_touched": False,
            "host": host,
            "port": port,
            "interfaces": link_names(),
            "oob_log": [],
            "unit": connect_canary(host, port, timeout),
        }
    unshare = shutil.which("unshare")
    if unshare is None:
        return _substrate_error(network, SUBSTRATE_NONE, host, port, "unshare(1) not found")
    if not Path("/dev/net/tun").exists():
        return _substrate_error(network, SUBSTRATE_NONE, host, port, "/dev/net/tun absent")
    argv = [
        unshare,
        "--user",
        "--map-root-user",
        "--net",
        sys.executable,
        "-S",
        "-B",
        str(Path(__file__).resolve()),
        "netns-unit",
        host,
        str(port),
        repr(float(timeout)),
    ]
    payload, reason = _run_child(argv, timeout=float(timeout) + 15.0)
    if payload is None:
        return _substrate_error(network, SUBSTRATE_NONE, host, port, reason)
    return {
        "network": network,
        "substrate": SUBSTRATE_NONE,
        "host_firewall_touched": False,
        "host": host,
        "port": port,
        "tun_addr": payload.get("tun_addr"),
        "setup": payload.get("setup"),
        "interfaces": list(payload.get("interfaces") or []),
        "oob_log": list(payload.get("oob_log") or []),
        "unit": dict(payload.get("unit") or {}),
    }


def assertion_only_canary(host: str, port: int, timeout: float = 1.5) -> dict[str, Any]:
    """Negative control: ``NETWORK=none`` exists only as an env flag, so the connect must succeed."""
    host = str(host)
    port = int(port)
    argv = [sys.executable, "-S", "-B", str(Path(__file__).resolve()), "env-unit", host, str(port), repr(float(timeout))]
    payload, reason = _run_child(argv, timeout=float(timeout) + 15.0, env={**os.environ, "NETWORK": "none"})
    if payload is None:
        out = _substrate_error("none", SUBSTRATE_HOST, host, port, reason)
    else:
        out = {
            "network": "none",
            "substrate": SUBSTRATE_HOST,
            "host_firewall_touched": False,
            "host": host,
            "port": port,
            "interfaces": list(payload.get("interfaces") or []),
            "oob_log": [],
            "unit": dict(payload.get("unit") or {}),
        }
    out.update({"assertion_only": True, "declared_network": "none", "enforcement": "env-flag-only"})
    return out


def network_layer_failure(unit: dict[str, Any]) -> bool:
    """True only when the connect itself failed with a network-layer errno and no declaration was consulted."""
    if not isinstance(unit, dict) or unit.get("connected") is not False:
        return False
    if unit.get("checked_declaration") is not False:
        return False
    code = unit.get("errno")
    if isinstance(code, bool):
        return False
    if isinstance(code, int) and code in NETWORK_LAYER_ERRNOS:
        return True
    if isinstance(code, str) and code in _NETWORK_LAYER_ERRNO_NAMES:
        return True
    return str(unit.get("result") or "") in {"TimeoutError", "timeout"}


def blocked_attempt_logged(denied: dict[str, Any], host: str, port: int) -> dict[str, Any]:
    """Did the TUN sidecar (signal b) see a TCP SYN to ``host:port`` from the unit (signal a)?"""
    hits = []
    for entry in denied.get("oob_log") or []:
        if not isinstance(entry, dict) or entry.get("proto") != socket.IPPROTO_TCP:
            continue
        if entry.get("dst") != str(host) or int(entry.get("dport") or -1) != int(port):
            continue
        if not (int(entry.get("flags") or 0) & _TCP_SYN):
            continue
        hits.append(entry)
    return {"ok": bool(hits), "count": len(hits), "hits": hits, "source": "tun-sidecar", "host": str(host), "port": int(port)}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 4 or args[0] not in {"netns-unit", "env-unit"}:
        print("usage: workspace.py (netns-unit|env-unit) HOST PORT TIMEOUT", file=sys.stderr)
        return 2
    mode, host, port, timeout = args[0], args[1], int(args[2]), float(args[3])
    payload = _netns_unit(host, port, timeout) if mode == "netns-unit" else _env_unit(host, port, timeout)
    print(json.dumps(payload, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
