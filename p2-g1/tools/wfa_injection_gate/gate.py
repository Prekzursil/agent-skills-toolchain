"""Neutralise instruction-shaped content in acquired workflow artifacts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROLE_RE = re.compile(r"you are now the system|ignore prior policy", re.I)
IGNORE_RE = re.compile(r"ignore previous instructions", re.I)
B64_RE = re.compile(r"base64\s+-d\s+\|\s*sh|base64\s+-d", re.I)
QUOTE_RE = re.compile(r"`[^`]+`|\"[^\"]+\"")


def is_bundled_agent_config(relpath: str) -> bool:
    posix = relpath.replace("\\", "/")
    if "/.claude/" in f"/{posix}" or posix.startswith(".claude/"):
        return posix.endswith("settings.json") or posix.endswith(".json")
    if "/.codex/" in f"/{posix}" or posix.startswith(".codex/"):
        return posix.endswith("config.toml") or posix.endswith(".toml")
    return False


def mention_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for m in QUOTE_RE.finditer(text):
        blob = m.group(0)
        if ROLE_RE.search(blob) or IGNORE_RE.search(blob) or "base64" in blob.lower():
            spans.append((m.start(), m.end()))
    return spans


def _classes_for(text: str, relpath: str) -> list[str]:
    doc = relpath.lower().endswith((".md", ".rst", ".txt"))
    if doc and mention_spans(text) and not (
        ROLE_RE.search(QUOTE_RE.sub("", text))
        or IGNORE_RE.search(QUOTE_RE.sub("", text))
        or B64_RE.search(QUOTE_RE.sub("", text))
    ):
        return []
    found: list[str] = []
    stripped = QUOTE_RE.sub("", text) if doc else text
    if ROLE_RE.search(stripped):
        found.append("role-spoof")
    if IGNORE_RE.search(stripped):
        found.append("ignore-previous")
    if B64_RE.search(stripped):
        found.append("base64-exec")
    if is_bundled_agent_config(relpath):
        found.append("bundled-agent-config")
    return found


def _neutralise_body(text: str, relpath: str) -> str:
    classes = _classes_for(text, relpath)
    if not classes:
        return text
    if is_bundled_agent_config(relpath):
        return "# NEUTRALISED bundled agent config\n"
    out = text
    out = ROLE_RE.sub("[NEUTRALISED-ROLE-SPOOF]", out)
    out = IGNORE_RE.sub("[NEUTRALISED-IGNORE-PREVIOUS]", out)
    out = B64_RE.sub("[NEUTRALISED-BASE64-EXEC]", out)
    from wfa_injection_gate.corpus import CANARY

    out = out.replace(CANARY, "[NEUTRALISED-CANARY]")
    return out


@dataclass
class NeutraliseResult:
    relpath: str
    classes: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    deleted: bool = False
    neutralised_text: str = ""

    def as_dict(self) -> dict:
        return {
            "relpath": self.relpath,
            "classes": list(self.classes),
            "findings": list(self.findings),
            "deleted": self.deleted,
        }


def neutralise_text(text: str, relpath: str) -> NeutraliseResult:
    classes = _classes_for(text, relpath)
    return NeutraliseResult(
        relpath=relpath,
        classes=classes,
        findings=list(classes),
        deleted=False,
        neutralised_text=_neutralise_body(text, relpath) if classes else text,
    )


def neutralise_tree(src: Path, dest: Path) -> list[NeutraliseResult]:
    src = Path(src)
    dest = Path(dest)
    rows: list[NeutraliseResult] = []
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        result = neutralise_text(text, rel)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.neutralised_text, encoding="utf-8")
        rows.append(result)
    return rows
