#!/usr/bin/env python3
"""Probe 2: content-gate parity (local blobread vs CI blob) + both-states trap.

Naive worktree hashing must go RED against the blob digest (the trap).
blobread.content_bytes must go GREEN and match CI. format_gate must be RED on
archive/worktree CRLF and GREEN on the cat-file blob.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import blobread as br  # noqa: E402

ART = REPO / "command-center/receipts/TST-0334.json"
CC = REPO / "tools" / "command-center"
OUT = HERE / "probe2-gate-parity.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0334-probe2 {msg}")
    return 1


def _fn_mentions_archive(src: str, names: set[str]) -> str | None:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and "archive" in ast.dump(child).lower():
                    return node.name
    return None


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0334" not in text:
        return fail("sentinel-absent")

    src = Path(br.__file__).read_text(encoding="utf-8")
    if "cat-file" not in src:
        return fail("blobread.py does not call cat-file")
    bad = _fn_mentions_archive(
        src, {"content_bytes", "content_read", "cat_file", "git_show"}
    )
    if bad:
        return fail(f"{bad} mentions archive")

    for rel in ("validate.py", "seed.py", "render.py"):
        body = (CC / rel).read_text(encoding="utf-8")
        if "blobread" not in body or "content_bytes" not in body:
            return fail(f"{rel} does not use blobread.content_bytes")
        if "git archive" in body and "never git archive" not in body.lower():
            return fail(f"{rel} still prescribes git archive")

    live = br.live_measure()
    gates = live["gates"]
    print(
        "hash ci={0} naive_wt={1} blobread={2} | "
        "format ci={3} archive={4} naive_wt={5} blobread={6}".format(
            gates["hash_ci_blob"]["verdict"],
            gates["hash_naive_worktree"]["verdict"],
            gates["hash_blobread_local"]["verdict"],
            gates["format_ci_blob"]["verdict"],
            gates["format_archive"]["verdict"],
            gates["format_naive_worktree"]["verdict"],
            gates["format_blobread_local"]["verdict"],
        )
    )
    if gates["hash_ci_blob"]["verdict"] != "GREEN":
        return fail("CI blob hash gate not GREEN")
    if gates["hash_blobread_local"]["verdict"] != "GREEN":
        return fail("blobread local hash gate not GREEN")
    if gates["hash_naive_worktree"]["verdict"] != "RED":
        return fail("naive worktree hash did not go RED (trap not demonstrated)")
    if not live["parity"]["local_blobread_matches_ci"]:
        return fail("local blobread verdict != CI")
    if not live["parity"]["naive_worktree_differs_from_ci"]:
        return fail("naive worktree already matched CI; trap not live")
    if gates["format_ci_blob"]["verdict"] != "GREEN":
        return fail("format gate RED on LF blob")
    if gates["format_archive"]["verdict"] != "RED":
        return fail("format gate GREEN on archive CRLF")
    if gates["format_blobread_local"]["verdict"] != "GREEN":
        return fail("format gate RED on blobread local bytes")

    art_parity = doc.get("gate_parity") or {}
    if art_parity.get("local_blobread_matches_ci") is not True:
        return fail("receipt gate_parity.local_blobread_matches_ci")
    if art_parity.get("naive_worktree_differs_from_ci") is not True:
        return fail("receipt gate_parity.naive_worktree_differs_from_ci")

    payload = {
        "probe": "probe2-gate-parity",
        "unit_id": "TST-0334",
        "pass": True,
        "gates": gates,
        "parity": live["parity"],
        "content_bytes_route": live["content_bytes_route"],
        "wired": ["validate.py", "seed.py", "render.py"],
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print("naive_worktree RED; blobread GREEN matches CI; archive format RED")
    print("SUCCESS:TST-0334-probe2 gate parity both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
