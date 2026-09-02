#!/usr/bin/env python3
"""Marketplace registry `install`: fetch index, fail closed on DNS failure.

PASS contract for TST-0129:
  * DNS failure -> non-zero exit
  * error names the registry host AND the resolver
  * ZERO bytes written to the index directory (byte-for-byte unchanged)
  * no fallback to a cached / partial index reported as success

`--dns-fail-mode` exists only so the detector can go red on a planted mutant.
Production default is `abort`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dns_udp as DNS  # noqa: E402

HOST_DEFAULT = "registry.tst-0129.example"
ALLOWLIST = frozenset({HOST_DEFAULT, "localhost", "127.0.0.1"})
MARKER_CACHE = '{"cached":true,"marker":"TST-0129-PREEXISTING-INDEX-v1"}\n'
LIVE_INDEX = {
    "registry": "marketplace",
    "host": HOST_DEFAULT,
    "packages": [
        {
            "id": "pkg.demo",
            "version": "1.0.0",
            "channel": "stable",
            "permissions": ["net:registry"],
        }
    ],
}


def allowlisted(host: str) -> bool:
    return host.rstrip(".").lower() in {h.lower() for h in ALLOWLIST}


def atomic_write(index_dir: Path, payload: bytes) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    dest = index_dir / "index.json"
    fd, tmp = tempfile.mkstemp(prefix=".tst0129-index.", dir=str(index_dir.parent))
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, dest)
    return dest


def fetch_index(ip: str, port: int, timeout_s: float) -> bytes:
    url = f"http://{ip}:{int(port)}/index.json"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Host": HOST_DEFAULT},
        method="GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout_s) as resp:
        ctype = str(resp.headers.get("Content-Type") or "")
        body = resp.read()
    if "json" not in ctype.lower():
        raise ValueError(f"unexpected content-type {ctype!r}")
    json.loads(body.decode("utf-8"))
    return body


def dns_error(host: str, resolver: str, detail: str) -> str:
    return (
        f"ERROR: DNS resolution failed for host={host} resolver={resolver}: {detail}"
    )


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install")
    p.add_argument("--host", default=HOST_DEFAULT)
    p.add_argument("--resolver", required=True, help="resolver IPv4")
    p.add_argument("--resolver-port", type=int, required=True)
    p.add_argument("--http-port", type=int, default=0)
    p.add_argument("--index-dir", required=True)
    p.add_argument("--timeout", type=float, default=0.6)
    p.add_argument(
        "--dns-fail-mode",
        choices=("abort", "cache-success", "write-partial"),
        default="abort",
        help="abort is the fail-closed path; other values are detector mutants",
    )
    args = p.parse_args(argv)

    host = args.host.strip()
    resolver = f"{args.resolver}:{int(args.resolver_port)}"
    index_dir = Path(args.index_dir)

    if not allowlisted(host):
        print(
            f"ERROR: host={host} not on net-allowlist; resolver={resolver} unused",
            file=sys.stderr,
        )
        return 3

    addrs, err = DNS.query_a(
        host, args.resolver, int(args.resolver_port), float(args.timeout)
    )
    if err or not addrs:
        detail = err or "empty address list"
        if args.dns_fail_mode == "cache-success":
            # Mutant: pretends a cached index is a successful install.
            print(
                f"OK: using cached index for host={host} (dns failed: {detail})",
                file=sys.stdout,
            )
            return 0
        if args.dns_fail_mode == "write-partial":
            atomic_write(index_dir, b'{"partial":true,"truncated":true}\n')
            print(
                dns_error(host, resolver, detail) + " (mutant wrote partial index)",
                file=sys.stderr,
            )
            return 2
        print(dns_error(host, resolver, detail), file=sys.stderr)
        return 2

    if not args.http_port:
        print(
            f"ERROR: host={host} resolved via resolver={resolver} "
            f"to {addrs[0]} but --http-port is required",
            file=sys.stderr,
        )
        return 4

    try:
        body = fetch_index(addrs[0], int(args.http_port), float(args.timeout))
    except (urllib.error.URLError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(
            f"ERROR: registry fetch failed for host={host} resolved={addrs[0]} "
            f"resolver={resolver}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 5

    dest = atomic_write(index_dir, body)
    digest = hashlib.sha256(body).hexdigest()
    print(
        f"OK: wrote {dest.as_posix()} bytes={len(body)} sha256={digest} "
        f"host={host} resolved={addrs[0]} resolver={resolver}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
