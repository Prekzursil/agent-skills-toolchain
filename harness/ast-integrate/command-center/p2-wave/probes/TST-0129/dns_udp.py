"""UDP DNS A-query client and a tiny answering / blackhole stub.

Used by the registry install client so resolution is a real packet exchange
against a named resolver address, not a mocked function return.
"""
from __future__ import annotations

import random
import socket
import struct
import threading
from typing import Callable


def encode_qname(name: str) -> bytes:
    out = bytearray()
    for label in name.rstrip(".").split("."):
        raw = label.encode("ascii")
        if not raw or len(raw) > 63:
            raise ValueError(f"bad DNS label {label!r}")
        out.append(len(raw))
        out.extend(raw)
    out.append(0)
    return bytes(out)


def skip_name(packet: bytes, offset: int) -> int:
    while True:
        if offset >= len(packet):
            raise ValueError("truncated DNS name")
        length = packet[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                raise ValueError("truncated compression pointer")
            return offset + 2
        offset += 1 + (length & 0x3F)


def build_query(host: str, qid: int | None = None) -> bytes:
    if qid is None:
        qid = random.randint(0, 65535)
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    return header + encode_qname(host) + struct.pack("!HH", 1, 1)


def parse_a_records(packet: bytes) -> list[str]:
    if len(packet) < 12:
        raise ValueError("DNS response shorter than header")
    _qid, flags, qdcount, ancount, _nscount, _arcount = struct.unpack(
        "!HHHHHH", packet[:12]
    )
    rcode = flags & 0xF
    if rcode != 0:
        raise ValueError(f"DNS rcode={rcode}")
    offset = 12
    for _ in range(qdcount):
        offset = skip_name(packet, offset)
        offset += 4
    addrs: list[str] = []
    for _ in range(ancount):
        offset = skip_name(packet, offset)
        if offset + 10 > len(packet):
            raise ValueError("truncated DNS answer")
        rtype, _rclass, _ttl, rdlength = struct.unpack(
            "!HHIH", packet[offset : offset + 10]
        )
        offset += 10
        rdata = packet[offset : offset + rdlength]
        offset += rdlength
        if rtype == 1 and rdlength == 4 and len(rdata) == 4:
            addrs.append(socket.inet_ntoa(rdata))
    return addrs


def query_a(
    host: str,
    resolver: str,
    resolver_port: int,
    timeout_s: float,
) -> tuple[list[str], str]:
    """Send one UDP A query. Returns (addrs, error_or_empty)."""
    payload = build_query(host)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout_s)
        sock.sendto(payload, (resolver, int(resolver_port)))
        data, _addr = sock.recvfrom(512)
    except TimeoutError:
        return [], f"timeout after {int(timeout_s * 1000)}ms"
    except OSError as exc:
        return [], f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()
    try:
        addrs = parse_a_records(data)
    except ValueError as exc:
        return [], str(exc)
    if not addrs:
        return [], "no A records in response"
    return addrs, ""


def _answer_packet(query: bytes, ipv4: str) -> bytes:
    if len(query) < 12:
        return b""
    qid = struct.unpack("!H", query[:2])[0]
    header = struct.pack("!HHHHHH", qid, 0x8180, 1, 1, 0, 0)
    question = query[12:]
    # Pointer to the QNAME at offset 12.
    answer = struct.pack("!HHHIH", 0xC00C, 1, 1, 30, 4)
    answer += socket.inet_aton(ipv4)
    return header + question + answer


class UdpResolver:
    """Answering stub or silent blackhole bound on 127.0.0.1."""

    def __init__(self, mode: str, host: str, ipv4: str = "127.0.0.1") -> None:
        if mode not in {"answer", "blackhole"}:
            raise ValueError(mode)
        self.mode = mode
        self.host = host.rstrip(".").lower()
        self.ipv4 = ipv4
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 0))
        self.ip, self.port = self._sock.getsockname()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if mode == "answer":
            self._sock.settimeout(0.2)
            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()
        else:
            # Bound but never read: queries time out. That is a named blackhole.
            self._sock.setblocking(False)

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    def _serve(self) -> None:
        wanted = encode_qname(self.host)
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(512)
            except TimeoutError:
                continue
            except OSError:
                break
            if len(data) < 12:
                continue
            qname = data[12 : 12 + len(wanted)]
            if qname.lower() != wanted.lower():
                qid = struct.unpack("!H", data[:2])[0]
                nx = struct.pack("!HHHHHH", qid, 0x8183, 1, 0, 0, 0)
                try:
                    self._sock.sendto(nx + data[12:], addr)
                except OSError:
                    pass
                continue
            reply = _answer_packet(data, self.ipv4)
            if reply:
                try:
                    self._sock.sendto(reply, addr)
                except OSError:
                    pass

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def __enter__(self) -> "UdpResolver":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def with_resolver(mode: str, host: str, fn: Callable[["UdpResolver"], object]):
    stub = UdpResolver(mode, host)
    try:
        return fn(stub)
    finally:
        stub.close()
