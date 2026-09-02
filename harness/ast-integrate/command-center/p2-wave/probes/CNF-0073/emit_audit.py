#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0073-multilingual-recheck.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

OUT = A.OUT_REL
SCHEMA = A.SCHEMA_REL


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0073 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    return {
        "path": rel,
        "line": find_line(rel, snippet),
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
    }


def main() -> int:
    doc = A.build_document(tests_result="PASS")
    if doc["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0073 state={doc['state']} class={doc.get('classification')}")
        return 1
    if not doc.get("second_path_named_and_different"):
        print("FAILED:CNF-0073 second path not named and different")
        return 1
    for row in doc["citations"]:
        texts = [t["text"] for t in row["translations"]]
        names = [t["path_name"] for t in row["translations"]]
        if len(texts) < 2 or not all(texts) or names[0] == names[1]:
            print(f"FAILED:CNF-0073 translations incomplete {row['id']}")
            return 1

    doc["evidence"] = [
        ev(
            "command-center/p2-wave/probes/CNF-0073/fixtures/citation-inventory.json",
            "该工作流可能不会在超时后自动重试。",
            "inventory",
            "Original-language cited span is pinned with its recorded translation.",
        ),
        ev(
            "command-center/p2-wave/probes/CNF-0073/translate.py",
            'PATH_INDEPENDENT = "hedge-tag-transfer-v1"',
            "probe",
            "Second translation path is a named live algorithm, not the inventory gloss re-run.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "a dropped hedge or qualifier is a material change",
            "catalog",
            "Catalog requires a dropped hedge to be filed even when the headline survives.",
        ),
        ev(
            "command-center/schema/citation-audit.schema.json",
            '"title": "Citation audit (Phase 11 confirmation)"',
            "schema",
            "Output parses against citation-audit.schema.json.",
        ),
        ev(
            "command-center/p2-wave/probes/CNF-0073/fixtures/hedges.json",
            '"id": "possibly"',
            "inventory",
            "Qualifier lexicon treats epistemic hedges as first-class tokens.",
        ),
    ]

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0073 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 200}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0073 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size <= 0:
        print("FAILED:CNF-0073 empty artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0073 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
