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


def _scalar(raw: str) -> object:
    """Unquote a YAML scalar; ``[]`` / ``[a, b]`` flow sequences become lists."""
    val = raw.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_scalar(item) for item in inner.split(",")]
    return val.strip('"').strip("'")


def _parse_yaml_mapping(block: str) -> dict[str, object]:
    """Indentation-aware parse of the frontmatter mapping.

    Only column-0 keys land in the returned mapping; an indented ``key:`` line
    is stored under its parent (so a ``paths:`` nested inside ``meta:`` is
    ``fm["meta"]["paths"]``, never ``fm["paths"]``).  ``- item`` lines attach to
    the nearest open key at the same or lower indentation.  Comments and blank
    lines are ignored; malformed lines are skipped rather than raising.
    """
    root: dict[str, object] = {}
    # (indent, key, parent-mapping) for every key still open above the cursor.
    stack: list[tuple[int, str, dict[str, object]]] = []
    for line in (block or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if stripped.startswith("- "):
            while stack and stack[-1][0] > indent:
                stack.pop()
            if not stack:
                continue
            _ind, key, parent = stack[-1]
            existing = parent.get(key)
            if existing is None:
                parent[key] = existing = []
            if isinstance(existing, list):
                existing.append(_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, val = stripped.split(":", 1)
        key = key.strip()
        val = val.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            parent = root
        else:
            _ind, pkey, pparent = stack[-1]
            child = pparent.get(pkey)
            if child is None:
                pparent[pkey] = child = {}
            if not isinstance(child, dict):
                continue  # scalar/list parent cannot hold a nested key
            parent = child
        parent[key] = None if val == "" else _scalar(val)
        stack.append((indent, key, parent))
    # A key opened with no value and never filled is an empty list (``paths:``).
    def _finalise(mapping: dict[str, object]) -> None:
        for k, v in list(mapping.items()):
            if v is None:
                mapping[k] = []
            elif isinstance(v, dict):
                _finalise(v)

    _finalise(root)
    return root


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
