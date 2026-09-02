"""Rule load-mode resolver: ALWAYS-ON unless paths globstar frontmatter. IMP-0387."""
from __future__ import annotations

from pathlib import Path

ALWAYS_ON = "ALWAYS-ON"
LAZY = "LAZY"


def extract_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (yaml-block, body). Absence of a frontmatter fence is (None, text)."""
    if not text.startswith("---"):
        return None, text
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return None, text
    block = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return block, body


def _parse_yaml_mapping(block: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current: str | None = None
    for line in (block or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current:
            data.setdefault(current, [])
            if isinstance(data[current], list):
                data[current].append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            current = key.strip()
            val = val.strip()
            data[current] = [] if val == "" else val.strip('"').strip("'")
    return data


def _frontmatter(text: str) -> dict[str, object]:
    block, _body = extract_frontmatter(text)
    if block is None:
        return {}
    return _parse_yaml_mapping(block)


def resolve_load_mode(text: str) -> str:
    fm = _frontmatter(text)
    if "paths" in fm:
        return LAZY
    return ALWAYS_ON


def iter_rule_files(root: Path):
    root = Path(root)
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.suffix in {".md", ".mdc", ".txt"} and path.is_file():
            yield path


def resolve_file(path: Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    return {
        "path": str(path),
        "load_mode": resolve_load_mode(text),
        "has_frontmatter": text.startswith("---"),
    }
