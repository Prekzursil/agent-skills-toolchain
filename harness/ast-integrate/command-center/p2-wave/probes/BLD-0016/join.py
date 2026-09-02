#!/usr/bin/env python3
"""Structural requirement↔test join for BLD-0043.

A mapping counts only when it is STRUCTURAL:
  * the REQ id appears in the test function name, or
  * a pytest.mark.req / REQ_IDS marker in code (not a comment), or
  * a TEST-REGISTRY (or fixture registry) entry names the pair.

A REQ id that appears only in a comment is unmapped.
"""
from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REQ_RE = re.compile(r"REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*")
# Uppercase tokens only so test_REQ_FX_01_work… maps to REQ-FX-01, not the
# remainder of the function name.
TEST_REQ_NAME_RE = re.compile(r"REQ(?:_[A-Z0-9]+)+")
MARKER_RE = re.compile(
    r"""mark\.req\(\s*['"](REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*)['"]""",
)
REQ_IDS_ASSIGN_RE = re.compile(
    r"""REQ_IDS\s*=\s*\(\s*['"](REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*)['"]""",
)

PROMOTE = "promote"
RETIRE = "retire"
CHANNELS = ("test-id", "marker", "registry-entry")


@dataclass
class Requirement:
    id: str
    text: str
    source_path: str
    source_line: int
    tokens: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source_path": self.source_path,
            "source_line": self.source_line,
            "tokens": list(self.tokens),
        }


@dataclass
class TestRec:
    id: str
    path: str
    name: str
    source: str
    registry_req_ids: tuple[str, ...] = ()
    corpus: str = "live"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "corpus": self.corpus,
        }


@dataclass
class Mapping:
    requirement_id: str
    test_id: str
    channel: str

    def as_dict(self) -> dict[str, str]:
        return {
            "requirement_id": self.requirement_id,
            "test_id": self.test_id,
            "channel": self.channel,
        }


@dataclass
class JoinResult:
    requirements: list[Requirement]
    tests: list[TestRec]
    mappings: list[Mapping]
    untested: list[dict[str, str]]
    orphans: list[dict[str, str]]
    comment_only: list[dict[str, str]] = field(default_factory=list)

    def mapped_req_ids(self) -> set[str]:
        return {m.requirement_id for m in self.mappings}

    def mapped_test_ids(self) -> set[str]:
        return {m.test_id for m in self.mappings}


def name_to_req_ids(name: str, known: Iterable[str] = ()) -> set[str]:
    found: set[str] = set()
    for match in TEST_REQ_NAME_RE.findall(name):
        found.add(match.replace("_", "-"))
    needle = f"_{name.upper().replace('-', '_')}_"
    for rid in known:
        alt = rid.upper().replace("-", "_")
        if alt and f"_{alt}_" in needle:
            found.add(rid)
    return {rid for rid in found if rid.startswith("REQ-")}


def comment_req_ids(source: str) -> set[str]:
    found: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                found |= set(REQ_RE.findall(tok.string.upper()))
    except tokenize.TokenError:
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                found |= set(REQ_RE.findall(stripped.upper()))
    return found


def code_marker_req_ids(source: str) -> set[str]:
    found: set[str] = set()
    found |= set(MARKER_RE.findall(source))
    found |= set(REQ_IDS_ASSIGN_RE.findall(source))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name == "req" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    found |= set(REQ_RE.findall(arg0.value))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REQ_IDS":
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                found |= set(REQ_RE.findall(elt.value))
    return found


def structural_channels(
    test: TestRec, known: Iterable[str] = ()
) -> dict[str, set[str]]:
    return {
        "test-id": name_to_req_ids(test.name, known),
        "marker": code_marker_req_ids(test.source),
        "registry-entry": set(test.registry_req_ids),
    }


def structural_ids(test: TestRec, known: Iterable[str] = ()) -> set[str]:
    ch = structural_channels(test, known)
    return ch["test-id"] | ch["marker"] | ch["registry-entry"]


def classify_orphan(test: TestRec) -> tuple[str, str]:
    """Every orphan gets exactly one of promote/retire. Never unclassified."""
    blob = f"{test.name}\n{test.path}\n{test.source}".lower()
    creep_hints = (
        "scope_creep",
        "unrelated",
        "helper_speed",
        "sleep_is_fast",
        "orphan_creep",
    )
    if any(h in blob for h in creep_hints):
        return (
            RETIRE,
            "SCOPE CREEP: test body does not falsify a CC-0024 requirement; "
            "retire it rather than silently counting it as coverage.",
        )
    if test.corpus == "live":
        return (
            PROMOTE,
            "UNDOCUMENTED REQUIREMENT: live test guards catalog/registry/"
            "close machinery that CC-0024 floor records do not name; promote "
            "it into the requirement register rather than treating the hole "
            "as coverage.",
        )
    return (
        PROMOTE,
        "UNDOCUMENTED REQUIREMENT: fixture/test has no structural REQ link "
        "and was not identified as scope creep; promote for owner decision.",
    )


def join(
    requirements: Iterable[Requirement],
    tests: Iterable[TestRec],
) -> JoinResult:
    reqs = list(requirements)
    tlist = list(tests)
    req_ids = {r.id for r in reqs}
    mappings: list[Mapping] = []
    comment_only: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for test in tlist:
        ch = structural_channels(test, req_ids)
        comments = comment_req_ids(test.source)
        structural = ch["test-id"] | ch["marker"] | ch["registry-entry"]
        for channel in CHANNELS:
            for rid in sorted(ch[channel]):
                if rid not in req_ids:
                    continue
                key = (rid, test.id, channel)
                if key in seen:
                    continue
                seen.add(key)
                mappings.append(
                    Mapping(
                        requirement_id=rid,
                        test_id=test.id,
                        channel=channel,
                    )
                )
        only_comment = comments - structural
        for rid in sorted(only_comment):
            comment_only.append(
                {
                    "test_id": test.id,
                    "requirement_id": rid,
                    "reason": "comment-only mapping is unmapped",
                }
            )

    mapped_reqs = {m.requirement_id for m in mappings}
    mapped_tests = {m.test_id for m in mappings}
    untested = [
        {
            "id": r.id,
            "reason": "no structural test mapping (test-id, marker, or registry-entry)",
        }
        for r in reqs
        if r.id not in mapped_reqs
    ]
    orphans: list[dict[str, str]] = []
    for test in tlist:
        if test.id in mapped_tests:
            continue
        classification, reason = classify_orphan(test)
        if classification not in {PROMOTE, RETIRE}:
            raise RuntimeError(f"unclassified orphan {test.id}")
        orphans.append(
            {
                "id": test.id,
                "path": test.path,
                "classification": classification,
                "reason": reason,
            }
        )
    return JoinResult(
        requirements=reqs,
        tests=tlist,
        mappings=mappings,
        untested=untested,
        orphans=orphans,
        comment_only=comment_only,
    )


def discover_tests(root: Path, rel_dir: str, corpus: str) -> list[TestRec]:
    tests: list[TestRec] = []
    directory = root / rel_dir
    if not directory.is_dir():
        return tests
    for path in sorted(directory.rglob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        rel = path.relative_to(root).as_posix()
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        lines = src.splitlines()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            start = node.lineno
            if node.decorator_list:
                start = min(
                    getattr(dec, "lineno", start) for dec in node.decorator_list
                )
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            snippet = "\n".join(lines[start - 1 : end])
            tests.append(
                TestRec(
                    id=f"{rel}::{node.name}",
                    path=rel,
                    name=node.name,
                    source=snippet,
                    corpus=corpus,
                )
            )
    return tests


def load_registry_maps(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    entries: list[Any] = []
    if isinstance(doc, dict):
        for key in ("tests", "entries", "items"):
            if isinstance(doc.get(key), list):
                entries.extend(doc[key])
        for suite in doc.get("suites") or []:
            if not isinstance(suite, dict):
                continue
            suite_path = str(suite.get("path") or "")
            for name in suite.get("tests") or []:
                if isinstance(name, str):
                    entries.append(
                        {
                            "id": f"{suite_path}::{name}" if suite_path else name,
                            "name": name,
                            "requirement_ids": suite.get("requirement_ids") or [],
                        }
                    )
            for inv in doc.get("invariants") or []:
                if not isinstance(inv, dict):
                    continue
                reqs = inv.get("requirement_ids") or inv.get("req_ids") or []
                if inv.get("id") and str(inv["id"]).startswith("REQ-"):
                    reqs = list(reqs) + [str(inv["id"])]
                for name in inv.get("tests") or []:
                    if isinstance(name, str):
                        entries.append(
                            {
                                "id": name,
                                "name": name,
                                "requirement_ids": reqs,
                            }
                        )
    elif isinstance(doc, list):
        entries = doc
    for item in entries:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or item.get("nodeid") or item.get("name") or "")
        if not tid:
            continue
        reqs = item.get("requirement_ids") or item.get("req_ids") or []
        if item.get("req_id"):
            reqs = list(reqs) + [item["req_id"]]
        ids = tuple(
            str(r) for r in reqs if isinstance(r, str) and r.startswith("REQ-")
        )
        if ids:
            out[tid] = ids
            # also index by function name so short registry ids resolve
            if "::" in tid:
                out[tid.split("::", 1)[1]] = ids
            elif tid.startswith("test_"):
                out[tid] = ids
    return out


def apply_registry(tests: list[TestRec], mapping: dict[str, tuple[str, ...]]) -> None:
    for test in tests:
        extra: list[str] = []
        for key in (test.id, test.name, test.path + "::" + test.name):
            extra.extend(mapping.get(key) or ())
        if extra:
            test.registry_req_ids = tuple(dict.fromkeys(extra))


def dump_join(result: JoinResult) -> dict[str, Any]:
    unclassified = [
        o for o in result.orphans if o.get("classification") not in {PROMOTE, RETIRE}
    ]
    if unclassified:
        raise RuntimeError(f"unclassified orphans: {unclassified}")
    return {
        "requirement_count": len(result.requirements),
        "test_count": len(result.tests),
        "mapping_count": len(result.mappings),
        "untested_count": len(result.untested),
        "orphan_count": len(result.orphans),
        "comment_only_count": len(result.comment_only),
        "requirements": [r.as_dict() for r in result.requirements],
        "tests": [t.as_dict() for t in result.tests],
        "mappings": [m.as_dict() for m in result.mappings],
        "untested_requirements": result.untested,
        "orphan_tests": result.orphans,
        "comment_only": result.comment_only,
    }
