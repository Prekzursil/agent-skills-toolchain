"""Path-set casefold collisions and case-insensitive zip extract (IMP-0022)."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

try:
    from .pathnorm import nfc_casefold, normalised_payload_path
except ImportError:  # imported as a loose module (IMP-0009 sys.path insert)
    from pathnorm import nfc_casefold, normalised_payload_path


class CaseCollisionError(ValueError):
    """Emitter refused to serialize a case-colliding mapping."""


@dataclass
class Collision:
    key: str
    paths: list[str]


def find_casefold_collisions(paths: Iterable[str]) -> list[Collision]:
    groups: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for raw in paths:
        original = str(raw).replace("\\", "/")
        if original in seen:
            continue
        seen.add(original)
        groups[normalised_payload_path(original)].append(original)
    return [Collision(key, members) for key, members in sorted(groups.items()) if len(members) > 1]


def _resolve(directory: Path, name: str) -> str:
    want = nfc_casefold(name)
    if directory.is_dir():
        for existing in os.listdir(directory):
            if nfc_casefold(existing) == want:
                return existing
    return name


def extract_zip_case_insensitive(zf: ZipFile, dest: Path) -> int:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p]
        current = dest
        for i, part in enumerate(parts):
            actual = _resolve(current, part)
            target = current / actual
            if i == len(parts) - 1:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(target, "wb") as out:
                    out.write(src.read())
            else:
                target.mkdir(parents=True, exist_ok=True)
                current = target
    n = 0
    for _dirpath, _dirnames, filenames in os.walk(dest):
        n += len(filenames)
    return n


def both_signals(members: dict[str, bytes]) -> dict:
    import io
    import zipfile

    paths = list(members)
    set_hits = find_casefold_collisions(paths)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    entries = [n for n in zipfile.ZipFile(io.BytesIO(buf.getvalue())).namelist() if n and not n.endswith("/")]
    import tempfile

    with tempfile.TemporaryDirectory(prefix="case-coll-") as tmp:
        extracted = extract_zip_case_insensitive(
            zipfile.ZipFile(io.BytesIO(buf.getvalue())), Path(tmp)
        )
    shortfall = len(entries) - extracted
    return {
        "set_fired": bool(set_hits),
        "extract_fired": shortfall > 0,
        "shortfall": shortfall,
        "set_count": len(set_hits),
    }


def independent_signal(paths: Iterable[str]) -> list[tuple[str, list[str]]]:
    return find_casefold_collisions(paths)


KIND_CASE = "case-distinct"
KIND_DUP = "duplicate-key"
DEFAULT_TARGETS = (
    "tools/plugin/tests/fixtures/clean-manifest.json",
    "tools/plugin/tests/fixtures/name-collision.json",
    "tools/plugin/tests/fixtures/duplicate-keys.json",
    "tools/plugin/tests/fixtures/nested-collision.json",
    "tools/plugin/tests/fixtures/non-colliding-siblings.json",
)


def _pairs_hook(pairs: list[tuple[str, object]]) -> list[tuple[str, object]]:
    return list(pairs)


def _is_pairs(node: object) -> bool:
    return (
        isinstance(node, list)
        and bool(node)
        and isinstance(node[0], (list, tuple))
        and len(node[0]) == 2
        and isinstance(node[0][0], str)
    )


def _walk_pairs(node: object, loc: str, findings: list[dict]) -> None:
    if _is_pairs(node):
        seen_exact: dict[str, object] = {}
        seen_fold: dict[str, str] = {}
        for key, value in node:  # type: ignore[union-attr]
            if key in seen_exact:
                findings.append({"kind": KIND_DUP, "keys": [key, key], "path": loc})
            seen_exact[key] = value
            folded = key.casefold()
            prev = seen_fold.get(folded)
            if prev is not None and prev != key:
                findings.append({"kind": KIND_CASE, "keys": [prev, key], "path": loc})
            else:
                seen_fold[folded] = key
            _walk_pairs(value, f"{loc}.{key}", findings)
        return
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk_pairs(item, f"{loc}[{i}]", findings)


def lint_file(path: str | Path) -> dict:
    target = Path(path)
    row: dict = {
        "path": str(target).replace("\\", "/"),
        "parse_ok": False,
        "findings": [],
    }
    if not target.is_file():
        row["error"] = "missing"
        return row
    text = target.read_text(encoding="utf-8")
    try:
        tree = json.loads(text, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as exc:
        row["error"] = str(exc)
        return row
    findings: list[dict] = []
    _walk_pairs(tree, "$", findings)
    row["parse_ok"] = True
    row["findings"] = findings
    return row


def lint_text(text: str) -> dict:
    try:
        tree = json.loads(text, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as exc:
        return {"parse_ok": False, "error": str(exc), "findings": []}
    findings: list[dict] = []
    _walk_pairs(tree, "$", findings)
    return {"parse_ok": True, "findings": findings}


def iter_document_keysets(text: str) -> list[str]:
    keys: list[str] = []

    def walk(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                keys.append(str(k) if prefix == "$" else f"{prefix}.{k}")
                walk(v, f"{prefix}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{prefix}[{i}]")

    try:
        tree = json.loads(text, object_pairs_hook=lambda pairs: dict(pairs))
    except json.JSONDecodeError:
        return keys
    walk(tree, "$")
    # also collect raw object keys only (collision is on sibling keys)
    def walk_keys(node: object) -> None:
        if isinstance(node, dict):
            keys.extend(str(k) for k in node.keys())
            for v in node.values():
                walk_keys(v)
        elif isinstance(node, list):
            for v in node:
                walk_keys(v)

    walk_keys(tree)
    return keys


class _DocResult:
    def __init__(self, accepted: bool, reason: str) -> None:
        self.accepted = accepted
        self.reason = reason


def validate_document(text: str) -> _DocResult:
    keys = iter_document_keysets(text)
    # sibling casefold collisions on object keys
    hits = find_casefold_collisions([k for k in keys if "." not in k or True])
    # Prefer object-key collisions from lint_text
    lint = lint_text(text)
    fired = bool(lint.get("findings"))
    if not lint.get("parse_ok"):
        return _DocResult(False, lint.get("error") or "parse")
    if fired:
        return _DocResult(False, "casefold-collision")
    return _DocResult(True, "ok")


__all__ = [
    "CaseCollisionError",
    "DEFAULT_TARGETS",
    "KIND_CASE",
    "KIND_DUP",
    "find_casefold_collisions",
    "extract_zip_case_insensitive",
    "both_signals",
    "independent_signal",
    "iter_document_keysets",
    "validate_document",
    "lint_file",
    "lint_text",
    "nfc_casefold",
]
