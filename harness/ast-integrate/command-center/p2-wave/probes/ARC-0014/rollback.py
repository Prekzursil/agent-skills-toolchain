#!/usr/bin/env python3
"""Rollback: restore one frozen generated file to hand-authored deploy status.

Does not add an opaque_body field to the registry. The file leaves generated_paths
and joins hand_authored_paths so the freeze hook stops treating it as a projection.
Deploy write of the restored bytes must succeed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from extract import ROLLBACK_REL  # noqa: E402
from freeze_hook import check, deploy_write  # noqa: E402


def restore_hand_authored(
    rel: str,
    source_bytes: bytes,
    deploy_root: Path,
    ledger: dict[str, Any],
) -> dict[str, Any]:
    paths = list(ledger.get("generated_paths") or [])
    if rel in paths:
        paths = [p for p in paths if p != rel]
        ledger["generated_paths"] = paths
    hand = list(ledger.get("hand_authored_paths") or [])
    if rel not in hand:
        hand.append(rel)
    ledger["hand_authored_paths"] = hand
    dest = deploy_write(deploy_root, rel, source_bytes)
    return {
        "restored_path": rel,
        "deploy_write_ok": dest.is_file() and dest.read_bytes() == source_bytes,
        "bytes": len(source_bytes),
        "hand_authored_paths": list(ledger["hand_authored_paths"]),
    }


def rehearse(
    live_root: Path,
    deploy_root: Path,
    registry: dict[str, Any],
    ledger: dict[str, Any],
    rel: str = ROLLBACK_REL,
) -> dict[str, Any]:
    source = (live_root / rel).read_bytes()
    generated_copy = (deploy_root / rel).read_bytes() if (deploy_root / rel).is_file() else b""
    deploy_write(deploy_root, rel, source)
    pre = check(deploy_root, registry, ledger)
    pre_reject = (not pre["ok"]) and any(
        r.get("path") == rel for r in pre.get("rejections") or []
    )
    deploy_write(deploy_root, rel, generated_copy)
    if not pre_reject:
        return {
            "restored_path": rel,
            "pass": False,
            "reason": "live-bytes-on-frozen-path-were-not-rejected",
            "deploy_write_ok": False,
            "freeze_rejects_sibling_tamper": False,
            "freeze_allows_restored_hand_edit": False,
            "freeze_rejected_live_bytes_before_rollback": False,
        }
    restored = restore_hand_authored(rel, source, deploy_root, ledger)
    restored["freeze_rejected_live_bytes_before_rollback"] = True
    if not restored["deploy_write_ok"]:
        restored["pass"] = False
        restored["reason"] = "deploy-write-failed"
        return restored
    # Hand-edit the restored file; freeze must allow it.
    edited = source + b"\nHAND-AUTHORED-EDIT:rollback-rehearsal\n"
    deploy_write(deploy_root, rel, edited)
    after_edit = check(deploy_root, registry, ledger)
    freeze_allows = after_edit["ok"]
    # Tamper a still-frozen sibling; freeze must reject.
    sibling = None
    for cand in ledger.get("generated_paths") or []:
        if cand != rel:
            sibling = cand
            break
    if sibling is None:
        restored["pass"] = False
        restored["reason"] = "no-frozen-sibling"
        restored["freeze_allows_restored_hand_edit"] = freeze_allows
        restored["freeze_rejects_sibling_tamper"] = False
        return restored
    sib_path = deploy_root / sibling
    original_sib = sib_path.read_bytes() if sib_path.is_file() else b""
    deploy_write(deploy_root, sibling, original_sib + b"\nHAND-EDIT TAMPER\n")
    after_tamper = check(deploy_root, registry, ledger)
    rejects = (not after_tamper["ok"]) and any(
        r.get("path") == sibling for r in after_tamper.get("rejections") or []
    )
    # restore sibling so later checks are clean
    deploy_write(deploy_root, sibling, original_sib)
    passed = (
        restored["deploy_write_ok"]
        and freeze_allows
        and rejects
    )
    return {
        **restored,
        "freeze_allows_restored_hand_edit": freeze_allows,
        "freeze_rejects_sibling_tamper": rejects,
        "sibling": sibling,
        "pass": passed,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="A2 hand-authored rollback")
    p.add_argument("--rel", default=ROLLBACK_REL)
    p.add_argument("--live-root", required=True)
    p.add_argument("--deploy-root", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--ledger", required=True)
    args = p.parse_args()
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    ledger_path = Path(args.ledger)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    result = rehearse(Path(args.live_root), Path(args.deploy_root), registry, ledger, args.rel)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
