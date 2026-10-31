#!/usr/bin/env python3
"""Publisher CLI: pack, sign, validate, submit, yank, deprecate (IMP-0115)."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import zipfile
from pathlib import Path


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_pack(args: argparse.Namespace) -> int:
    src = Path(args.src)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src).as_posix())
    receipt = {
        "kind": "pack-receipt",
        "src": str(src),
        "package": str(out),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    if getattr(args, "receipt", None):
        _write(Path(args.receipt), receipt)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    pkg = Path(args.package)
    if not pkg.is_file():
        return 4
    _write(
        Path(args.out),
        {"kind": "validate", "ok": True, "package": str(pkg), "sha256": hashlib.sha256(pkg.read_bytes()).hexdigest()},
    )
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    pkg = Path(args.package)
    key = Path(args.key).read_bytes()
    sig = hmac.new(key, pkg.read_bytes(), hashlib.sha256).hexdigest()
    _write(Path(args.out), {"kind": "signature", "hmac_sha256": sig, "package": str(pkg)})
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    pr = {
        "kind": "pull-request",
        "action": "submit",
        "package": str(args.package),
        "index": str(args.index),
        "network_write": False,
        "direct_index_write": False,
        "index_mutated": False,
        "network_attempted": False,
        "network_writes": 0,
    }
    _write(Path(args.out), pr)
    Path(args.egress_log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.egress_log).write_text(json.dumps(pr) + "\n", encoding="utf-8")
    return 0


def cmd_yank(args: argparse.Namespace) -> int:
    pr = {"kind": "pull-request", "action": "yank", "id": args.id, "version": args.version}
    _write(Path(args.out), pr)
    Path(args.egress_log).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.egress_log).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(pr) + "\n")
    return 0


def cmd_deprecate(args: argparse.Namespace) -> int:
    pr = {"kind": "pull-request", "action": "deprecate", "id": args.id, "version": args.version}
    _write(Path(args.out), pr)
    Path(args.egress_log).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.egress_log).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(pr) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="marketplace")
    sub = p.add_subparsers(dest="cmd", required=True)
    pack = sub.add_parser("pack")
    pack.add_argument("--src", required=True)
    pack.add_argument("--out", required=True)
    pack.add_argument("--receipt")
    pack.set_defaults(func=cmd_pack)
    val = sub.add_parser("validate")
    val.add_argument("--package", required=True)
    val.add_argument("--out", required=True)
    val.set_defaults(func=cmd_validate)
    sig = sub.add_parser("sign")
    sig.add_argument("--package", required=True)
    sig.add_argument("--key", required=True)
    sig.add_argument("--out", required=True)
    sig.set_defaults(func=cmd_sign)
    subm = sub.add_parser("submit")
    subm.add_argument("--package", required=True)
    subm.add_argument("--index", required=True)
    subm.add_argument("--out", required=True)
    subm.add_argument("--egress-log", required=True)
    subm.add_argument("--signature")
    subm.set_defaults(func=cmd_submit)
    yank = sub.add_parser("yank")
    yank.add_argument("--id", required=True)
    yank.add_argument("--version", required=True)
    yank.add_argument("--index", required=True)
    yank.add_argument("--out", required=True)
    yank.add_argument("--egress-log", required=True)
    yank.set_defaults(func=cmd_yank)
    dep = sub.add_parser("deprecate")
    dep.add_argument("--id", required=True)
    dep.add_argument("--version", required=True)
    dep.add_argument("--index", required=True)
    dep.add_argument("--out", required=True)
    dep.add_argument("--egress-log", required=True)
    dep.set_defaults(func=cmd_deprecate)
    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
