"""Estate-specific mutation operators for TST-0015.

Generic mutators (arithmetic, boundary) do not model the defects that actually
shipped here. Each operator injects one named class into an isolated tree copy
and records the original bytes so the tree can be restored to the pinned SHA.

Operators never write the shared checkout. apply() refuses an unmarked tree.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from treeutil import assert_isolated, unified_file_diff

SENTINEL_TOKEN = "SUCCESS:FIXTURE-UNIT"
DEFAULT_FALSE = "require_complete: bool = False"
DEFAULT_TRUE = "require_complete: bool = True"
MANIFEST_NAME_KEY = '"name":'
MANIFEST_NAME_FLIPPED = '"Name":'
ARTIFACT_PATH_JSON = '"json/receipt.json"'
# JSON source for the value json\receipt.json (one backslash in the string).
ARTIFACT_PATH_FLIPPED = '"json\\\\receipt.json"'

INCOMPLETE_PAYLOAD = {"complete": False}


@dataclass
class MutationRecord:
    operator_id: str
    targets: list[str]
    originals: dict[str, bytes]
    intended_summary: str
    diffs: dict[str, str] = field(default_factory=dict)

    def restore(self, tree: Path) -> None:
        assert_isolated(tree)
        for rel, raw in self.originals.items():
            path = tree / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)


ApplyFn = Callable[[Path], MutationRecord]
IntendFn = Callable[[Path, MutationRecord], bool]
ValidFn = Callable[[Path, MutationRecord], bool]


def _capture_and_write(
    tree: Path,
    operator_id: str,
    targets: list[str],
    new_bytes: dict[str, bytes],
    intended_summary: str,
) -> MutationRecord:
    assert_isolated(tree)
    originals: dict[str, bytes] = {}
    diffs: dict[str, str] = {}
    for rel in targets:
        path = tree / rel
        if not path.is_file():
            raise FileNotFoundError(f"{operator_id}: missing {rel}")
        originals[rel] = path.read_bytes()
    for rel, raw in new_bytes.items():
        if rel not in originals:
            raise RuntimeError(f"{operator_id}: write to unlisted target {rel}")
        if raw == originals[rel]:
            raise RuntimeError(f"{operator_id}: {rel} unchanged (no-op mutation)")
        (tree / rel).write_bytes(raw)
        diffs[rel] = unified_file_diff(rel, originals[rel], raw)
    return MutationRecord(
        operator_id=operator_id,
        targets=list(targets),
        originals=originals,
        intended_summary=intended_summary,
        diffs=diffs,
    )


def apply_lf_crlf(tree: Path) -> MutationRecord:
    rel = "text/notes.md"
    old = (tree / rel).read_bytes()
    if b"\r\n" in old:
        raise RuntimeError("lf-crlf-flip: target already has CRLF")
    if b"\n" not in old:
        raise RuntimeError("lf-crlf-flip: target has no LF to flip")
    new = old.replace(b"\n", b"\r\n")
    return _capture_and_write(
        tree,
        "lf-crlf-flip",
        [rel],
        {rel: new},
        "replace every LF with CRLF in text/notes.md; no other byte changes",
    )


def _intended_lf_crlf(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old, new = rec.originals[rel], (tree / rel).read_bytes()
    return (
        new == old.replace(b"\n", b"\r\n")
        and new != old
        and new.decode("utf-8").replace("\r\n", "\n") == old.decode("utf-8")
    )


def valid_text_still_decodes(tree: Path, rec: MutationRecord) -> bool:
    for rel in rec.targets:
        (tree / rel).read_text(encoding="utf-8")
    return True


def apply_json_key_case(tree: Path) -> MutationRecord:
    rel = "json/manifest.json"
    text = (tree / rel).read_text(encoding="utf-8")
    if MANIFEST_NAME_KEY not in text:
        raise RuntimeError("json-key-case-flip: no \"name\": key")
    if MANIFEST_NAME_FLIPPED in text:
        raise RuntimeError("json-key-case-flip: already flipped")
    # Surgical source replace so indent/key-order stay put. One root key only.
    if text.count(MANIFEST_NAME_KEY) != 1:
        raise RuntimeError("json-key-case-flip: expected exactly one \"name\":")
    new_text = text.replace(MANIFEST_NAME_KEY, MANIFEST_NAME_FLIPPED, 1)
    json.loads(new_text)  # must remain parseable JSON
    return _capture_and_write(
        tree,
        "json-key-case-flip",
        [rel],
        {rel: new_text.encode("utf-8")},
        'flip JSON key "name" to "Name" in json/manifest.json; values unchanged',
    )


def intended_json_key_case(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old_obj = json.loads(rec.originals[rel].decode("utf-8"))
    new_obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    if "name" not in old_obj or "Name" not in new_obj:
        return False
    if "name" in new_obj or "Name" in old_obj:
        return False
    if new_obj["Name"] != old_obj["name"]:
        return False
    rest_old = {k: v for k, v in old_obj.items() if k != "name"}
    rest_new = {k: v for k, v in new_obj.items() if k != "Name"}
    return rest_old == rest_new


def valid_json_parseable(tree: Path, rec: MutationRecord) -> bool:
    for rel in rec.targets:
        json.loads((tree / rel).read_text(encoding="utf-8"))
    return True


def apply_path_separator(tree: Path) -> MutationRecord:
    rel = "json/manifest.json"
    text = (tree / rel).read_text(encoding="utf-8")
    if ARTIFACT_PATH_JSON not in text:
        raise RuntimeError("path-separator-flip: posix artifact_path literal missing")
    # JSON-aware: flipping / to a single backslash in source would become \r.
    new_text = text.replace(ARTIFACT_PATH_JSON, ARTIFACT_PATH_FLIPPED, 1)
    obj = json.loads(new_text)
    if "/" in str(obj.get("artifact_path", "")):
        raise RuntimeError("path-separator-flip: posix separator survived")
    if "\\" not in obj["artifact_path"]:
        raise RuntimeError("path-separator-flip: backslash not in parsed value")
    return _capture_and_write(
        tree,
        "path-separator-flip",
        [rel],
        {rel: new_text.encode("utf-8")},
        "flip artifact_path posix separators to backslash via JSON-aware rewrite",
    )


def intended_path_separator(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old_obj = json.loads(rec.originals[rel].decode("utf-8"))
    new_obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    old_path = old_obj.get("artifact_path")
    new_path = new_obj.get("artifact_path")
    if not isinstance(old_path, str) or not isinstance(new_path, str):
        return False
    if new_path != old_path.replace("/", "\\"):
        return False
    rest_old = {k: v for k, v in old_obj.items() if k != "artifact_path"}
    rest_new = {k: v for k, v in new_obj.items() if k != "artifact_path"}
    return rest_old == rest_new


def apply_sentinel_deletion(tree: Path) -> MutationRecord:
    rel = "json/receipt.json"
    obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    if obj.get("sentinel") != SENTINEL_TOKEN:
        raise RuntimeError("sentinel-deletion: sentinel field is not the live token")
    text = (tree / rel).read_text(encoding="utf-8")
    # Delete the token from the field, keep JSON valid. Do not touch mentions elsewhere.
    new_text = text.replace(f'"{SENTINEL_TOKEN}"', '""', 1)
    new_obj = json.loads(new_text)
    if new_obj.get("sentinel") != "":
        raise RuntimeError("sentinel-deletion: sentinel field not cleared")
    return _capture_and_write(
        tree,
        "sentinel-deletion",
        [rel],
        {rel: new_text.encode("utf-8")},
        "clear json/receipt.json sentinel field; JSON remains parseable",
    )


def intended_sentinel_deletion(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old_obj = json.loads(rec.originals[rel].decode("utf-8"))
    new_obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    if old_obj.get("sentinel") != SENTINEL_TOKEN:
        return False
    if new_obj.get("sentinel") != "":
        return False
    rest_old = {k: v for k, v in old_obj.items() if k != "sentinel"}
    rest_new = {k: v for k, v in new_obj.items() if k != "sentinel"}
    return rest_old == rest_new


def apply_truncation(tree: Path) -> MutationRecord:
    rel = "json/receipt.json"
    old = (tree / rel).read_bytes()
    if len(old) < 40:
        raise RuntimeError("mid-write-truncation: fixture too small")
    # Cut inside the sentinel string so the write looks mid-flight, not at a brace.
    token = SENTINEL_TOKEN.encode("ascii")
    idx = old.find(token)
    if idx < 0:
        raise RuntimeError("mid-write-truncation: token not in file")
    cut = idx + len(token) // 2
    new = old[:cut]
    try:
        json.loads(new.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    else:
        raise RuntimeError("mid-write-truncation: truncated file still parsed")
    if not new:
        raise RuntimeError("mid-write-truncation: empty file (MSYS-truncation signature)")
    return _capture_and_write(
        tree,
        "mid-write-truncation",
        [rel],
        {rel: new},
        "truncate json/receipt.json mid-token; file remains non-empty and unparseable",
    )


def intended_truncation(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old, new = rec.originals[rel], (tree / rel).read_bytes()
    if not new or not old.startswith(new) or len(new) >= len(old):
        return False
    try:
        json.loads(new.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return True
    return False


def valid_tree_walkable(tree: Path, rec: MutationRecord) -> bool:
    """Truncation yields a defective file inside a still-walkable tree."""
    for rel in rec.targets:
        path = tree / rel
        if not path.is_file() or path.stat().st_size <= 0:
            return False
    return True


def apply_default_argument(tree: Path) -> MutationRecord:
    rel = "code/module.py"
    text = (tree / rel).read_text(encoding="utf-8")
    if text.count(DEFAULT_FALSE) != 1:
        raise RuntimeError("default-argument-change: expected one False default")
    new_text = text.replace(DEFAULT_FALSE, DEFAULT_TRUE, 1)
    ast.parse(new_text)
    return _capture_and_write(
        tree,
        "default-argument-change",
        [rel],
        {rel: new_text.encode("utf-8")},
        "flip require_complete default False -> True in code/module.py",
    )


def intended_default_argument(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    old = rec.originals[rel].decode("utf-8")
    new = (tree / rel).read_text(encoding="utf-8")
    if DEFAULT_FALSE not in old or DEFAULT_TRUE not in new:
        return False
    restored = new.replace(DEFAULT_TRUE, DEFAULT_FALSE, 1)
    return restored == old


def valid_python_parses(tree: Path, rec: MutationRecord) -> bool:
    for rel in rec.targets:
        ast.parse((tree / rel).read_text(encoding="utf-8"))
    return True


def apply_use_vs_mention(tree: Path) -> MutationRecord:
    rel = "json/receipt.json"
    obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    if obj.get("sentinel") != SENTINEL_TOKEN:
        raise RuntimeError("use-vs-mention-swap: live use missing")
    obj["sentinel"] = "NOT-A-SENTINEL"
    obj["notes"] = (
        f'documentation example: "{SENTINEL_TOKEN}" must appear in the sentinel field'
    )
    new_text = json.dumps(obj, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL_TOKEN not in new_text:
        raise RuntimeError("use-vs-mention-swap: mention did not land in file")
    if json.loads(new_text)["sentinel"] == SENTINEL_TOKEN:
        raise RuntimeError("use-vs-mention-swap: use still in sentinel field")
    return _capture_and_write(
        tree,
        "use-vs-mention-swap",
        [rel],
        {rel: new_text.encode("utf-8")},
        "move SUCCESS:FIXTURE-UNIT from the sentinel field into a quoted mention",
    )


def intended_use_vs_mention(tree: Path, rec: MutationRecord) -> bool:
    rel = rec.targets[0]
    new_obj = json.loads((tree / rel).read_text(encoding="utf-8"))
    text = (tree / rel).read_text(encoding="utf-8")
    if new_obj.get("sentinel") == SENTINEL_TOKEN:
        return False
    notes = str(new_obj.get("notes") or "")
    if SENTINEL_TOKEN not in notes:
        return False
    if SENTINEL_TOKEN not in text:
        return False
    return True


@dataclass(frozen=True)
class Operator:
    operator_id: str
    apply: ApplyFn
    intended: IntendFn
    valid_tree: ValidFn
    defect_class: str


OPERATORS: tuple[Operator, ...] = (
    Operator(
        "lf-crlf-flip",
        apply_lf_crlf,
        _intended_lf_crlf,
        valid_text_still_decodes,
        "LF->CRLF flip",
    ),
    Operator(
        "json-key-case-flip",
        apply_json_key_case,
        intended_json_key_case,
        valid_json_parseable,
        "JSON key-case flip",
    ),
    Operator(
        "path-separator-flip",
        apply_path_separator,
        intended_path_separator,
        valid_json_parseable,
        "path-separator flip",
    ),
    Operator(
        "sentinel-deletion",
        apply_sentinel_deletion,
        intended_sentinel_deletion,
        valid_json_parseable,
        "sentinel deletion",
    ),
    Operator(
        "mid-write-truncation",
        apply_truncation,
        intended_truncation,
        valid_tree_walkable,
        "mid-write truncation",
    ),
    Operator(
        "default-argument-change",
        apply_default_argument,
        intended_default_argument,
        valid_python_parses,
        "default-argument change",
    ),
    Operator(
        "use-vs-mention-swap",
        apply_use_vs_mention,
        intended_use_vs_mention,
        valid_json_parseable,
        "use-vs-mention swap",
    ),
)

OPERATOR_BY_ID = {op.operator_id: op for op in OPERATORS}


def get(operator_id: str) -> Operator:
    try:
        return OPERATOR_BY_ID[operator_id]
    except KeyError as exc:
        raise KeyError(f"unknown operator {operator_id}") from exc
