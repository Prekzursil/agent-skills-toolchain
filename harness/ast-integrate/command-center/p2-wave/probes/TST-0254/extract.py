"""Extract fenced blocks tagged as a workflow from the product docs tree."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

FENCE_OPEN = re.compile(r"^([ \t]*)```([^\n]*)$")
TOKEN_SPLIT = re.compile(r"[\s,;]+")
NAMED_DOCS = (
    "command-center/RUNBOOK.md",
    "command-center/RELEASE-CHECKLIST.md",
)
OPTIONAL_DOCS = ("README.md",)


def is_workflow_tag(info: str) -> bool:
    tokens = [t.strip().lower().lstrip(".") for t in TOKEN_SPLIT.split(info or "") if t.strip()]
    return "workflow" in tokens


@dataclass
class Fence:
    path: str
    line: int
    info: str
    body: str
    document: dict[str, Any] | None = None
    parse_error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def iter_doc_paths(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        if rel in seen:
            return
        seen.add(rel)
        found.append(path)

    for rel in NAMED_DOCS + OPTIONAL_DOCS:
        add(root / rel)
    cc = root / "command-center"
    if cc.is_dir():
        for path in sorted(cc.glob("*.md")):
            add(path)
    docs = root / "docs"
    if docs.is_dir():
        for path in sorted(docs.rglob("*.md")):
            add(path)
    return found


def extract_markdown(text: str, rel_path: str) -> list[Fence]:
    lines = text.splitlines()
    out: list[Fence] = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        m = FENCE_OPEN.match(raw)
        if not m:
            i += 1
            continue
        info = m.group(2).strip()
        start = i + 1
        i += 1
        body_lines: list[str] = []
        while i < n and not lines[i].lstrip().startswith("```"):
            body_lines.append(lines[i])
            i += 1
        if i < n:
            i += 1
        if not is_workflow_tag(info):
            continue
        body = "\n".join(body_lines)
        fence = Fence(path=rel_path, line=start, info=info, body=body)
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            fence.parse_error = f"JSONDecodeError: {exc}"
            out.append(fence)
            continue
        if not isinstance(parsed, dict):
            fence.parse_error = f"root-not-object:{type(parsed).__name__}"
            out.append(fence)
            continue
        fence.document = parsed
        out.append(fence)
    return out


def independent_tagged_open_count(text: str) -> int:
    """Second counter: fence-open lines whose info tokenizes to include workflow."""
    n = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") and not stripped[3:].lstrip().startswith("```"):
            info = stripped[3:].strip()
            if info and is_workflow_tag(info):
                n += 1
    return n


def extract_path(path: Path, repo: Path | None = None) -> list[Fence]:
    root = repo or REPO
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    return extract_markdown(path.read_text(encoding="utf-8"), rel)


def extract_docs_tree(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    paths = iter_doc_paths(root)
    fences: list[Fence] = []
    independent = 0
    scanned: list[str] = []
    missing_named = [rel for rel in NAMED_DOCS if not (root / rel).is_file()]
    present_named = [rel for rel in NAMED_DOCS if (root / rel).is_file()]
    for path in paths:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        scanned.append(rel)
        text = path.read_text(encoding="utf-8")
        independent += independent_tagged_open_count(text)
        fences.extend(extract_markdown(text, rel))
    return {
        "scanned": scanned,
        "missing_named": missing_named,
        "present_named": present_named,
        "fences": fences,
        "extracted": len(fences),
        "independent_open_count": independent,
        "count_match": independent == len(fences),
    }
