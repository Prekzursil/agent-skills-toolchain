#!/usr/bin/env python3
"""Live shipped-CLI / schema / docs slice for TST-0112 (honest counts, not a greenwash)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_PARSERS = [
    "tools/command-center/validate.py",
    "tools/command-center/seed.py",
    "tools/command-center/render.py",
    "tools/command-center/close.py",
    "tools/command-center/reconcile_delivery.py",
    "tools/command-center/measure_rate.py",
    "tools/command-center/unit_manifest.py",
    "tools/command-center/discrepancy_router.py",
    "tools/plugin/cli.py",
    "tools/plugin/repair.py",
    "tools/plugin/interpreter_probe.py",
]

LIVE_SCHEMAS = [
    "tools/plugin/schema/interpreter-probe.schema.json",
    "tools/plugin/schema/drift-classification.schema.json",
]


def _md_files() -> list[Path]:
    roots = [
        REPO / "tools" / "command-center",
        REPO / "tools" / "plugin",
        REPO / "command-center",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            rel = path.relative_to(REPO).as_posix()
            if "/p2-wave/" in rel or "/fixtures/" in rel or "/vendor/" in rel:
                continue
            if path.name.upper() in {"CHANGELOG.md"}:
                continue
            out.append(path)
    return sorted(out)


def load_live_inputs() -> dict:
    parser_sources = []
    parser_paths = []
    for rel in LIVE_PARSERS:
        path = REPO / rel
        if path.is_file():
            parser_sources.append(path.read_text(encoding="utf-8"))
            parser_paths.append(rel)
    schemas = []
    schema_paths = []
    for rel in LIVE_SCHEMAS:
        path = REPO / rel
        if path.is_file():
            schemas.append(json.loads(path.read_text(encoding="utf-8")))
            schema_paths.append(rel)
    docs = []
    doc_paths = []
    for path in _md_files():
        docs.append(path.read_text(encoding="utf-8"))
        doc_paths.append(path.relative_to(REPO).as_posix())
    return {
        "parser_sources": parser_sources,
        "parser_paths": parser_paths,
        "schemas": schemas,
        "schema_paths": schema_paths,
        "doc_texts": docs,
        "doc_paths": doc_paths,
    }
