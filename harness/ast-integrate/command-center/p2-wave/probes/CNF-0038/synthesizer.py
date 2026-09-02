"""Synthesize an independent test from a CNF-0005 brief. Never open author test/diff."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import leak_detector as L
from paths import (
    ACCESS_LOG,
    AUTHOR_TEST,
    BRIEF_PATH,
    DIFF_PATCH,
    FORBIDDEN_DIR_PARTS,
    FORBIDDEN_NAMES,
    GENERATED,
    IMPLEMENTER_NOTES,
    PUBLIC_API,
    REPO,
    REQUIREMENT,
    SYNTH_TEST,
)

CASE_RE = re.compile(
    r"### CASE id=(?P<id>\S+)\s+"
    r"INPUT=(?P<input>\{.*?\})\s+"
    r"EXPECT_OK=(?P<ok>true|false)\s+"
    r"EXPECT_REASON=(?P<reason>\S+)",
    re.S,
)
API_NAME_RE = re.compile(
    r"public API function\s+(\w+)\s+in\s+module\s+(\w+)",
    re.I,
)


class LeakError(RuntimeError):
    """Synthesizer opened a forbidden path."""


def _rel_parts(path: Path) -> set[str]:
    return set(path.as_posix().split("/"))


def guarded_read(path: Path, log: list[dict]) -> str:
    resolved = path.resolve()
    name = resolved.name
    parts = _rel_parts(resolved)
    rec = {"path": str(resolved), "name": name, "allowed": True}
    if name in FORBIDDEN_NAMES or resolved in {AUTHOR_TEST.resolve(), DIFF_PATCH.resolve(), IMPLEMENTER_NOTES.resolve()}:
        rec["allowed"] = False
        log.append(rec)
        raise LeakError(f"forbidden file {name}")
    if parts & FORBIDDEN_DIR_PARTS:
        rec["allowed"] = False
        log.append(rec)
        raise LeakError(f"forbidden snapshot dir in {resolved}")
    log.append(rec)
    return resolved.read_text(encoding="utf-8")


def parse_cases(requirement: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for m in CASE_RE.finditer(requirement):
        payload = json.loads(m.group("input"))
        cases.append(
            {
                "id": m.group("id"),
                "input": payload,
                "expect_ok": m.group("ok") == "true",
                "expect_reason": m.group("reason"),
            }
        )
    if len(cases) < 2:
        raise SystemExit("FAILED:CNF-0038 requirement has fewer than 2 CASE blocks")
    return cases


def parse_api(requirement: str, surface: str) -> tuple[str, str]:
    m = API_NAME_RE.search(requirement)
    if not m:
        raise SystemExit("FAILED:CNF-0038 requirement does not name public API function/module")
    func, mod = m.group(1), m.group(2)
    tree = ast.parse(surface)
    names = {
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if func not in names:
        raise SystemExit(f"FAILED:CNF-0038 public API surface has no {func}()")
    return func, mod


def render_test(func: str, mod: str, cases: list[dict[str, Any]]) -> str:
    return f'''#!/usr/bin/env python3
"""Independently synthesised from the requirement + public API surface.

Not copied from an author test. Not derived from a diff.
"""
from __future__ import annotations

import sys

from {mod} import {func}

CASES = {cases!r}


def main() -> int:
    failed = 0
    for case in CASES:
        got = {func}(case["input"])
        ok = got.get("ok") is case["expect_ok"] and got.get("reason") == case["expect_reason"]
        print(
            "CASE {{id}} got={{got!r}} expect_ok={{expect_ok}} "
            "expect_reason={{expect_reason}} pass={{ok}}".format(
                id=case["id"],
                got=got,
                expect_ok=case["expect_ok"],
                expect_reason=case["expect_reason"],
                ok=ok,
            )
        )
        if not ok:
            failed += 1
    print("SUMMARY failed={{0}} of {{1}}".format(failed, len(CASES)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def synthesise(brief: dict | None = None) -> dict:
    GENERATED.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []
    if brief is None:
        brief_text = guarded_read(BRIEF_PATH, log)
        brief = json.loads(brief_text)
    else:
        log.append({"path": str(BRIEF_PATH), "name": BRIEF_PATH.name, "allowed": True, "in_memory": True})
    claim = brief["claim_statement"]
    surface = brief["public_api_surface"]
    hits = L.scan(claim + "\n" + surface + "\n" + json.dumps(brief))
    if hits:
        raise SystemExit(f"FAILED:CNF-0038 synthesizer brief leaked {hits}")
    # Re-read the two allowed inputs so the access log names them.
    guarded_read(REQUIREMENT, log)
    guarded_read(PUBLIC_API, log)
    func, mod = parse_api(claim, surface)
    cases = parse_cases(claim)
    source = render_test(func, mod, cases)
    if L.scan(source):
        raise SystemExit("FAILED:CNF-0038 synthesised test contains leak markers")
    SYNTH_TEST.write_text(source, encoding="utf-8")
    ACCESS_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    return {
        "path": SYNTH_TEST.relative_to(REPO).as_posix(),
        "source": source,
        "derived_from": ["requirement", "public_api"],
        "author_test_bytes_read": 0,
        "diff_bytes_read": 0,
        "cases": cases,
        "function": func,
        "module": mod,
        "access_log": log,
    }
