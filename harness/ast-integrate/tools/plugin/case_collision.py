"""Casefold collisions: path sets + case-insensitive zip extract (IMP-0022), JSON key
linting (IMP-0009), and JSON documents whose sibling keys collide under a
case-insensitive parser (TST-0180: validator REJECT, independent key-set-size signal,
emitter refusal)."""
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


# --- TST-0180: JSON documents whose keys collide under a case-insensitive parser ---


@dataclass
class KeySet:
    """The raw sibling keys of one JSON object, plus their casefolded projection."""

    path: str
    raw_keys: list[str]

    @property
    def unique_raw_size(self) -> int:
        return len(set(self.raw_keys))

    @property
    def casefolded_size(self) -> int:
        return len({k.casefold() for k in self.raw_keys})

    @property
    def collides(self) -> bool:
        return self.unique_raw_size > self.casefolded_size

    def colliding_groups(self) -> list[list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for key in self.raw_keys:
            if key not in groups[key.casefold()]:
                groups[key.casefold()].append(key)
        return [members for _fold, members in sorted(groups.items()) if len(members) > 1]


def _walk_keysets(node: object, loc: str, out: list[KeySet]) -> None:
    if _is_pairs(node):
        out.append(KeySet(path=loc, raw_keys=[str(k) for k, _v in node]))  # type: ignore[union-attr]
        for key, value in node:  # type: ignore[union-attr]
            _walk_keysets(value, f"{loc}.{key}", out)
        return
    if isinstance(node, list) and not _is_pairs(node):
        for i, item in enumerate(node):
            _walk_keysets(item, f"{loc}[{i}]", out)


def iter_document_keysets(text: str) -> list[KeySet]:
    """One :class:`KeySet` per JSON object in document order; ``[]`` when unparseable.

    Parsed with ``object_pairs_hook`` so exact duplicates survive to the key bag.
    An empty object still yields a (size-0) key set so callers see every object.
    """
    try:
        tree = json.loads(text, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError:
        return []
    out: list[KeySet] = []
    if tree == []:  # `{}` and `[]` both parse to [] under the pairs hook
        out.append(KeySet(path="$", raw_keys=[]))
        return out
    _walk_keysets(tree, "$", out)
    return out


def independent_signal(keysets: Iterable[KeySet]) -> dict:
    """Signal (b): raw vs casefolded key-set sizes, independent of the validator verdict."""
    sets = list(keysets)
    worst = max(sets, key=lambda ks: ks.unique_raw_size - ks.casefolded_size, default=None)
    if worst is None:
        return {
            "any_case_collision": False,
            "sizes_differ": False,
            "worst_path": None,
            "worst_raw_keyset_size": 0,
            "worst_casefolded_keyset_size": 0,
            "keysets": 0,
        }
    return {
        "any_case_collision": any(ks.collides for ks in sets),
        "sizes_differ": worst.unique_raw_size != worst.casefolded_size,
        "worst_path": worst.path,
        "worst_raw_keyset_size": worst.unique_raw_size,
        "worst_casefolded_keyset_size": worst.casefolded_size,
        "keysets": len(sets),
    }


@dataclass
class DocumentVerdict:
    accepted: bool
    reason: str
    collisions: list[dict]


def _describe(ks: KeySet) -> str:
    groups = "; ".join(" vs ".join(repr(k) for k in g) for g in ks.colliding_groups())
    return f"case-collision at {ks.path}: {groups}"


def validate_document(text: str) -> DocumentVerdict:
    """REJECT a document whose sibling keys collide under casefold (or repeat exactly)."""
    try:
        json.loads(text, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as exc:
        return DocumentVerdict(False, f"parse-error: {exc}", [])
    keysets = iter_document_keysets(text)
    hits = [ks for ks in keysets if ks.collides]
    dups = [ks for ks in keysets if len(ks.raw_keys) != ks.unique_raw_size]
    if hits:
        reason = "; ".join(_describe(ks) for ks in hits)
        return DocumentVerdict(
            False,
            reason,
            [{"path": ks.path, "keys": g} for ks in hits for g in ks.colliding_groups()],
        )
    if dups:
        repeated = sorted(
            {k for ks in dups for k in ks.raw_keys if ks.raw_keys.count(k) > 1}
        )
        return DocumentVerdict(
            False,
            "duplicate-key at " + ", ".join(ks.path for ks in dups) + f": {repeated}",
            [{"path": ks.path, "keys": repeated} for ks in dups],
        )
    return DocumentVerdict(True, "ok", [])


def casefold_last_wins(text: str) -> dict:
    """What a naive case-insensitive parser would keep: casefolded keys, last value wins."""

    def fold(node: object) -> object:
        if _is_pairs(node):
            folded: dict = {}
            for key, value in node:  # type: ignore[union-attr]
                folded[str(key).casefold()] = fold(value)
            return folded
        if isinstance(node, list):
            return [fold(item) for item in node]
        return node

    tree = json.loads(text, object_pairs_hook=_pairs_hook)
    if tree == []:
        return {}
    result = fold(tree)
    return result if isinstance(result, dict) else {"$": result}


def _check_mapping(node: object, loc: str) -> None:
    if isinstance(node, dict):
        ks = KeySet(path=loc, raw_keys=[str(k) for k in node.keys()])
        if ks.collides:
            raise CaseCollisionError(f"emitter-refused: {_describe(ks)}")
        for key, value in node.items():
            _check_mapping(value, f"{loc}.{key}")
    elif isinstance(node, (list, tuple)):
        for i, item in enumerate(node):
            _check_mapping(item, f"{loc}[{i}]")


def emit_document(mapping: dict, *, indent: int | None = 2) -> str:
    """Serialize ``mapping``; refuse (``CaseCollisionError``) before ``dumps`` on a collision."""
    _check_mapping(mapping, "$")
    text = json.dumps(mapping, indent=indent, ensure_ascii=False) + "\n"
    verdict = validate_document(text)
    if not verdict.accepted:  # belt-and-braces: never let a colliding document out
        raise CaseCollisionError(f"emitter-refused: {verdict.reason}")
    return text


__all__ = [
    "CaseCollisionError",
    "DEFAULT_TARGETS",
    "DocumentVerdict",
    "KIND_CASE",
    "KIND_DUP",
    "KeySet",
    "find_casefold_collisions",
    "extract_zip_case_insensitive",
    "both_signals",
    "casefold_last_wins",
    "emit_document",
    "independent_signal",
    "iter_document_keysets",
    "validate_document",
    "lint_file",
    "lint_text",
    "nfc_casefold",
]
