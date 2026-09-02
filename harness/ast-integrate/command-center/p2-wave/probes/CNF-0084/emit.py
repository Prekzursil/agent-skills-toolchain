#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0084-cache-parity.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = H.OUT_REL
SCHEMA = H.SCHEMA_REL
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator():
    """Draft 2020-12 validator that resolves ast-integrate.invalid $ref on disk.

    This worktree's distro jsonschema is 4.10.3 (resolver=, no registry=). CI
    pins 4.25.1. Both accept this RefResolver store. Never fetch the fake host.
    """
    profiles = load_json(PROFILES)
    receipt = load_json(RECEIPT)
    store = {
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
    }
    fragment = profiles["$defs"]["determinism-report"]
    resolver = RefResolver(
        base_uri=str(profiles["$id"]),
        referrer=profiles,
        store=store,
    )
    return Draft202012Validator(fragment, resolver=resolver)


def schema_errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    doc = H.build_document()
    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0084 schema errors")
        for err in errs[:30]:
            print(" ", err)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0084", "state": "SUCCESS"},
    ):
        if schema_errors(garbage):
            garbage_rejected += 1
        else:
            print("FAILED:CNF-0084 schema accepted garbage", list(garbage)[:4])
            return 1
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if H.UNIT not in text or "SUCCESS:CNF-0084" not in text:
        print("FAILED:CNF-0084 sentinel missing from rendered artifact")
        return 1
    sentinel = str(doc.get("sentinel") or "")
    if sentinel and sentinel not in text:
        print("FAILED:CNF-0084 catalog completion_sentinel not in artifact")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    size = len(text.encode("utf-8"))
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0084 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} garbage_rejected={garbage_rejected}")
    print("SUCCESS:CNF-0084 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
