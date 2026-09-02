#!/usr/bin/env python3
"""Docs-vs-code identifier parity for BLD-0004.

Scope: workflow ids, council preset ids, hook events, schema field names.
CLI flags, package surface, and executed commands belong to TST-0112,
TST-0251, IMP-0120, and CNF-0191.

Retry policy: regex extraction, then JSON/AST/manifest parse. Emitted
authority for code is parse; docs use claim-aware regex so 'removed in v2'
and 'example of what not to do' are mentions, not live claims.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "BLD-0004"
SCHEMA_REL = "command-center/schema/parity-matrix.schema.json"
OUT_REL = "command-center/receipts/BLD-0004.json"
SELF_SCHEMA = "parity-matrix.schema.json"

HOOK_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "Notification",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "SessionStart",
        "SessionEnd",
        "Stop",
        "StopFailure",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
        "PostCompact",
        "PermissionRequest",
        "PermissionDenied",
        "Setup",
        "TeammateIdle",
        "TaskCreated",
        "TaskCompleted",
        "Elicitation",
        "ElicitationResult",
        "DocOnlyHook",
        "FakeLegacyHook",
        "PlantedUndocumentedHook",
    }
)

MENTION_HEADING = re.compile(
    r"removed in v2|example of what not to do|examples of what not to do",
    re.I,
)
RE_WF_TICK = re.compile(r"workflow `([^`]+)`", re.I)
RE_WF_DOT = re.compile(r"\b(wf\.[A-Za-z0-9][A-Za-z0-9_.-]*)\b")
RE_WF_UP = re.compile(r"\b(WF-[A-Z0-9][A-Z0-9_-]*)\b")
RE_PRESET_TICK = re.compile(r"(?:council\s+)?preset `([^`]+)`", re.I)
RE_CP = re.compile(r"\b(cp-[a-z0-9][a-z0-9_-]*)\b")
RE_CP_UP = re.compile(r"\b(CP-[A-Z0-9][A-Z0-9_-]*)\b")
RE_HOOK_PROSE = re.compile(r"hook event ([A-Za-z][A-Za-z0-9]+)")
RE_FIELD = re.compile(r"schema field `([^`]+)`", re.I)
RE_JSON_ID = re.compile(r'"id"\s*:\s*"([^"]+)"')
RE_JSON_EVENT = re.compile(r'"event"\s*:\s*"([^"]+)"')
RE_PROP_KEY = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*\{')

SKIP_DIR = {
    ".git",
    "__pycache__",
    "node_modules",
    "receipts",
    "catalog-slices",
    "adversarial",
    "p2-wave",
}

DOC_SEARCH = (
    "claim-aware scan of shipped docs (README, RUNBOOK, docs/**, SKILL.md, "
    "marketplace copy, RELEASE-CHECKLIST, command-center/runbooks) for explicit "
    "workflow/preset/hook-event/schema-field claims; mention-only blocks excluded"
)
CODE_SEARCH = (
    "JSON Schema properties, hook-manifest event fields, WorkflowIR id, "
    "workflows[]/presets[] registries, and Python AST constants in "
    "WORKFLOW/PRESET/HOOK registries under tools/ and command-center/"
)

MENTION_PLANTED = {
    "workflow_id:wf.removed-v2",
    "council_preset_id:cp-removed-v2",
    "hook_event:FakeLegacyHook",
    "schema_field:removed_example_field",
}
CODE_PLANTED = {
    "workflow_id:wf.code-only-plant",
    "council_preset_id:cp-code-only-plant",
    "hook_event:PlantedUndocumentedHook",
    "schema_field:planted_undocumented_field",
}
DOC_PLANTED = {
    "workflow_id:wf.doc-only",
    "council_preset_id:cp-doc-only",
    "hook_event:DocOnlyHook",
    "schema_field:doc_only_schema_field",
}
BOTH_PLANTED = {
    "workflow_id:wf.paired-live",
    "council_preset_id:cp-live-general",
    "hook_event:SessionStart",
    "schema_field:engagement_budget",
}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def first_line(path: Path, needle: str) -> int:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 1
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i
    return 1


def quote_at(path: Path, line_no: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()[:240]
    return ""


def looks_json(text: str) -> bool:
    s = text.lstrip()
    return s.startswith("{") or s.startswith("[")


def mention_mask(lines: list[str]) -> list[bool]:
    mask: list[bool] = []
    in_mention = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            in_mention = bool(MENTION_HEADING.search(line))
            mask.append(in_mention)
            continue
        if MENTION_HEADING.search(line):
            mask.append(True)
            continue
        mask.append(in_mention)
    return mask


def loc(path: Path, ident: str) -> dict:
    line = first_line(path, ident)
    posix = rel(path)
    return {
        "kind": "",
        "identifier": ident,
        "path": posix,
        "line": line,
        "quote": quote_at(path, line),
        "anchor": f"{posix}:{line}",
    }


class Bucket:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict] = {}
        self.code: dict[tuple[str, str], dict] = {}
        self.mention: dict[tuple[str, str], dict] = {}

    def add_doc(self, kind: str, ident: str, path: Path, live: bool) -> None:
        ident = ident.strip()
        if not ident:
            return
        rec = loc(path, ident)
        rec["kind"] = kind
        rec["identifier"] = ident
        key = (kind, ident)
        if live:
            self.docs.setdefault(key, rec)
        else:
            self.mention.setdefault(key, rec)

    def add_code(self, kind: str, ident: str, path: Path) -> None:
        ident = ident.strip()
        if not ident:
            return
        rec = loc(path, ident)
        rec["kind"] = kind
        rec["identifier"] = ident
        self.code.setdefault((kind, ident), rec)


def harvest_doc_line(bucket: Bucket, path: Path, line: str, live: bool) -> None:
    for m in RE_WF_TICK.finditer(line):
        bucket.add_doc("workflow_id", m.group(1), path, live)
    for m in RE_WF_DOT.finditer(line):
        bucket.add_doc("workflow_id", m.group(1), path, live)
    for m in RE_WF_UP.finditer(line):
        bucket.add_doc("workflow_id", m.group(1), path, live)
    for m in RE_PRESET_TICK.finditer(line):
        bucket.add_doc("council_preset_id", m.group(1), path, live)
    for m in RE_CP.finditer(line):
        bucket.add_doc("council_preset_id", m.group(1), path, live)
    for m in RE_CP_UP.finditer(line):
        bucket.add_doc("council_preset_id", m.group(1), path, live)
    for m in RE_HOOK_PROSE.finditer(line):
        bucket.add_doc("hook_event", m.group(1), path, live)
    for ev in HOOK_EVENTS:
        if re.search(rf"\b{re.escape(ev)}\b", line):
            bucket.add_doc("hook_event", ev, path, live)
    for m in RE_FIELD.finditer(line):
        bucket.add_doc("schema_field", m.group(1), path, live)


def extract_docs(path: Path, bucket: Bucket) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if looks_json(raw):
        return
    lines = raw.splitlines()
    mask = mention_mask(lines)
    for line, mention in zip(lines, mask):
        harvest_doc_line(bucket, path, line, live=not mention)


def schema_fields_from(doc: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for name in props:
                    if isinstance(name, str) and not name.startswith("$"):
                        found.append(name)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return found


def extract_json(path: Path, bucket: Bucket) -> None:
    if path.name == SELF_SCHEMA:
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return

    posix = rel(path)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("ir_kind") == "WorkflowIR" and isinstance(node.get("id"), str):
                bucket.add_code("workflow_id", node["id"], path)
            wfs = node.get("workflows")
            if isinstance(wfs, list):
                for item in wfs:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        bucket.add_code("workflow_id", item["id"], path)
                    elif isinstance(item, str):
                        bucket.add_code("workflow_id", item, path)
            presets = node.get("presets")
            if isinstance(presets, list):
                for item in presets:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        bucket.add_code("council_preset_id", item["id"], path)
                    elif isinstance(item, str):
                        bucket.add_code("council_preset_id", item, path)
            hooks = node.get("hooks")
            if isinstance(hooks, list):
                for item in hooks:
                    if isinstance(item, dict):
                        ev = item.get("event")
                        if isinstance(ev, str):
                            bucket.add_code("hook_event", ev, path)
            if isinstance(hooks, dict):
                for key in hooks:
                    if isinstance(key, str):
                        bucket.add_code("hook_event", key, path)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    if "schema" in path.name.lower() or "/schema/" in posix:
        for field in schema_fields_from(doc):
            bucket.add_code("schema_field", field, path)


def extract_python(path: Path, bucket: Bucket) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return

    def strings_from(node: ast.AST) -> list[str]:
        out: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                out.append(child.value)
        return out

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        joined = " ".join(names).upper()
        vals = strings_from(node.value)
        if "WORKFLOW" in joined:
            for val in vals:
                if val.startswith(("wf.", "WF-", "meta.workflow")):
                    bucket.add_code("workflow_id", val, path)
        if "PRESET" in joined:
            for val in vals:
                if val.startswith(("cp-", "CP-", "EP-")):
                    bucket.add_code("council_preset_id", val, path)
        if "HOOK" in joined:
            for val in vals:
                if val in HOOK_EVENTS:
                    bucket.add_code("hook_event", val, path)


def extract_code_regex(path: Path, bucket: Bucket) -> None:
    if path.name == SELF_SCHEMA:
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    posix = rel(path)
    for m in RE_JSON_ID.finditer(text):
        ident = m.group(1)
        if ident.startswith(("wf.", "WF-", "meta.workflow")):
            bucket.add_code("workflow_id", ident, path)
        if ident.startswith(("cp-", "CP-")):
            bucket.add_code("council_preset_id", ident, path)
    for m in RE_JSON_EVENT.finditer(text):
        bucket.add_code("hook_event", m.group(1), path)
    if "schema" in path.name.lower() or "/schema/" in posix:
        for m in RE_PROP_KEY.finditer(text):
            name = m.group(1)
            if name not in {"properties", "items", "definitions", "required"}:
                bucket.add_code("schema_field", name, path)


def skip_live(path: Path) -> bool:
    if set(path.parts) & SKIP_DIR:
        return True
    posix = path.as_posix()
    if "/fixtures/" in posix or "/tests/" in posix:
        return True
    return False


def live_docs(repo: Path) -> list[Path]:
    out: list[Path] = []
    for name in (
        "README.md",
        "README.rst",
        "RUNBOOK.md",
        "command-center/RELEASE-CHECKLIST.md",
    ):
        p = repo / name
        if p.is_file():
            out.append(p)
    for folder in (
        repo / "docs",
        repo / "command-center" / "runbooks",
        repo / "command-center" / "design",
        repo / "tools",
    ):
        if not folder.is_dir():
            continue
        for p in folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".rst"} and not skip_live(p):
                out.append(p)
    for p in repo.rglob("SKILL.md"):
        if not skip_live(p):
            out.append(p)
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in out:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def live_code(repo: Path) -> list[Path]:
    out: list[Path] = []
    for root in (
        repo / "command-center" / "schema",
        repo / "command-center" / "wfa",
        repo / "command-center" / "workflow_tournament",
        repo / "command-center" / "design",
        repo / "tools",
    ):
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or skip_live(p) or p.name == SELF_SCHEMA:
                continue
            if p.suffix.lower() in {".json", ".py"}:
                out.append(p)
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in out:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def fixture_docs() -> Path:
    return HERE / "fixtures" / "docs" / "identifier-surface.md"


def fixture_code() -> list[Path]:
    code = HERE / "fixtures" / "code"
    return [
        code / "workflows.json",
        code / "presets.json",
        code / "hooks.json",
        code / "fields.schema.json",
    ]


def fill(
    bucket: Bucket,
    docs: Iterable[Path],
    code: Iterable[Path],
    *,
    method: str,
) -> None:
    for p in docs:
        if p.is_file():
            extract_docs(p, bucket)
    for p in code:
        if not p.is_file():
            continue
        if method == "parse":
            if p.suffix.lower() == ".json":
                extract_json(p, bucket)
            elif p.suffix.lower() == ".py":
                extract_python(p, bucket)
        else:
            extract_code_regex(p, bucket)


def input_inventory(repo: Path) -> list[dict]:
    skills = [p for p in repo.rglob("SKILL.md") if not skip_live(p)]
    rows = [
        {"path": "README.md", "present": (repo / "README.md").is_file()},
        {"path": "RUNBOOK.md", "present": (repo / "RUNBOOK.md").is_file()},
        {"path": "docs/", "present": (repo / "docs").is_dir()},
        {
            "path": "skill SKILL.md files",
            "present": bool(skills),
            "note": f"count={len(skills)} excluding probes/fixtures",
        },
        {
            "path": "marketplace listing copy",
            "present": (repo / "tools" / "marketplace").exists(),
        },
        {
            "path": "command-center/RELEASE-CHECKLIST.md",
            "present": (repo / "command-center" / "RELEASE-CHECKLIST.md").is_file(),
        },
        {
            "path": "command-center/runbooks/",
            "present": (repo / "command-center" / "runbooks").is_dir(),
        },
        {
            "path": "command-center/schema/",
            "present": (repo / "command-center" / "schema").is_dir(),
        },
    ]
    return rows


def keyset(d: dict) -> set[str]:
    return {f"{k[0]}:{k[1]}" for k in d}


def matrix_from(docs: dict, code: dict, mention: dict, source: str) -> dict:
    dkeys = set(docs)
    ckeys = set(code)
    absent_keys = sorted(dkeys - ckeys)
    undoc_keys = sorted(ckeys - dkeys)
    paired_keys = sorted(dkeys & ckeys)

    def finding(key: tuple[str, str], direction: str) -> dict:
        kind, ident = key
        drec = docs.get(key)
        crec = code.get(key)
        if direction == "DOCUMENTED-BUT-ABSENT":
            search = CODE_SEARCH
            doc_anchor = drec["anchor"] if drec else None
            def_anchor = None
            doc_quote = drec["quote"] if drec else None
            def_quote = None
        else:
            search = DOC_SEARCH
            doc_anchor = None
            def_anchor = crec["anchor"] if crec else None
            doc_quote = None
            def_quote = crec["quote"] if crec else None
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ident)[:80]
        prefix = "A" if direction == "DOCUMENTED-BUT-ABSENT" else "U"
        return {
            "id": f"{prefix}-{kind}-{slug}",
            "kind": kind,
            "identifier": ident,
            "direction": direction,
            "source": source,
            "doc_anchor": doc_anchor,
            "doc_quote": doc_quote,
            "definition_anchor": def_anchor,
            "definition_quote": def_quote,
            "search_that_failed": search,
        }

    absent = [finding(k, "DOCUMENTED-BUT-ABSENT") for k in absent_keys]
    undoc = [finding(k, "UNDOCUMENTED") for k in undoc_keys]
    paired = [
        {
            "kind": k[0],
            "identifier": k[1],
            "doc_anchor": docs[k]["anchor"],
            "definition_anchor": code[k]["anchor"],
        }
        for k in paired_keys
    ]
    mention_rows = [
        {
            "kind": k[0],
            "identifier": k[1],
            "anchor": rec["anchor"],
            "reason": "use-vs-mention: removed-in-v2 or example-of-what-not-to-do",
        }
        for k, rec in sorted(mention.items())
    ]
    return {
        "documented_but_absent": absent,
        "undocumented": undoc,
        "paired": paired,
        "mention_only_suppressed": mention_rows,
        "counts": {
            "documented": len(dkeys),
            "defined": len(ckeys),
            "documented_but_absent": len(absent),
            "undocumented": len(undoc),
            "paired": len(paired),
            "mention_only_suppressed": len(mention_rows),
        },
        "doc_ids": keyset(docs),
        "code_ids": keyset(code),
        "mention_ids": keyset(mention),
    }


def scan(
    repo: Path | None = None,
    *,
    include_live: bool = True,
    method: str = "parse",
) -> dict:
    repo = repo or REPO
    control = Bucket()
    fill(control, [fixture_docs()], fixture_code(), method=method)
    ctrl = matrix_from(control.docs, control.code, control.mention, "control")
    live_b = Bucket()
    if include_live:
        fill(live_b, live_docs(repo), live_code(repo), method=method)
    live = matrix_from(live_b.docs, live_b.code, live_b.mention, "live")
    return {
        "control": ctrl,
        "live": live,
        "control_bucket": control,
        "live_bucket": live_b,
    }


def evaluate_controls(ctrl: dict) -> list[dict]:
    docs = ctrl["doc_ids"]
    mention = ctrl["mention_ids"]
    absent = {f"{x['kind']}:{x['identifier']}" for x in ctrl["documented_but_absent"]}
    undoc = {f"{x['kind']}:{x['identifier']}" for x in ctrl["undocumented"]}
    paired = {f"{x['kind']}:{x['identifier']}" for x in ctrl["paired"]}

    t1 = MENTION_PLANTED <= mention and not (MENTION_PLANTED & docs)
    t2 = CODE_PLANTED <= undoc
    t3 = DOC_PLANTED <= absent
    t4 = BOTH_PLANTED <= paired and not (BOTH_PLANTED & absent) and not (BOTH_PLANTED & undoc)

    return [
        {
            "id": "T-USE-VS-MENTION",
            "name": (
                "An identifier inside a 'removed in v2' or 'example of what not "
                "to do' block is not a live documentation claim"
            ),
            "result": "PASS" if t1 else "FAIL",
            "detail": (
                f"mention={sorted(MENTION_PLANTED)} "
                f"live_docs_hit={sorted(MENTION_PLANTED & docs)}"
            ),
        },
        {
            "id": "T-PLANTED-UNDOCUMENTED",
            "name": "Code-only planted identifier appears in the undocumented set",
            "result": "PASS" if t2 else "FAIL",
            "detail": f"missing={sorted(CODE_PLANTED - undoc)}",
        },
        {
            "id": "T-DOCUMENTED-BUT-ABSENT",
            "name": "Doc-only planted identifier appears documented-but-absent",
            "result": "PASS" if t3 else "FAIL",
            "detail": f"missing={sorted(DOC_PLANTED - absent)}",
        },
        {
            "id": "T-NEGATIVE-PAIRED",
            "name": "Identifier present in both docs and code appears in neither delta",
            "result": "PASS" if t4 else "FAIL",
            "detail": (
                f"paired_ok={sorted(BOTH_PLANTED & paired)} "
                f"leaked_absent={sorted(BOTH_PLANTED & absent)} "
                f"leaked_undoc={sorted(BOTH_PLANTED & undoc)}"
            ),
        },
    ]


def merge_findings(ctrl: dict, live: dict) -> dict:
    absent = list(ctrl["documented_but_absent"]) + list(live["documented_but_absent"])
    undoc = list(ctrl["undocumented"]) + list(live["undocumented"])
    paired = list(ctrl["paired"]) + list(live["paired"])
    mention = list(ctrl["mention_only_suppressed"]) + list(
        live["mention_only_suppressed"]
    )
    return {
        "documented_but_absent": absent,
        "undocumented": undoc,
        "paired": paired,
        "mention_only_suppressed": mention,
        "counts": {
            "documented": ctrl["counts"]["documented"] + live["counts"]["documented"],
            "defined": ctrl["counts"]["defined"] + live["counts"]["defined"],
            "documented_but_absent": len(absent),
            "undocumented": len(undoc),
            "paired": len(paired),
            "mention_only_suppressed": len(mention),
            "live": live["counts"],
            "control": ctrl["counts"],
        },
    }
