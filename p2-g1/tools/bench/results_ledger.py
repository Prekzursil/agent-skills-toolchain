#!/usr/bin/env python3
"""Append-only content-addressed results ledger (TST-0322)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEDGER_REL = "command-center/bench/results/ledger.jsonl"
CONCURRENT_WRITERS = 2
CONCURRENT_RECORDS_EACH = 50


def canonical(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def _digest_line(prev: str, line: str) -> str:
    return hashlib.sha256(f"{prev}|{line}".encode("utf-8")).hexdigest()


@dataclass
class VerifyReport:
    ok: bool
    findings: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    events: int = 0
    broken_tail: bool = False
    torn_bytes: int = 0
    wall_clock_s: float = 0.0

    def has_class(self, name: str) -> bool:
        return name in self.classes


def verify_ledger(path: Path, check_tip: bool = False) -> VerifyReport:
    t0 = time.perf_counter()
    path = Path(path)
    raw = path.read_bytes() if path.is_file() else b""
    torn = 0
    broken_tail = False
    if raw and not raw.endswith(b"\n"):
        broken_tail = True
        torn = len(raw) - raw.rfind(b"\n") - 1
    text = raw.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    findings: list[str] = []
    classes: list[str] = []
    prev = "genesis"
    events = 0
    seen = []
    for i, ln in enumerate(lines):
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            findings.append(f"unparseable:{i}")
            classes.append("torn-row")
            continue
        want = _digest_line(prev, canonical({k: v for k, v in ev.items() if k != "chain"}))
        chain = str(ev.get("chain") or ev.get("digest") or "")
        if chain and chain != want:
            findings.append(f"chain-break:{i}")
            classes.append("in-place-edit")
        prev = chain or want
        events += 1
        seen.append(ev)
    # detect deleted/inserted via sequence holes if seq present
    seqs = [e.get("seq") for e in seen if isinstance(e.get("seq"), int)]
    if seqs and seqs != list(range(seqs[0], seqs[0] + len(seqs))):
        if len(seqs) < (max(seqs) - min(seqs) + 1):
            classes.append("deleted-row")
            findings.append("deleted-row")
        if len(set(seqs)) != len(seqs):
            classes.append("inserted-row")
            findings.append("inserted-row")
    if broken_tail:
        classes.append("torn-tail")
        findings.append("torn-tail")
    ok = not findings
    return VerifyReport(
        ok=ok,
        findings=findings,
        classes=sorted(set(classes)),
        events=events,
        broken_tail=broken_tail,
        torn_bytes=torn,
        wall_clock_s=time.perf_counter() - t0,
    )


def repair_ledger(path: Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        cut = raw.rfind(b"\n")
        lost = raw[cut + 1 :] if cut >= 0 else raw
        kept = raw[: cut + 1] if cut >= 0 else b""
        path.write_bytes(kept)
        return {"lost": 1, "lost_bytes": len(lost), "ok": True}
    return {"lost": 0, "ok": True}


def append_event(path: Path, payload: dict[str, Any], prev: str = "genesis") -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    line_wo = canonical({k: v for k, v in body.items() if k != "chain"})
    digest = _digest_line(prev, line_wo)
    body["chain"] = digest
    line = canonical(body) + "\n"
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    fd = os.open(str(path), flags, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    return digest


def _seed_ledger(path: Path, n: int = 12) -> None:
    path = Path(path)
    if path.is_file() and path.stat().st_size > 0:
        return
    prev = "genesis"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    for i in range(n):
        prev = append_event(path, {"seq": i, "payload": {"value": i, "kind": "seed"}}, prev)


def worker(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?")
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--n", type=int, default=CONCURRENT_RECORDS_EACH)
    ap.add_argument("--writer-id", default="W")
    ap.add_argument("--ready-path", type=Path, required=True)
    ap.add_argument("--go-path", type=Path, required=True)
    ap.add_argument("--pad", type=int, default=0)
    args = ap.parse_args(argv)
    args.ready_path.write_text("ready\n", encoding="utf-8")
    while not args.go_path.is_file():
        time.sleep(0.005)
    prev = "genesis"
    if args.ledger.is_file() and args.ledger.stat().st_size:
        # best-effort: do not parse chain under contention; lock via exclusive create sidecar
        pass
    lock = args.ledger.with_suffix(args.ledger.suffix + ".lock")
    for i in range(int(args.n)):
        while True:
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                time.sleep(0.002)
            except PermissionError:
                # Windows surfaces a sharing violation on a racing lock
                # create/unlink as EACCES, not EEXIST. It is contention:
                # retry exactly like the exists case.
                time.sleep(0.005)
        try:
            # read last digest
            prev = "genesis"
            if args.ledger.is_file():
                lines = [ln for ln in args.ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
                if lines:
                    try:
                        prev = json.loads(lines[-1]).get("chain") or "genesis"
                    except json.JSONDecodeError:
                        prev = "genesis"
            pad = "x" * int(args.pad)
            append_event(
                args.ledger,
                {
                    "seq": None,
                    "i": i,
                    "payload": {"value": i, "pad": pad, "writer_id": args.writer_id},
                },
                prev,
            )
        finally:
            try:
                os.unlink(lock)
            except OSError:
                pass
    return 0


def main() -> int:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        return worker(sys.argv[2:])
    root = Path(__file__).resolve().parents[2]
    _seed_ledger(root / LEDGER_REL)
    print("ledger-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
