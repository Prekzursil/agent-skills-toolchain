#!/usr/bin/env python3
"""Declared downstream consumer for the attack-artifact class.

Condition 12's intent is that a real consumer can open, parse, and extract a
required field — not that a receipt flag says executed=true.

This consumer requires `records` to be a non-empty list of objects, each with:
  id: nonempty string
  sha256: 64 lowercase hex
  status: exactly "OK"
  kind: one of {receipt, report, ledger}

It never consults the 12 syntactic completion fields. A reducer PASS with a
nonzero exit here is the counterexample.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VALID_KINDS = frozenset({"receipt", "report", "ledger"})


def consume_document(doc: Any) -> tuple[int, str]:
    if not isinstance(doc, dict):
        return 1, "not-an-object"
    records = doc.get("records")
    if not isinstance(records, list) or len(records) < 1:
        return 2, "records-missing-or-empty"
    extracted: list[str] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            return 3, f"record[{i}]-not-object"
        rid = rec.get("id")
        sha = rec.get("sha256")
        status = rec.get("status")
        kind = rec.get("kind")
        if not isinstance(rid, str) or not rid.strip():
            return 4, f"record[{i}]-id-unusable"
        if not isinstance(sha, str) or not SHA_RE.match(sha):
            return 5, f"record[{i}]-sha256-unusable:{sha!r}"
        if status != "OK":
            return 6, f"record[{i}]-status-not-accepted:{status!r}"
        if kind not in VALID_KINDS:
            return 7, f"record[{i}]-kind-not-accepted:{kind!r}"
        extracted.append(rid)
    return 0, f"read-ok n={len(extracted)} first_id={extracted[0]}"


def consume_file(path: Path) -> tuple[int, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return 1, f"parse-fail:{type(exc).__name__}"
    code, why = consume_document(doc)
    return code, why


def live_delivery_gate(path: Path) -> tuple[bool, str]:
    """ready_units.artifact_delivered — the live P2 fan-in on this tree.

    Does not evaluate condition 12. With resolver=None (platform absent),
    schema validation is also skipped. A PASS here on an unusable artifact
    is independent evidence that c12 is decorative at the live call site.
    """
    rel = path.resolve().relative_to(REPO).as_posix()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"unparseable:{type(exc).__name__}"
    sentinel = doc.get("sentinel") if isinstance(doc, dict) else None
    unit = {
        "id": "ADV-0001-FIXTURE",
        "output_path": rel,
        "output_schema": "",
        "completion_sentinel": sentinel if isinstance(sentinel, str) else "SUCCESS:",
    }
    cc = REPO / "command-center"
    if str(cc) not in sys.path:
        sys.path.insert(0, str(cc.parent))
    try:
        from command_center_ready import artifact_delivered  # type: ignore
    except ImportError:
        pass
    try:
        sys.path.insert(0, str(cc))
        import ready_units as ru  # type: ignore
    except Exception as exc:  # pragma: no cover - import environment
        return False, f"ready_units-unimportable:{type(exc).__name__}"
    ok, why = ru.artifact_delivered(unit, resolver=None)
    return bool(ok), str(why)


def production_inventory() -> dict:
    """What of B07/CC-0003 actually exists on this worktree."""
    paths = {
        "platform_lib_completion_predicate": "platform/lib/completion_predicate.py",
        "platform_schema_receipt": "platform/schema/receipt.schema.json",
        "command_center_receipt_schema": "command-center/schema/receipt.schema.json",
        "completion_gates": "command-center/COMPLETION-GATES.json",
        "cc0003_receipt": "command-center/receipts/CC-0003.json",
        "artifact_manifest": "command-center/ARTIFACT-MANIFEST.json",
        "ready_units": "command-center/ready_units.py",
        "imp0433_builder": "command-center/p2-wave/_build_IMP0433.py",
    }
    out = {}
    for key, rel in paths.items():
        p = REPO / rel
        out[key] = {
            "path": rel,
            "present": p.is_file(),
            "bytes": p.stat().st_size if p.is_file() else 0,
        }
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if target is None:
        print("usage: consumer.py <artifact.json>")
        raise SystemExit(2)
    code, why = consume_file(target)
    print(f"exit={code} {why}")
    raise SystemExit(code)
