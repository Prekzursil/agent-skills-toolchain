"""Static malicious-plugin review: permissions vs class allowlist, auto-load hooks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
AUTOLOAD_MARKERS = (".claude/hooks/", ".codex/hooks/")
PROSE_NAMES = {"README.md", "SKILL.md"}


def _allowlists() -> dict[str, list[str]]:
    path = HERE / "class_allowlists.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def review_package(package: Path | str) -> dict[str, Any]:
    root = Path(package)
    findings: list[dict[str, Any]] = []
    manifest = root / "plugin.json"
    cls = "skill"
    perms: list[str] = []
    if manifest.is_file():
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        cls = str(doc.get("class") or "skill")
        raw = doc.get("tool_permissions") or []
        perms = [str(p) for p in raw]
    allowed = set(_allowlists().get(cls) or [])
    extra = [p for p in perms if p not in allowed]
    if extra:
        findings.append(
            {
                "rule_id": "EXCESSIVE_PERMISSION",
                "path": "plugin.json",
                "extra": extra,
            }
        )
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = _rel(root, path)
            if path.name in PROSE_NAMES:
                continue
            if any(rel.startswith(m) or f"/{m}" in f"/{rel}" for m in AUTOLOAD_MARKERS):
                findings.append(
                    {
                        "rule_id": "AUTO_LOADING_AGENT_CONFIG",
                        "path": rel,
                    }
                )
    rule_ids = sorted({str(f.get("rule_id")) for f in findings})
    flagged = bool(findings)
    return {
        "verdict": "FLAG" if flagged else "CLEAN",
        "flagged": flagged,
        "findings": findings,
        "rule_ids": rule_ids,
        "class": cls,
        "permissions": perms,
    }
