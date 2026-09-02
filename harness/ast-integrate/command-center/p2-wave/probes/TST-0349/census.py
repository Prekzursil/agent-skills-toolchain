#!/usr/bin/env python3
"""AST census: declared subject inside the patched set.

A raw mock count is not a finding. Overlap is. String mentions of patch()
are not patches. Neighbour doubles are not the subject.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SETUP_NAMES = frozenset(
    {
        "setUp",
        "setUpClass",
        "setup_method",
        "setup_class",
        "asyncSetUp",
    }
)
SEVERITY_WEIGHT = {"P0": 100, "P1": 50, "P2": 20, "P3": 10}
CLAIM_WEIGHT = {
    "contract": 40,
    "integration": 25,
    "unit": 10,
    "unknown": 0,
}


@dataclass
class PatchSite:
    target: str
    lineno: int
    form: str


@dataclass
class TestRecord:
    path: str
    name: str
    qualname: str
    lineno: int
    patched: list[str]
    patch_sites: list[dict]
    subject: str | None
    subject_source: str
    overlaps: list[str]
    flagged: bool
    patch_call_count: int
    severity: str
    claimed_coverage: str
    claim_class: str
    score: int
    corpus: str
    unresolved_patch_forms: list[str] = field(default_factory=list)
    conversion: str = ""


def dotted(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def collect_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    aliases[alias.name.split(".")[0]] = alias.name.split(".")[0]
                    aliases[alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                aliases[bound] = f"{node.module}.{alias.name}"
    return aliases


def resolve_name(name: str, aliases: dict[str, str]) -> str:
    parts = name.split(".")
    if not parts:
        return name
    head = parts[0]
    if head in aliases:
        return ".".join([aliases[head], *parts[1:]]) if len(parts) > 1 else aliases[head]
    return name


def classify_call(resolved: str) -> str | None:
    first = resolved.split(".")[0]
    if resolved.endswith(".setattr") and "monkeypatch" in resolved.lower():
        return "setattr"
    if resolved in {"monkeypatch.setattr"}:
        return "setattr"
    if resolved.endswith(".object"):
        base = resolved[: -len(".object")]
        if base == "patch" or base.endswith(".patch"):
            if first in {"patch", "mock", "mocker", "unittest"}:
                return "patch.object"
        return None
    if resolved == "patch" or resolved.endswith(".patch"):
        if first in {"patch", "mock", "mocker", "unittest"}:
            return "patch"
    if resolved.endswith(".dict") and (resolved == "patch.dict" or ".patch.dict" in resolved):
        if first in {"patch", "mock", "mocker", "unittest"}:
            return "patch"
    return None


def first_str_arg(call: ast.Call) -> str | None:
    if call.args:
        arg0 = call.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            return arg0.value
    for kw in call.keywords:
        if kw.arg in {"target", "name"} and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                return kw.value.value
    return None


def object_attr_target(call: ast.Call, aliases: dict[str, str]) -> str | None:
    if not call.args:
        return None
    arg0 = call.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return resolve_name(arg0.value, aliases)
    if len(call.args) < 2:
        return None
    obj = dotted(arg0)
    attr_node = call.args[1]
    if obj is None:
        return None
    if not isinstance(attr_node, ast.Constant) or not isinstance(attr_node.value, str):
        return None
    return f"{resolve_name(obj, aliases)}.{attr_node.value}"


def harvest_calls(
    nodes: Iterable[ast.AST], aliases: dict[str, str]
) -> tuple[list[PatchSite], list[str]]:
    sites: list[PatchSite] = []
    unresolved: list[str] = []
    seen: set[tuple[str, int, str]] = set()
    for root in nodes:
        for sub in ast.walk(root):
            if not isinstance(sub, ast.Call):
                continue
            raw = dotted(sub.func)
            if raw is None:
                continue
            resolved = resolve_name(raw, aliases)
            kind = classify_call(resolved)
            if kind is None:
                continue
            if kind in {"patch.object", "setattr"}:
                target = object_attr_target(sub, aliases)
            else:
                target = first_str_arg(sub)
                if target:
                    target = resolve_name(target, aliases)
            lineno = getattr(sub, "lineno", 0) or 0
            if not target:
                unresolved.append(f"{kind}@{lineno}")
                continue
            key = (target, lineno, kind)
            if key in seen:
                continue
            seen.add(key)
            sites.append(PatchSite(target=target, lineno=lineno, form=kind))
    return sites, unresolved


def iter_tests(tree: ast.Module) -> Iterable[tuple[str, ast.AST, list[ast.AST]]]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                yield node.name, node, []
        elif isinstance(node, ast.ClassDef):
            setups = [
                item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name in SETUP_NAMES
            ]
            extras: list[ast.AST] = list(node.decorator_list) + setups
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not item.name.startswith("test_"):
                    continue
                yield f"{node.name}.{item.name}", item, extras


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def overlap(subject: str, target: str) -> bool:
    s = normalize(subject)
    t = normalize(target)
    if not s or not t:
        return False
    if s == t:
        return True
    if t.startswith(s + ".") or s.startswith(t + "."):
        return True
    return False


def score_row(severity: str, claim_class: str, overlap_n: int) -> int:
    return (
        SEVERITY_WEIGHT.get(severity, 0)
        + CLAIM_WEIGHT.get(claim_class, 0)
        + min(overlap_n, 5)
    )


def conversion_note(flagged: bool) -> str:
    if not flagged:
        return "not-flagged"
    return "convert-to-contract-or-integration; do-not-delete"


def load_subject_index(registry: dict[str, Any], repo: Path) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    rows = registry.get("tests")
    if not isinstance(rows, list):
        rows = registry.get("entries")
    if not isinstance(rows, list):
        return index
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("id") or "")
        rel = normalize(str(row.get("path") or ""))
        if not name:
            continue
        index[(rel, name)] = row
        index[("", name)] = row
        index[(normalize(str((repo / rel).as_posix() if rel else "")), name)] = row
    return index


def lookup_subject(
    index: dict[tuple[str, str], dict], rel: str, name: str, qualname: str
) -> dict | None:
    rel_n = normalize(rel)
    for key in ((rel_n, name), (rel_n, qualname), ("", name), ("", qualname)):
        if key in index:
            return index[key]
    short = qualname.split(".")[-1]
    if ("", short) in index:
        return index[("", short)]
    return None


def scan_file(
    path: Path,
    repo: Path,
    subject_index: dict[tuple[str, str], dict],
    corpus: str,
    subject_source_default: str,
) -> list[TestRecord]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    if not isinstance(tree, ast.Module):
        return []
    aliases = collect_aliases(tree)
    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    out: list[TestRecord] = []
    for qualname, func, extras in iter_tests(tree):
        name = qualname.split(".")[-1]
        sites, unresolved = harvest_calls([func, *extras], aliases)
        patched = sorted({s.target for s in sites})
        meta = lookup_subject(subject_index, rel, name, qualname) or {}
        subject = meta.get("subject") or meta.get("declared_subject")
        subject_s = str(subject) if subject else None
        source = subject_source_default if subject_s else "undeclared"
        if meta and subject_s:
            source = str(meta.get("subject_source") or subject_source_default)
        overlaps = (
            sorted({t for t in patched if overlap(subject_s, t)}) if subject_s else []
        )
        flagged = bool(overlaps)
        severity = str(meta.get("severity") or "P3")
        claim_class = str(meta.get("claim_class") or "unknown")
        coverage = str(meta.get("claimed_coverage") or "")
        rec = TestRecord(
            path=rel,
            name=name,
            qualname=qualname,
            lineno=int(getattr(func, "lineno", 0) or 0),
            patched=patched,
            patch_sites=[asdict(s) for s in sites],
            subject=subject_s,
            subject_source=source,
            overlaps=overlaps,
            flagged=flagged,
            patch_call_count=len(sites),
            severity=severity,
            claimed_coverage=coverage,
            claim_class=claim_class,
            score=score_row(severity, claim_class, len(overlaps)) if flagged else 0,
            corpus=corpus,
            unresolved_patch_forms=unresolved,
            conversion=conversion_note(flagged),
        )
        out.append(rec)
    return out


def python_tests_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name in {"conftest.py"}:
            files.append(path)
            continue
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            files.append(path)
    return files


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def live_registry_inventory(registry: dict[str, Any] | None) -> dict[str, Any]:
    """Describe the live TEST-REGISTRY.json shape without inventing subjects.

    The catalog input is 'the declared subject of each test from the registry'.
    The live file is a suite/invariant ledger: it names tests and what they
    protect, but it does not declare a patchable object path per test. Overlap
    flags require that object path. Counting named tests is not a subject.
    """
    if not isinstance(registry, dict):
        return {
            "shape": "absent-or-unreadable",
            "named_test_ids": [],
            "named_test_count": 0,
            "object_subject_rows": 0,
            "suite_count": 0,
            "invariant_count": 0,
            "keys": [],
        }
    named: list[str] = []
    object_subject_rows = 0
    rows = registry.get("tests")
    if not isinstance(rows, list):
        rows = registry.get("entries")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("id") or "")
            if name:
                named.append(name)
            subj = row.get("subject") or row.get("declared_subject")
            if isinstance(subj, str) and subj.strip():
                object_subject_rows += 1
    for inv in registry.get("invariants") or []:
        if not isinstance(inv, dict):
            continue
        for item in inv.get("tests") or []:
            if isinstance(item, str) and item:
                named.append(item)
    suites = registry.get("suites") if isinstance(registry.get("suites"), list) else []
    if object_subject_rows:
        shape = "per-test-subject-rows"
    elif suites or registry.get("invariants"):
        shape = "suite-invariant-ledger"
    else:
        shape = "unknown"
    unique = sorted(set(named))
    return {
        "shape": shape,
        "named_test_ids": unique,
        "named_test_count": len(unique),
        "object_subject_rows": object_subject_rows,
        "suite_count": len(suites),
        "invariant_count": (
            len(registry.get("invariants") or [])
            if isinstance(registry.get("invariants"), list)
            else 0
        ),
        "keys": sorted(str(k) for k in registry.keys()),
    }


def run_census(
    repo: Path,
    planted_registry: Path,
    planted_tests: Path,
    live_registry: Path,
    live_roots: list[Path],
) -> dict[str, Any]:
    planted_doc = load_json(planted_registry)
    planted_index = load_subject_index(planted_doc, repo)
    live_present = live_registry.is_file()
    live_index: dict[tuple[str, str], dict] = {}
    live_registry_error = None
    live_doc: dict[str, Any] | None = None
    if live_present:
        try:
            loaded = load_json(live_registry)
            if isinstance(loaded, dict):
                live_doc = loaded
                live_index = load_subject_index(loaded, repo)
            else:
                live_registry_error = "not-an-object"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            live_registry_error = type(exc).__name__
    inventory = live_registry_inventory(live_doc)

    planted_rows: list[TestRecord] = []
    for path in python_tests_under(planted_tests):
        planted_rows.extend(
            scan_file(
                path,
                repo,
                planted_index,
                corpus="planted",
                subject_source_default="planted-registry",
            )
        )

    live_rows: list[TestRecord] = []
    walked: list[str] = []
    for root in live_roots:
        try:
            rel = root.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = str(root)
        walked.append(rel)
        if not root.is_dir():
            continue
        for path in python_tests_under(root):
            live_rows.extend(
                scan_file(
                    path,
                    repo,
                    live_index,
                    corpus="live",
                    subject_source_default="live-registry" if live_present else "undeclared",
                )
            )

    flagged_planted = [r for r in planted_rows if r.flagged]
    flagged_live = [r for r in live_rows if r.flagged]
    prioritized = sorted(
        flagged_planted + flagged_live,
        key=lambda r: (-r.score, r.path, r.qualname),
    )
    return {
        "live_registry_present": live_present,
        "live_registry_error": live_registry_error,
        "live_subject_rows": inventory["object_subject_rows"],
        "live_registry_inventory": inventory,
        "live_roots_walked": walked,
        "planted": [asdict(r) for r in planted_rows],
        "live": [asdict(r) for r in live_rows],
        "flagged_planted": [asdict(r) for r in flagged_planted],
        "flagged_live": [asdict(r) for r in flagged_live],
        "prioritized": [asdict(r) for r in prioritized],
        "counts": {
            "planted_tests": len(planted_rows),
            "live_tests": len(live_rows),
            "planted_flagged": len(flagged_planted),
            "live_flagged": len(flagged_live),
            "live_undeclared_subject": sum(
                1 for r in live_rows if r.subject is None
            ),
            "live_with_patches": sum(1 for r in live_rows if r.patch_call_count),
        },
    }


def record_by_name(rows: list[dict], name: str) -> dict | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None
