#!/usr/bin/env python3
"""Probe 2: static review of post-normalisation containment (not from probe 1).

A pre-normalisation startswith('..') check is bypassable via pkg/../../escape.
This probe re-derives the guard from source + AST, then confirms the production
function rejects that name after posixpath.normpath.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.archive_extract import (  # noqa: E402
    ArchiveExtractError,
    normalize_member_name,
)

ART = REPO / "command-center/adversarial/ADV-0027-archive-extraction-traversal-attacks.json"
SRC = REPO / "tools/marketplace/archive_extract.py"
SCHEMA = REPO / "command-center/schema/exploit-proof.schema.json"
BYPASS = "pkg/../../escape.beacon"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0027-probe2 {msg}")
    return 1


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_named(fn: ast.FunctionDef, name: str) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def _uses_normpath(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr == "normpath":
            return True
    return False


def _extractall_calls(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "extractall":
                lines.append(getattr(node, "lineno", 0))
    return lines


def main() -> int:
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    extractall_in_import_path = _extractall_calls(tree)
    norm_fn = _fn(tree, "normalize_member_name")
    contain_fn = _fn(tree, "assert_contained_after_normalize")
    extract_fn = _fn(tree, "extract_import_archive")
    if norm_fn is None or contain_fn is None or extract_fn is None:
        return fail("required functions missing from archive_extract.py")

    pre_startswith_only = BYPASS.startswith("..")
    try:
        normalize_member_name(BYPASS)
        post = {"raised": False, "code": None}
    except ArchiveExtractError as exc:
        post = {"raised": True, "code": exc.code, "member": exc.member}

    contain_calls_normalize = _calls_named(contain_fn, "normalize_member_name")
    contain_relative_to = _calls_named(contain_fn, "relative_to")
    norm_uses_normpath = _uses_normpath(norm_fn)
    extract_calls_contain = _calls_named(extract_fn, "assert_contained_after_normalize")

    schema_ok = False
    garbage_rejected = []
    jsonschema = None
    if SCHEMA.is_file():
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            jsonschema = None  # type: ignore
        if jsonschema is not None:
            if ART.is_file():
                doc = json.loads(ART.read_text(encoding="utf-8"))
                jsonschema.Draft7Validator(schema).validate(doc)
                schema_ok = True
            for garbage in ({}, {"unit_id": 1}, {"nope": True}):
                errs = list(jsonschema.Draft7Validator(schema).iter_errors(garbage))
                garbage_rejected.append({"sample": garbage, "n_errs": len(errs)})
                if not errs:
                    return fail(f"schema accepted garbage {garbage}")

    # Independent extractall census outside the import path (context only).
    other_extractall: list[str] = []
    for path in (REPO / "tools").rglob("*.py"):
        if path.resolve() == SRC.resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "extractall" in text:
            rel = path.relative_to(REPO).as_posix()
            other_extractall.append(rel)

    checks = {
        "extractall_in_import_path": extractall_in_import_path,
        "normalize_uses_posixpath_normpath": norm_uses_normpath,
        "contain_calls_normalize_first": contain_calls_normalize,
        "contain_uses_relative_to": contain_relative_to,
        "extract_calls_containment": extract_calls_contain,
        "pre_normalize_startswith_dotdot": pre_startswith_only,
        "post_normalize_raises_TRAVERSAL": post.get("code") == "TRAVERSAL",
        "schema_validates_artifact_if_present": schema_ok or not ART.is_file(),
        "garbage_rejected": garbage_rejected,
        "other_tools_extractall": other_extractall,
    }
    printable = {
        "probe": "probe2-static-post-normalization-containment",
        "unit_id": "ADV-0027",
        "bypass_member": BYPASS,
        "checks": checks,
        "post": post,
        "source": "tools/marketplace/archive_extract.py",
        "computed_not_asserted": True,
    }
    print(json.dumps(printable, sort_keys=True))

    if extractall_in_import_path:
        return fail(f"import path calls extractall at {extractall_in_import_path}")
    if pre_startswith_only:
        return fail("bypass member unexpectedly startswith('..')")
    if post.get("code") != "TRAVERSAL":
        return fail(f"post-normalize did not TRAVERSAL: {post}")
    if not norm_uses_normpath:
        return fail("normalize_member_name does not call posixpath.normpath")
    if not contain_calls_normalize:
        return fail("assert_contained_after_normalize does not call normalize_member_name")
    if not contain_relative_to:
        return fail("containment missing Path.relative_to after resolve")
    if not extract_calls_contain:
        return fail("extract_import_archive does not call assert_contained_after_normalize")
    if "extractall(" in source:
        return fail("extractall leftover in import-path source")
    if ART.is_file() and jsonschema is not None and not schema_ok:
        return fail("artifact present but schema validation skipped")

    print(
        f"post_normpath_TRAVERSAL=True startswith_bypass={not pre_startswith_only} "
        f"no_extractall=True other_tools={other_extractall}"
    )
    print("SUCCESS:ADV-0027-probe2 static: containment runs AFTER normalisation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
