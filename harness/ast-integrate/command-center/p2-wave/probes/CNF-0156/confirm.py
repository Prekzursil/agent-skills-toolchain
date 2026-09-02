#!/usr/bin/env python3
"""Two mechanically independent local confirmer vendors for CNF-0156.

Live mcp__codex rails are not available on this worktree. The vendors are
local executable adapters named after the catalog vendor roles:

  * anthropic: whole-file byte oracle (hashlib.sha256 of read_bytes)
  * openai: stat + streaming/line-scan oracle (os.stat, chunked hash, per-line
    substring). A spanning-newline substring is therefore visible to anthropic
    and invisible to openai — a measured method difference, not a label leak.

CLI is prompt-by-file, blocking foreground. --background is refused. A 429/529
injection writes a quota document and must be classified NOT-CHECKED by the
dispatcher, never REFUTED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VENDORS = ("anthropic", "openai")


def _path(rel: str) -> Path:
    return REPO / str(rel).replace("\\", "/")


def _json_get(doc: Any, json_path: list) -> Any:
    cur = doc
    for key in json_path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def eval_anthropic(item: dict[str, Any]) -> dict[str, Any]:
    ev = item["evidence"]
    path = _path(ev["path"])
    kind = ev["kind"]
    asserted = ev.get("asserted")
    if kind == "file_exists":
        holds = path.is_file()
        obs = {"exists": holds, "method": "Path.is_file"}
    elif not path.is_file():
        holds = False
        obs = {"exists": False, "method": "read_bytes-missing"}
    else:
        data = path.read_bytes()
        if kind == "sha256_eq":
            got = hashlib.sha256(data).hexdigest()
            holds = got == asserted
            obs = {"got": got, "method": "hashlib.sha256(read_bytes)"}
        elif kind == "json_field_eq":
            doc = json.loads(data.decode("utf-8"))
            got = _json_get(doc, list(ev.get("json_path") or []))
            holds = got == asserted
            obs = {"got": got, "method": "json.loads(full-bytes)"}
        elif kind == "line_count_eq":
            got = len(data.decode("utf-8").splitlines())
            holds = got == asserted
            obs = {"got": got, "method": "decode.splitlines"}
        elif kind == "bytes_prefix_eq":
            needle = str(asserted).encode("ascii")
            got = data[: len(needle)]
            holds = got == needle
            obs = {"got": got.decode("ascii", "replace"), "method": "data[:n]"}
        elif kind == "substring_present":
            needle = str(asserted).encode("utf-8")
            holds = needle in data
            obs = {"holds": holds, "method": "bytes-in-read_bytes"}
        else:
            raise ValueError(f"unknown kind {kind}")
    verdict = "CONFIRMED" if holds else "REFUTED"
    return {
        "id": item["id"],
        "verdict": verdict,
        "observation": obs,
        "vendor": "anthropic",
    }


def eval_openai(item: dict[str, Any]) -> dict[str, Any]:
    ev = item["evidence"]
    path = _path(ev["path"])
    kind = ev["kind"]
    asserted = ev.get("asserted")
    if kind == "file_exists":
        try:
            os.stat(path)
            holds = True
        except OSError:
            holds = False
        obs = {"exists": holds, "method": "os.stat"}
    elif kind == "sha256_eq":
        if not path.is_file():
            holds = False
            obs = {"exists": False, "method": "chunked-sha256-missing"}
        else:
            h = hashlib.new("sha256")
            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(4096)
                    if not chunk:
                        break
                    h.update(chunk)
            got = h.hexdigest()
            holds = got == asserted
            obs = {"got": got, "method": "hashlib.new+4KiB-chunks"}
    elif kind == "json_field_eq":
        if not path.is_file():
            holds = False
            obs = {"exists": False}
        else:
            with path.open("r", encoding="utf-8") as fh:
                doc = json.load(fh)
            got = _json_get(doc, list(ev.get("json_path") or []))
            holds = got == asserted
            obs = {"got": got, "method": "json.load(stream)"}
    elif kind == "line_count_eq":
        if not path.is_file():
            holds = False
            obs = {"exists": False}
        else:
            with path.open("r", encoding="utf-8") as fh:
                got = sum(1 for _ in fh)
            holds = got == asserted
            obs = {"got": got, "method": "sum(1 for line in file)"}
    elif kind == "bytes_prefix_eq":
        if not path.is_file():
            holds = False
            obs = {"exists": False}
        else:
            needle = str(asserted).encode("ascii")
            with path.open("rb") as fh:
                got = fh.read(len(needle))
            holds = got == needle
            obs = {"got": got.decode("ascii", "replace"), "method": "read(n)"}
    elif kind == "substring_present":
        needle = str(asserted)
        if "\n" in needle or "\r" in needle:
            holds = False
            obs = {
                "holds": False,
                "method": "per-line-scan",
                "reason": "newline in needle cannot match a single line",
            }
        elif not path.is_file():
            holds = False
            obs = {"exists": False}
        else:
            holds = False
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if needle in line:
                        holds = True
                        break
            obs = {"holds": holds, "method": "per-line-scan"}
    else:
        raise ValueError(f"unknown kind {kind}")
    verdict = "CONFIRMED" if holds else "REFUTED"
    return {
        "id": item["id"],
        "verdict": verdict,
        "observation": obs,
        "vendor": "openai",
    }


EVALUATORS = {"anthropic": eval_anthropic, "openai": eval_openai}


def evaluate_payload(vendor: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    fn = EVALUATORS[vendor]
    return [fn(item) for item in payload["items"]]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--background" in argv:
        print("FAILED:confirm --background is banned", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", required=True, choices=list(VENDORS))
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--ignore-user-config", action="store_true")
    args = parser.parse_args(argv)

    inject = os.environ.get("CNF0156_INJECT", "").strip()
    out = Path(args.output_file)
    if inject == "severed":
        if out.exists():
            out.unlink()
        return 0
    if inject in {"429", "529"}:
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "error": f"{inject} Too Many Requests",
            "vendor": args.vendor,
            "verdicts": [],
        }
        out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0

    payload_path = Path(args.payload_file)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    raw = payload_path.read_bytes().replace(b"\r\n", b"\n")
    rows = evaluate_payload(args.vendor, payload)
    doc = {
        "vendor": args.vendor,
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_bytes": len(raw),
        "ignore_user_config": bool(args.ignore_user_config),
        "verdicts": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
