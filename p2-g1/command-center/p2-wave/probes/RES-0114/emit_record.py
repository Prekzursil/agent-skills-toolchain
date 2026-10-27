#!/usr/bin/env python3
"""Emit command-center/research/RES-0114.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
from engine import (  # noqa: E402
    build_record,
    schema_rejects_garbage,
    schema_rejects_stripped_lineage,
    validate_against_schema,
)

OUT = REPO / C.OUTPUT_REL


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    if not schema_rejects_garbage():
        print("FAILED:RES-0114 schema accepted garbage")
        return 1
    doc = build_record()
    if not schema_rejects_stripped_lineage(doc):
        print("FAILED:RES-0114 source_lineage-stripped mutant was accepted")
        return 1
    errs = validate_against_schema(doc)
    if errs:
        print("FAILED:RES-0114 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1
    mapping = doc.get("silent_download_mapping") or {}
    if mapping.get("catching_property_id") != C.CATCHING_PROPERTY_ID:
        print("FAILED:RES-0114 catching property not mapped")
        return 1
    if mapping.get("would_have_caught") is not True:
        print("FAILED:RES-0114 would_have_caught is not true")
        return 1
    imp = doc.get("impossible_property") or {}
    if imp.get("id") != C.IMPOSSIBLE_PROPERTY_ID:
        print("FAILED:RES-0114 impossible property not named")
        return 1
    if imp.get("satisfiable_by_agent_run_with_live_model_and_web") is not False:
        print("FAILED:RES-0114 impossible property marked satisfiable")
        return 1
    if "M-PLANTED-NO-BASELINE" in (doc.get("promoted_mechanisms") or []):
        print("FAILED:RES-0114 E3-no-baseline was promoted")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if C.SENTINEL not in text:
        print("FAILED:RES-0114 sentinel missing from serialized artifact")
        return 1
    OUT.write_text(text, encoding="utf-8")
    digest, size = sha256_file(OUT)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0114 artifact {size}B below floor")
        return 1
    print(f"wrote {C.OUTPUT_REL} bytes={size} sha256={digest}")
    print(
        "promoted={p} held={h} catch={c} impossible={i} state={st}".format(
            p=len(doc.get("promoted_mechanisms") or []),
            h=len(doc.get("e3_held_out") or []),
            c=mapping.get("catching_property_id"),
            i=imp.get("id"),
            st=doc.get("state"),
        )
    )
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0114 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:RES-0114 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
