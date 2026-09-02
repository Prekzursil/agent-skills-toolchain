#!/usr/bin/env python3
"""Docs-vs-code parity for one surface (fixture tree or live repo slice)."""
from __future__ import annotations

import json
from pathlib import Path

from extract import (
    code_paths_from_parser_source,
    diff,
    flags_from_docs,
    flags_from_parser_source,
    keys_from_docs,
    keys_from_schema,
    paths_from_docs,
    resolve_paths,
    tree_files,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def measure_fixture(root: Path) -> dict:
    docs = _read(root / "docs.md")
    parser_src = _read(root / "parser.py")
    schema = json.loads(_read(root / "schema.json"))

    doc_flags, mention_flags = flags_from_docs(docs)
    parser_flags = flags_from_parser_source(parser_src)
    flag_diff = diff(doc_flags, parser_flags)

    doc_keys, mention_keys = keys_from_docs(docs)
    schema_keys = keys_from_schema(schema)
    key_diff = diff(doc_keys, schema_keys)

    doc_paths, mention_paths = paths_from_docs(docs)
    path_res = resolve_paths(doc_paths, root)
    tree = tree_files(root)
    tree_undoc = sorted(tree - set(doc_paths))
    path_res["tree"] = sorted(tree)
    path_res["tree_not_documented"] = tree_undoc
    path_res["tree_not_documented_count"] = len(tree_undoc)
    path_res["code_declared_paths"] = sorted(code_paths_from_parser_source(parser_src))

    return {
        "root": str(root),
        "flags": {
            **flag_diff,
            "mention_only": sorted(mention_flags),
        },
        "keys": {
            **key_diff,
            "mention_only": sorted(mention_keys),
        },
        "paths": {
            **path_res,
            "mention_only": sorted(mention_paths),
        },
    }


def measure_sources(doc_texts: list[str], parser_sources: list[str], schemas: list[object], tree_root: Path) -> dict:
    doc_flags: set[str] = set()
    mention_flags: set[str] = set()
    doc_keys: set[str] = set()
    mention_keys: set[str] = set()
    doc_paths: set[str] = set()
    mention_paths: set[str] = set()
    parser_flags: set[str] = set()
    schema_keys: set[str] = set()
    code_paths: set[str] = set()

    for text in doc_texts:
        f, mf = flags_from_docs(text)
        doc_flags |= f
        mention_flags |= mf
        k, mk = keys_from_docs(text)
        doc_keys |= k
        mention_keys |= mk
        p, mp = paths_from_docs(text)
        doc_paths |= p
        mention_paths |= mp
    for src in parser_sources:
        parser_flags |= flags_from_parser_source(src)
        code_paths |= code_paths_from_parser_source(src)
    for schema in schemas:
        schema_keys |= keys_from_schema(schema)

    flag_diff = diff(doc_flags, parser_flags)
    key_diff = diff(doc_keys, schema_keys)
    path_res = resolve_paths(doc_paths, tree_root)
    code_undoc = sorted(set(code_paths) - set(doc_paths))
    path_res["code_declared_paths"] = sorted(code_paths)
    path_res["tree_not_documented"] = code_undoc
    path_res["tree_not_documented_count"] = len(code_undoc)
    return {
        "flags": {**flag_diff, "mention_only": sorted(mention_flags - doc_flags)},
        "keys": {**key_diff, "mention_only": sorted(mention_keys - doc_keys)},
        "paths": {**path_res, "mention_only": sorted(mention_paths - doc_paths)},
    }
