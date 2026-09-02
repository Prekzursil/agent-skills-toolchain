"""Quoting-safe command marshaller with file-based payload transport."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_QUOTE_ATTEMPTS = 2


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unsafe_reasons(payload: bytes) -> list[str]:
    reasons: list[str] = []
    if b"\x00" in payload:
        reasons.append("nul")
    if b"\n" in payload:
        reasons.append("newline")
    if b"'" in payload:
        reasons.append("apostrophe")
    if b"\nEOF\n" in payload or payload.endswith(b"\nEOF") or b"\nEOF" in payload:
        reasons.append("heredoc-eof")
    if b"$( " in payload or b"`" in payload or b"; touch " in payload or b"&&" in payload:
        reasons.append("injection")
    if b"rm -rf" in payload and b"mention" not in payload[:40]:
        # mention-only bodies still quote rm but are classified separately by corpus
        pass
    if any(ch < 32 and ch not in (9, 10, 13) for ch in payload):
        if "nul" not in reasons and b"\x00" in payload:
            pass
        elif b"\x00" not in payload:
            reasons.append("control-byte")
    return reasons


def corpus(canary: Path) -> list[dict[str, Any]]:
    touch = f"touch {canary.as_posix()}".encode("ascii")
    entries = [
        {"id": "plain-ascii", "payload": b"hello-world", "expect_unsafe": False, "shape": "plain"},
        {"id": "apostrophe", "payload": b"it's a test", "expect_unsafe": True, "shape": "apostrophe"},
        {"id": "heredoc-eof-line", "payload": b"alpha\nEOF\nomega", "expect_unsafe": True, "shape": "heredoc"},
        {"id": "injection-canary", "payload": b"ok'; " + touch + b"; echo 'x", "expect_unsafe": True, "shape": "injection"},
        {"id": "destructive-mention", "payload": b"the docs say never run `rm -rf /` on a host", "expect_unsafe": True, "shape": "mention"},
        {"id": "control-nul", "payload": b"pre\x00post", "expect_unsafe": True, "shape": "nul"},
        {"id": "double-quote", "payload": b'say "hi"', "expect_unsafe": False, "shape": "dquote"},
        {"id": "spaces", "payload": b"one two three", "expect_unsafe": False, "shape": "spaces"},
        {"id": "newlines", "payload": b"line1\nline2", "expect_unsafe": True, "shape": "newline"},
    ]
    return entries


@dataclass
class Envelope:
    mode: str
    path: Path | None = None
    reasons: list[str] = field(default_factory=list)
    argv: list[str] = field(default_factory=list)

    def payload_leaked_into_argv(self, payload: bytes) -> bool:
        blob = payload.decode("utf-8", errors="replace")
        return any(blob in arg for arg in self.argv)


@dataclass
class DeliveryResult:
    ok: bool
    round_trip: bool
    reason: str = ""
    quoting_attempts: int = 0
    switched_to_file: bool = False
    received: bytes = b""


def _python_echo_file(path: Path) -> list[str]:
    return [sys.executable, "-c", "import pathlib,sys; sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())", str(path)]


def deliver(payload: bytes, workdir: Path) -> tuple[Envelope, DeliveryResult]:
    workdir.mkdir(parents=True, exist_ok=True)
    reasons = unsafe_reasons(payload)
    if reasons:
        dest = workdir / (sha256_hex(payload)[:16] + ".payload")
        dest.write_bytes(payload)
        argv = _python_echo_file(dest)
        env = Envelope(mode="file", path=dest, reasons=reasons, argv=argv)
        proc = subprocess.run(argv, capture_output=True)
        received = proc.stdout
        ok = proc.returncode == 0 and received == payload
        return env, DeliveryResult(ok=ok, round_trip=ok, reason="" if ok else "file-echo", received=received)
    argv = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.argv[1].encode('utf-8'))", payload.decode("utf-8")]
    env = Envelope(mode="inline-argv", reasons=[], argv=argv)
    proc = subprocess.run(argv, capture_output=True)
    received = proc.stdout
    ok = proc.returncode == 0 and received == payload
    return env, DeliveryResult(ok=ok, round_trip=ok, reason="" if ok else "inline-echo", received=received)


def run_naive(transport: str, payload: bytes) -> tuple[int, bytes, str]:
    text = payload.decode("utf-8", errors="surrogateescape")
    shell = "bash"
    if transport.startswith("dash_"):
        shell = "dash"
        kind = transport[len("dash_"):]
    elif transport.startswith("bash_"):
        kind = transport[len("bash_"):]
    else:
        kind = transport
    if kind == "single_quote":
        cmd = f"printf '%s' '{text}'"
    elif kind == "double_quote":
        cmd = f'printf "%s" "{text}"'
    elif kind == "heredoc":
        cmd = f"cat <<EOF\n{text}\nEOF"
    else:
        return 2, b"", f"unknown-transport:{transport}"
    try:
        proc = subprocess.run([shell, "-c", cmd], capture_output=True, timeout=8)
    except FileNotFoundError:
        return 127, b"", f"missing-shell:{shell}"
    except subprocess.TimeoutExpired:
        return 124, b"", "timeout"
    return proc.returncode, proc.stdout, "ok" if proc.returncode == 0 else "naive-fail"


def try_naive_then_file(payload: bytes, workdir: Path, transport: str, meta: dict[str, Any] | None = None) -> DeliveryResult:
    attempts = 0
    for _ in range(MAX_QUOTE_ATTEMPTS):
        attempts += 1
        rc, out, reason = run_naive(transport, payload)
        if rc == 0 and out == payload:
            return DeliveryResult(ok=True, round_trip=True, quoting_attempts=attempts, switched_to_file=False, received=out)
    env, result = deliver(payload, workdir)
    result.quoting_attempts = attempts
    result.switched_to_file = env.mode == "file"
    return result


def run_matrix(workdir: Path, canary: Path) -> dict[str, Any]:
    entries = corpus(canary)
    cells: list[dict[str, Any]] = []
    transports = ["marshaller", "bash_single_quote", "bash_heredoc", "bash_double_quote"]
    by: dict[str, dict[str, int]] = {t: {"ok": 0, "fail": 0} for t in transports}
    for entry in entries:
        if canary.exists():
            canary.unlink()
        inv, res = deliver(entry["payload"], workdir)
        leaked = inv.payload_leaked_into_argv(entry["payload"]) if inv.mode == "file" else False
        cell = {
            "transport": "marshaller",
            "payload_id": entry["id"],
            "ok": res.ok and res.round_trip,
            "round_trip": res.round_trip,
            "leaked_into_argv": leaked,
            "canary_created": canary.is_file(),
            "mode": inv.mode,
        }
        cells.append(cell)
        by["marshaller"]["ok" if cell["ok"] else "fail"] += 1
        if canary.exists():
            canary.unlink()
        for tr in transports[1:]:
            if canary.exists():
                canary.unlink()
            rc, out, reason = run_naive(tr, entry["payload"])
            ok = rc == 0 and out == entry["payload"]
            cells.append(
                {
                    "transport": tr,
                    "payload_id": entry["id"],
                    "ok": ok,
                    "round_trip": ok,
                    "leaked_into_argv": False,
                    "canary_created": canary.is_file(),
                    "reason": reason,
                }
            )
            by[tr]["ok" if ok else "fail"] += 1
    return {
        "cells": cells,
        "payload_count": len(entries),
        "cell_count": len(cells),
        "by_transport": by,
        "destructive_mention_present": any(e["id"] == "destructive-mention" for e in entries),
    }
