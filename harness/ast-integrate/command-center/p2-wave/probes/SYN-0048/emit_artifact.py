#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0048.handoff-package.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import package as P  # noqa: E402
import resume as R  # noqa: E402
import schema_local as S  # noqa: E402
from store import NoteStore, run_self_check  # noqa: E402


def main() -> int:
    store_check = run_self_check()
    fixture_failures = R.run_fixture_battery()
    if fixture_failures:
        print("FAILED:SYN-0048 emit resume fixtures")
        for item in fixture_failures:
            print(f"  {item}")
        return 1
    if not store_check.get("delete_refused") or not store_check.get("resolve_control_fired"):
        print(f"FAILED:SYN-0048 emit store self-check {store_check}")
        return 1

    store = NoteStore(REPO / P.VAULT)
    doc = P.build(store)
    errors = S.error_list(doc)
    if errors:
        fp = hashlib.sha256("\n".join(errors).encode("utf-8")).hexdigest()[:16]
        print("FAILED:SYN-0048 schema")
        print(f"error_fingerprint={fp}")
        for err in errors[:12]:
            print(f"  {err}")
        return 1

    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    sentinel = str(doc.get("sentinel") or "")
    if "SUCCESS:SYN-0048" not in sentinel or sentinel not in text:
        print("FAILED:SYN-0048 sentinel missing from serialized artifact")
        return 1

    out = REPO / P.OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {P.OUT} next_action={doc['report']['next_action']['kind']}")
    print("SUCCESS:SYN-0048-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
