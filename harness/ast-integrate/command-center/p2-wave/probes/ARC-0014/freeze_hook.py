#!/usr/bin/env python3
"""Freeze hook: after A2-FREEZE-GENERATED, reject hand-edits of deployed copies.

A path on the freeze ledger's generated_paths is TAMPERED when classify() says
so. Paths moved to hand_authored_paths by rollback are exempt (hand-authorability
restored). This exemption lives on the ledger, not as an opaque registry field.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARC10 = HERE.parent / "ARC-0010"
sys.path.insert(0, str(ARC10))
import generator as G  # noqa: E402

from extract import SAMPLE_RELS  # noqa: E402

FREEZE_ID = "A2-FREEZE-GENERATED"
HOOK_REL = "command-center/p2-wave/probes/ARC-0014/freeze_hook.py"


def default_ledger(generated_paths: list[str] | None = None) -> dict[str, Any]:
    return {
        "frozen": True,
        "freeze_point": FREEZE_ID,
        "generated_paths": list(generated_paths or SAMPLE_RELS),
        "hand_authored_paths": [],
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(
    deploy_root: Path,
    registry: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    if not ledger.get("frozen"):
        return {
            "ok": True,
            "reason": "not-frozen",
            "rejections": [],
            "rows": [],
        }
    expected = G.generate(registry)
    generated = set(ledger.get("generated_paths") or [])
    hand = set(ledger.get("hand_authored_paths") or [])
    rows = []
    rejections = []
    for rel in sorted(generated):
        if rel in hand:
            rows.append({"path": rel, "status": "HAND-AUTHORED", "reason": "ledger-exempt"})
            continue
        path = deploy_root / rel
        rec = G.classify(path, registry, expected, rel)
        rows.append(rec)
        if rec.get("status") == "TAMPERED":
            rejections.append(rec)
    return {
        "ok": not rejections,
        "reason": "tampered-generated" if rejections else "clean-or-exempt",
        "rejections": rejections,
        "rows": rows,
    }


def deploy_write(deploy_root: Path, rel: str, data: bytes) -> Path:
    dest = deploy_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def main() -> int:
    p = argparse.ArgumentParser(description="A2 freeze hook")
    p.add_argument("--root", required=True, help="deploy tree root")
    p.add_argument("--registry", required=True, help="registry json")
    p.add_argument("--ledger", required=True, help="freeze ledger json")
    args = p.parse_args()
    registry = load_json(Path(args.registry))
    ledger = load_json(Path(args.ledger))
    result = check(Path(args.root), registry, ledger)
    print(json.dumps({k: result[k] for k in ("ok", "reason", "rejections")}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
