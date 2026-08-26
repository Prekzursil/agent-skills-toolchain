from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


_DOC_EXTENSIONS = frozenset({".adoc", ".md", ".rst", ".txt"})
_SOURCE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".cxx",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".pyi",
        ".rb",
        ".rs",
        ".swift",
        ".ts",
        ".tsx",
    }
)
_RECURRING_BASENAMES = frozenset(
    {"__init__.py", "index.js", "index.jsx", "index.ts", "index.tsx"}
)
_STRUCTURED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
_PATCH_TOOLS = frozenset({"apply_patch"})
_UNIDENTIFIED_OWNERS = frozenset({"", "none", "null", "unknown"})
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "AUX",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "CON",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
        "NUL",
        "PRN",
    }
)
_PATCH_PAYLOAD_KEYS = frozenset({"environment_id", "patch"})
_NEWLINE_BY_LABEL = {
    "cr": "\r",
    "crlf": "\r\n",
    "lf": "\n",
    "mixed": "\n",
    "none": "\n",
}


class MutationPlanningError(ValueError):
    """Raised when a tool payload cannot be reduced to deterministic file mutations."""


@dataclass(frozen=True)
class ResolvedTarget:
    relative_path: Path
    absolute_path: Path
    exists: bool


@dataclass(frozen=True)
class PathMutation:
    kind: Literal["add", "delete", "move", "update"]
    target_relative_path: str
    source_relative_path: str | None
    target_absolute_path: str
    source_absolute_path: str | None
    target_exists_before: bool
    source_exists_before: bool | None
    target_file_identity: str | None
    source_file_identity: str | None
    postimage_bytes: bytes | None
    postimage_sha256: str | None
    doc_family: str | None
    source_basename: str | None
    top_level_symbols: tuple[str, ...]
    line_ending: Literal["cr", "crlf", "lf", "mixed", "none"]
    has_final_newline: bool


@dataclass(frozen=True)
class MutationPlan:
    tool_name: str
    owner: str
    operation_id: str
    payload_sha256: str
    targets: tuple[str, ...]
    mutations: tuple[PathMutation, ...]


@dataclass(frozen=True)
class _ValidatedTarget:
    relative_path: Path
    absolute_path: Path
    physical_path: Path
    exists: bool
    file_identity: str | None


@dataclass(frozen=True)
class _PatchBodyLine:
    kind: Literal[" ", "+", "-"]
    text: str


@dataclass(frozen=True)
class _PatchChunk:
    headers: tuple[str, ...]
    lines: tuple[_PatchBodyLine, ...]
    end_of_file: bool


@dataclass(frozen=True)
class _PatchOperation:
    kind: Literal["add", "delete", "move", "update"]
    source: str
    target: str
    chunks: tuple[_PatchChunk, ...]


@dataclass(frozen=True)
class _LineRecord:
    text: str
    ending: str


@dataclass(frozen=True)
class _DecodedFile:
    records: tuple[_LineRecord, ...]
    line_ending: Literal["cr", "crlf", "lf", "mixed", "none"]
    has_final_newline: bool


CanonicalPathResolver = Callable[[str, Path, Path], ResolvedTarget]
PolicyName = Literal["workspace_strict"]
LineEndingMode = Literal["preserve"]


def build_mutation_plan(
    *,
    tool_name: str,
    payload: Any,
    owner: str,
    tool_use_id: str | None,
    repo_root: Path,
    base_dir: Path,
    resolve_target: CanonicalPathResolver,
    policy: PolicyName = "workspace_strict",
    line_ending_mode: LineEndingMode = "preserve",
) -> MutationPlan:
    owner_text = str(owner).strip()
    if owner_text.lower() in _UNIDENTIFIED_OWNERS:
        raise MutationPlanningError("unknown owner is rejected by caller contract")
    if tool_name not in _STRUCTURED_TOOLS | _PATCH_TOOLS:
        raise MutationPlanningError(f"unsupported tool: {tool_name}")
    if policy != "workspace_strict":
        raise MutationPlanningError(f"unsupported workspace mutation policy: {policy}")
    if line_ending_mode != "preserve":
        raise MutationPlanningError(f"unsupported line ending mode: {line_ending_mode}")
    repo_root = repo_root.resolve(strict=True)
    base_dir = base_dir.resolve(strict=False)
    payload_sha256 = _canonical_payload_sha256(payload)
    if tool_name in _STRUCTURED_TOOLS:
        targets, mutations = _build_structured_mutations(
            tool_name=tool_name,
            payload=payload,
            repo_root=repo_root,
            base_dir=base_dir,
            resolve_target=resolve_target,
            line_ending_mode=line_ending_mode,
        )
    else:
        targets, mutations = _build_patch_mutations(
            payload=payload,
            repo_root=repo_root,
            base_dir=base_dir,
            resolve_target=resolve_target,
            policy=policy,
            line_ending_mode=line_ending_mode,
        )
    return MutationPlan(
        tool_name=tool_name,
        owner=owner_text,
        operation_id=_operation_id(
            owner=owner_text,
            tool_use_id=tool_use_id,
            targets=targets,
            payload_sha256=payload_sha256,
        ),
        payload_sha256=payload_sha256,
        targets=targets,
        mutations=mutations,
    )


def _build_structured_mutations(
    *,
    tool_name: str,
    payload: Any,
    repo_root: Path,
    base_dir: Path,
    resolve_target: CanonicalPathResolver,
    line_ending_mode: LineEndingMode,
) -> tuple[tuple[str, ...], tuple[PathMutation, ...]]:
    if not isinstance(payload, dict):
        raise MutationPlanningError(f"{tool_name} payload must be an object")
    raw_target = payload.get("file_path")
    if not isinstance(raw_target, str) or not raw_target.strip():
        raise MutationPlanningError(f"{tool_name} target is missing")
    target = _resolve_target(
        resolve_target=resolve_target,
        raw_target=raw_target,
        base_dir=base_dir,
        repo_root=repo_root,
    )
    if tool_name == "Write":
        content = payload.get("content")
        if not isinstance(content, str):
            raise MutationPlanningError("Write content must be a string")
        encoded = content.encode("utf-8")
        decoded = _decode_postimage(encoded)
        kind: Literal["add", "update"] = "update" if target.exists else "add"
        return (
            (target.relative_path.as_posix(),),
            (
                _build_mutation(
                    kind=kind,
                    source=None,
                    target=target,
                    postimage=encoded,
                    decoded=decoded,
                ),
            ),
        )
    if not target.exists:
        raise MutationPlanningError(f"{tool_name} target is missing")
    original = _read_utf8_bytes(target.absolute_path)
    decoded_source = _decode_source_bytes(original)
    current_text = original.decode("utf-8")
    preferred_line_ending = _select_preferred_line_ending(
        decoded_source, line_ending_mode
    )
    if tool_name == "Edit":
        updated_text = _apply_edit(
            current_text, payload, preferred_line_ending=preferred_line_ending
        )
    else:
        updated_text = _apply_multiedit(
            current_text, payload, preferred_line_ending=preferred_line_ending
        )
    encoded = updated_text.encode("utf-8")
    decoded = _decode_postimage(encoded)
    return (
        (target.relative_path.as_posix(),),
        (
            _build_mutation(
                kind="update",
                source=None,
                target=target,
                postimage=encoded,
                decoded=decoded,
            ),
        ),
    )


def _build_patch_mutations(
    *,
    payload: Any,
    repo_root: Path,
    base_dir: Path,
    resolve_target: CanonicalPathResolver,
    policy: PolicyName,
    line_ending_mode: LineEndingMode,
) -> tuple[tuple[str, ...], tuple[PathMutation, ...]]:
    operations = _parse_patch(_extract_patch_text(payload))
    touched: list[str] = []
    seen_targets: set[str] = set()
    seen_operation_paths: dict[str, str] = {}
    mutations: list[PathMutation] = []
    for operation in operations:
        source = _resolve_target(
            resolve_target=resolve_target,
            raw_target=operation.source,
            base_dir=base_dir,
            repo_root=repo_root,
        )
        _remember_operation_target(seen_operation_paths, source)
        _remember_target(touched, seen_targets, source.relative_path.as_posix())
        if operation.kind == "add":
            if source.exists:
                raise MutationPlanningError(
                    f"{policy} policy blocks Add File over existing path: {source.relative_path.as_posix()}"
                )
            encoded = _render_added_file(operation.chunks)
            decoded = _decode_postimage(encoded)
            mutations.append(
                _build_mutation(
                    kind="add",
                    source=None,
                    target=source,
                    postimage=encoded,
                    decoded=decoded,
                )
            )
            continue
        if not source.exists:
            raise MutationPlanningError(
                f"patch source is missing: {source.relative_path.as_posix()}"
            )
        if operation.kind == "delete":
            mutations.append(
                _build_mutation(
                    kind="delete",
                    source=None,
                    target=source,
                    postimage=None,
                    decoded=None,
                )
            )
            continue
        target = _resolve_target(
            resolve_target=resolve_target,
            raw_target=operation.target,
            base_dir=base_dir,
            repo_root=repo_root,
        )
        _remember_target(touched, seen_targets, target.relative_path.as_posix())
        if operation.kind == "move" and _same_physical_target(source, target):
            raise MutationPlanningError(
                "move target resolves to the same physical file"
            )
        if operation.kind == "move" and target.exists:
            raise MutationPlanningError(
                f"{policy} policy blocks Move over existing path: {target.relative_path.as_posix()}"
            )
        if operation.kind == "move":
            _remember_operation_target(seen_operation_paths, target)
        original = _read_utf8_bytes(source.absolute_path)
        encoded = _apply_patch_to_bytes(
            original,
            operation.chunks,
            line_ending_mode=line_ending_mode,
        )
        decoded = _decode_postimage(encoded)
        mutations.append(
            _build_mutation(
                kind=operation.kind,
                source=source if operation.kind == "move" else None,
                target=target,
                postimage=encoded,
                decoded=decoded,
            )
        )
    return tuple(touched), tuple(mutations)


def _resolve_target(
    *,
    resolve_target: CanonicalPathResolver,
    raw_target: str,
    base_dir: Path,
    repo_root: Path,
) -> _ValidatedTarget:
    try:
        resolved = resolve_target(raw_target, base_dir, repo_root)
    except MutationPlanningError:
        raise
    except Exception as exc:  # pragma: no cover
        raise MutationPlanningError(f"target resolution failed: {raw_target}") from exc
    if not isinstance(resolved, ResolvedTarget):
        raise MutationPlanningError("target resolver returned an invalid result")
    relative_path = _sanitize_relative_path(resolved.relative_path)
    absolute_path = Path(resolved.absolute_path)
    if not absolute_path.is_absolute():
        raise MutationPlanningError("resolver returned a non-absolute target")
    absolute_path = _normalize_absolute_path(absolute_path)
    if not _is_within_repo(repo_root, absolute_path):
        raise MutationPlanningError("resolver returned a target outside the repo")
    _validate_existing_ancestors(repo_root, absolute_path)
    physical_path = absolute_path.resolve(strict=False)
    if not _is_within_repo(repo_root, physical_path):
        raise MutationPlanningError("resolver returned a target outside the repo")
    expected_relative = _physical_relative_path(repo_root, physical_path)
    if _normalized_relative_key(relative_path) != _normalized_relative_key(
        expected_relative
    ):
        raise MutationPlanningError(
            "resolver returned mismatched relative and absolute paths"
        )
    existing_stat = _stat_existing_target(physical_path)
    actual_exists = existing_stat is not None
    if bool(resolved.exists) != actual_exists:
        raise MutationPlanningError("resolver returned a stale existence flag")
    file_identity = _file_identity_from_stat(existing_stat) if existing_stat else None
    if actual_exists:
        if not stat.S_ISREG(existing_stat.st_mode):
            raise MutationPlanningError("resolver returned a non-regular file target")
        canonical_absolute = (repo_root / relative_path).resolve(strict=True)
        if not os.path.samefile(canonical_absolute, physical_path):
            raise MutationPlanningError("resolver returned a mismatched file identity")
    return _ValidatedTarget(
        relative_path=expected_relative,
        absolute_path=absolute_path,
        physical_path=physical_path,
        exists=actual_exists,
        file_identity=file_identity,
    )


def _sanitize_relative_path(raw_relative: Path) -> Path:
    value = str(raw_relative).replace("\\", "/").strip()
    if not value:
        raise MutationPlanningError("resolver returned an empty relative path")
    relative = Path(value)
    if relative.is_absolute():
        raise MutationPlanningError("resolver returned an absolute relative path")
    for part in relative.parts:
        if part in {".", ".."}:
            raise MutationPlanningError("resolver returned a traversal path")
        if ":" in part:
            raise MutationPlanningError("resolver returned a path with ADS syntax")
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise MutationPlanningError("resolver returned a Windows device path")
    return relative


def _normalize_absolute_path(path: Path) -> Path:
    return Path(os.path.normpath(os.fspath(path)))


def _validate_existing_ancestors(repo_root: Path, absolute_path: Path) -> None:
    try:
        relative_absolute = absolute_path.relative_to(repo_root)
    except ValueError as exc:
        raise MutationPlanningError(
            "resolver returned a target outside the repo"
        ) from exc
    current = repo_root
    for part in relative_absolute.parts[:-1]:
        current = current / part
        try:
            stat_result = current.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise MutationPlanningError(
                f"resolver target ancestor is unreadable: {current}"
            ) from exc
        if not stat.S_ISDIR(stat_result.st_mode):
            relative_ancestor = current.relative_to(repo_root).as_posix()
            raise MutationPlanningError(
                f"resolver target ancestor is not a directory: {relative_ancestor}"
            )
        physical_ancestor = current.resolve(strict=True)
        if not _is_within_repo(repo_root, physical_ancestor):
            relative_ancestor = current.relative_to(repo_root).as_posix()
            raise MutationPlanningError(
                f"resolver target ancestor escapes repo root: {relative_ancestor}"
            )


def _is_within_repo(repo_root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath([str(repo_root), str(candidate)]) == str(repo_root)
    except ValueError:
        return False


def _physical_relative_path(repo_root: Path, physical_path: Path) -> Path:
    try:
        return physical_path.relative_to(repo_root)
    except ValueError as exc:
        raise MutationPlanningError("resolver target escapes repo root") from exc


def _normalized_relative_key(path: Path) -> str:
    return os.path.normcase(path.as_posix())


def _stat_existing_target(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MutationPlanningError(f"resolver target is unreadable: {path}") from exc


def _file_identity_from_stat(stat_result: os.stat_result) -> str:
    return f"{stat_result.st_dev}:{stat_result.st_ino}"


def _file_identity(path: Path) -> str | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None
    return f"{stat_result.st_dev}:{stat_result.st_ino}"


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except OSError:
        return False


def _same_physical_target(source: _ValidatedTarget, target: _ValidatedTarget) -> bool:
    if _normalized_relative_key(source.relative_path) == _normalized_relative_key(
        target.relative_path
    ):
        return True
    if source.exists and target.exists:
        try:
            return os.path.samefile(source.physical_path, target.physical_path)
        except OSError:
            return False
    return (
        source.file_identity is not None
        and source.file_identity == target.file_identity
    )


def _canonical_payload_sha256(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MutationPlanningError("payload is not canonically serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


def _operation_id(
    *,
    owner: str,
    tool_use_id: str | None,
    targets: tuple[str, ...],
    payload_sha256: str,
) -> str:
    if isinstance(tool_use_id, str) and tool_use_id.strip():
        return tool_use_id.strip()
    material = "\n".join((owner, *targets, payload_sha256)).encode("utf-8")
    return f"{owner}:{hashlib.sha256(material).hexdigest()[:16]}"


def _apply_edit(
    text: str, payload: dict[str, Any], *, preferred_line_ending: str
) -> str:
    old_string = payload.get("old_string")
    new_string = payload.get("new_string")
    replace_all = _replace_all_flag(payload)
    if not isinstance(old_string, str) or not isinstance(new_string, str):
        raise MutationPlanningError("Edit old_string/new_string must be strings")
    return _replace_text(
        text=text,
        old_string=old_string,
        new_string=new_string,
        replace_all=replace_all,
        preferred_line_ending=preferred_line_ending,
    )


def _apply_multiedit(
    text: str, payload: dict[str, Any], *, preferred_line_ending: str
) -> str:
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise MutationPlanningError("MultiEdit edits must be a non-empty list")
    current = text
    for edit in edits:
        if not isinstance(edit, dict):
            raise MutationPlanningError("MultiEdit edit entries must be objects")
        old_string = edit.get("old_string")
        new_string = edit.get("new_string")
        replace_all = _replace_all_flag(edit)
        if not isinstance(old_string, str) or not isinstance(new_string, str):
            raise MutationPlanningError(
                "MultiEdit old_string/new_string must be strings"
            )
        current = _replace_text(
            text=current,
            old_string=old_string,
            new_string=new_string,
            replace_all=replace_all,
            preferred_line_ending=preferred_line_ending,
        )
    return current


def _replace_all_flag(payload: dict[str, Any]) -> bool:
    if "replace_all" not in payload:
        return False
    value = payload["replace_all"]
    if isinstance(value, bool):
        return value
    raise MutationPlanningError("replace_all must be an explicit boolean")


def _replace_text(
    *,
    text: str,
    old_string: str,
    new_string: str,
    replace_all: bool,
    preferred_line_ending: str,
) -> str:
    if old_string == "":
        raise MutationPlanningError("empty edit context is not supported")
    search_old = old_string
    replacement_new = _coerce_payload_line_endings(new_string, preferred_line_ending)
    count = text.count(search_old)
    if count == 0:
        search_old = _coerce_payload_line_endings(old_string, preferred_line_ending)
        count = text.count(search_old)
    if count == 0:
        raise MutationPlanningError("missing edit context")
    if replace_all:
        return text.replace(search_old, replacement_new)
    if count != 1:
        raise MutationPlanningError("ambiguous edit context")
    return text.replace(search_old, replacement_new, 1)


def _coerce_payload_line_endings(text: str, preferred_line_ending: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if preferred_line_ending == "\n":
        return normalized
    return normalized.replace("\n", preferred_line_ending)


def _extract_patch_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict) or "patch" not in payload:
        raise MutationPlanningError("apply_patch payload is invalid")
    if not set(payload).issubset(_PATCH_PAYLOAD_KEYS):
        raise MutationPlanningError("apply_patch payload has unsupported keys")
    patch = payload.get("patch")
    environment_id = payload.get("environment_id")
    if not isinstance(patch, str):
        raise MutationPlanningError("apply_patch patch must be a string")
    if "environment_id" in payload and not isinstance(environment_id, str):
        raise MutationPlanningError("apply_patch environment_id must be a string")
    return patch


def _parse_patch(patch_text: str) -> tuple[_PatchOperation, ...]:
    lines = patch_text.strip().splitlines()
    if (
        len(lines) < 2
        or lines[0].strip() != "*** Begin Patch"
        or lines[-1].strip() != "*** End Patch"
    ):
        raise MutationPlanningError("patch envelope is invalid")
    index = 1
    if index < len(lines) - 1 and lines[index].strip().startswith(
        "*** Environment ID:"
    ):
        environment_id = lines[index].strip()[len("*** Environment ID:") :].strip()
        if not environment_id:
            raise MutationPlanningError("patch environment id is empty")
        index += 1
    operations: list[_PatchOperation] = []
    while index < len(lines) - 1:
        line = lines[index].strip()
        if line.startswith("*** Add File: "):
            target = line[len("*** Add File: ") :].strip()
            if not target:
                raise MutationPlanningError("patch add target is missing")
            index += 1
            chunks, index = _parse_chunks(lines, index, allow_unheaded=True)
            if not chunks:
                raise MutationPlanningError("patch add body is missing")
            operations.append(
                _PatchOperation(kind="add", source=target, target=target, chunks=chunks)
            )
            continue
        if line.startswith("*** Delete File: "):
            target = line[len("*** Delete File: ") :].strip()
            if not target:
                raise MutationPlanningError("patch delete target is missing")
            operations.append(
                _PatchOperation(kind="delete", source=target, target=target, chunks=())
            )
            index += 1
            continue
        if line.startswith("*** Update File: "):
            source = line[len("*** Update File: ") :].strip()
            if not source:
                raise MutationPlanningError("patch update target is missing")
            index += 1
            target = source
            kind: Literal["move", "update"] = "update"
            if index < len(lines) - 1 and lines[index].startswith("*** Move to: "):
                target = lines[index][len("*** Move to: ") :].strip()
                if not target:
                    raise MutationPlanningError("patch move target is missing")
                kind = "move"
                index += 1
            chunks, index = _parse_chunks(lines, index, allow_unheaded=True)
            if not chunks:
                raise MutationPlanningError("patch update has no hunks")
            operations.append(
                _PatchOperation(kind=kind, source=source, target=target, chunks=chunks)
            )
            continue
        raise MutationPlanningError(f"unknown patch directive: {line}")
    return tuple(operations)


def _parse_chunks(
    lines: list[str], start_index: int, *, allow_unheaded: bool
) -> tuple[tuple[_PatchChunk, ...], int]:
    index = start_index
    chunks: list[_PatchChunk] = []
    headers: list[str] = []
    current_body: list[_PatchBodyLine] = []
    current_eof = False
    saw_body = False

    def flush_chunk() -> None:
        nonlocal current_body, current_eof, saw_body
        if not current_body and not current_eof:
            return
        if not saw_body:
            raise MutationPlanningError("patch hunk has no body")
        if not any(item.kind in {"+", "-"} for item in current_body):
            raise MutationPlanningError("patch hunk must change content")
        chunks.append(
            _PatchChunk(
                headers=tuple(headers),
                lines=tuple(current_body),
                end_of_file=current_eof,
            )
        )
        headers.clear()
        current_body = []
        current_eof = False
        saw_body = False

    while index < len(lines) - 1 and (
        not lines[index].startswith("*** ") or lines[index] == "*** End of File"
    ):
        line = lines[index]
        marker_line = line.rstrip()
        header = _parse_patch_header(marker_line)
        if current_eof:
            if not marker_line:
                index += 1
                continue
            if header is not None:
                flush_chunk()
                headers.append(header)
                index += 1
                continue
            raise MutationPlanningError("patch hunk body cannot follow end of file")
        if header is not None:
            if saw_body:
                flush_chunk()
            elif headers:
                raise MutationPlanningError("patch hunk header is malformed")
            headers.append(header)
            index += 1
            continue
        if marker_line == "*** End of File":
            if not headers and not saw_body:
                raise MutationPlanningError("patch eof marker has no active hunk")
            current_eof = True
            saw_body = True
            index += 1
            continue
        if line == "":
            kind = " "
            text = ""
        elif line.startswith((" ", "+", "-")):
            kind = line[0]
            text = line[1:]
        else:
            raise MutationPlanningError("patch hunk body is malformed")
        if not headers and not saw_body and not allow_unheaded:
            raise MutationPlanningError("patch hunk header is missing")
        current_body.append(_PatchBodyLine(kind=kind, text=text))
        saw_body = True
        index += 1
    if headers or current_body or current_eof:
        flush_chunk()
    return tuple(chunks), index


def _parse_patch_header(line: str) -> str | None:
    if line == "@@":
        return ""
    if line.startswith("@@ "):
        return line[3:]
    if line.startswith("@@"):
        raise MutationPlanningError("patch hunk header is malformed")
    return None


def _render_added_file(chunks: tuple[_PatchChunk, ...]) -> bytes:
    if len(chunks) != 1:
        raise MutationPlanningError("patch add must contain a single body")
    chunk = chunks[0]
    if chunk.headers or chunk.end_of_file:
        raise MutationPlanningError("patch add body must contain only direct additions")
    for entry in chunk.lines:
        if entry.kind != "+":
            raise MutationPlanningError("patch add body must contain only additions")
    final_newline = not chunk.end_of_file
    text = "\n".join(entry.text for entry in chunk.lines)
    if final_newline and chunk.lines:
        text += "\n"
    return text.encode("utf-8")


def _apply_patch_to_bytes(
    original: bytes,
    chunks: tuple[_PatchChunk, ...],
    *,
    line_ending_mode: LineEndingMode,
) -> bytes:
    decoded = _decode_source_bytes(original)
    records = list(decoded.records)
    cursor = 0
    preferred_line_ending = _select_preferred_line_ending(decoded, line_ending_mode)
    for chunk in chunks:
        match, next_cursor = _find_chunk_match(records, cursor, chunk)
        if chunk.end_of_file and match + _old_length(chunk) != len(records):
            raise MutationPlanningError("patch eof marker must target file end")
        replacement = _build_replacement_records(
            matched=records[match : match + _old_length(chunk)],
            chunk=chunk,
            preferred_ending=preferred_line_ending,
        )
        records[match : match + _old_length(chunk)] = replacement
        if _old_length(chunk) == 0:
            cursor = next_cursor
        else:
            cursor = match + len(replacement)
    for index, record in enumerate(records):
        if record.ending == "":
            records[index] = _LineRecord(text=record.text, ending=preferred_line_ending)
    return "".join(record.text + record.ending for record in records).encode("utf-8")


def _old_length(chunk: _PatchChunk) -> int:
    return sum(1 for entry in chunk.lines if entry.kind != "+")


def _build_replacement_records(
    *,
    matched: list[_LineRecord],
    chunk: _PatchChunk,
    preferred_ending: str,
) -> list[_LineRecord]:
    replacement: list[_LineRecord] = []
    matched_index = 0
    for entry in chunk.lines:
        if entry.kind == " ":
            record = matched[matched_index]
            if not _patch_line_matches(record.text, entry.text):
                raise MutationPlanningError(
                    "patch context did not match the source slice"
                )
            replacement.append(record)
            matched_index += 1
            continue
        if entry.kind == "-":
            record = matched[matched_index]
            if not _patch_line_matches(record.text, entry.text):
                raise MutationPlanningError(
                    "patch delete did not match the source slice"
                )
            matched_index += 1
            continue
        replacement.append(_LineRecord(text=entry.text, ending=preferred_ending))
    if matched_index != len(matched):
        raise MutationPlanningError(
            "patch hunk did not consume its entire source slice"
        )
    return replacement


def _preferred_line_ending(decoded: _DecodedFile) -> str:
    for record in decoded.records:
        if record.ending:
            return record.ending
    return _NEWLINE_BY_LABEL.get(decoded.line_ending, "\n")


def _select_preferred_line_ending(
    decoded: _DecodedFile, line_ending_mode: LineEndingMode
) -> str:
    if line_ending_mode != "preserve":
        raise MutationPlanningError(f"unsupported line ending mode: {line_ending_mode}")
    return _preferred_line_ending(decoded)


def _find_chunk_match(
    records: list[_LineRecord], cursor: int, chunk: _PatchChunk
) -> tuple[int, int]:
    record_texts = [record.text for record in records]
    anchor_floor = _anchor_floor(record_texts, chunk.headers, cursor)
    old_lines = [entry.text for entry in chunk.lines if entry.kind != "+"]
    if not old_lines:
        if any(header for header in chunk.headers):
            return len(records), anchor_floor
        return len(records), cursor
    match = _seek_sequence(
        record_texts,
        old_lines,
        start=anchor_floor,
        eof=chunk.end_of_file,
    )
    if match is None:
        raise MutationPlanningError("missing patch context")
    return match, match + len(old_lines)


def _anchor_floor(lines: list[str], headers: tuple[str, ...], cursor: int) -> int:
    filtered_headers = tuple(header for header in headers if header)
    if not filtered_headers:
        return cursor
    line_index = cursor
    for header in filtered_headers:
        match = _seek_sequence(lines, [header], start=line_index, eof=False)
        if match is None:
            raise MutationPlanningError("missing patch header anchor")
        line_index = match + 1
    return line_index


def _seek_sequence(
    lines: list[str],
    pattern: list[str],
    *,
    start: int,
    eof: bool,
) -> int | None:
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None
    if eof and len(lines) >= len(pattern):
        search_start = max(start, len(lines) - len(pattern))
    else:
        search_start = start
    for matcher in (
        _sequence_exact_match,
        _sequence_rstrip_match,
        _sequence_strip_match,
        _sequence_normalized_match,
    ):
        match = matcher(lines, pattern, search_start)
        if match is not None:
            return match
    return None


def _sequence_exact_match(
    lines: list[str], pattern: list[str], start: int
) -> int | None:
    for index in range(start, len(lines) - len(pattern) + 1):
        if lines[index : index + len(pattern)] == pattern:
            return index
    return None


def _sequence_rstrip_match(
    lines: list[str], pattern: list[str], start: int
) -> int | None:
    return _sequence_match_by(lines, pattern, start, str.rstrip)


def _sequence_strip_match(
    lines: list[str], pattern: list[str], start: int
) -> int | None:
    return _sequence_match_by(lines, pattern, start, str.strip)


def _sequence_normalized_match(
    lines: list[str], pattern: list[str], start: int
) -> int | None:
    return _sequence_match_by(lines, pattern, start, _normalize_match_text)


def _sequence_match_by(
    lines: list[str],
    pattern: list[str],
    start: int,
    transform: Callable[[str], str],
) -> int | None:
    transformed_pattern = [transform(item) for item in pattern]
    for index in range(start, len(lines) - len(pattern) + 1):
        if [
            transform(item) for item in lines[index : index + len(pattern)]
        ] == transformed_pattern:
            return index
    return None


def _normalize_match_text(text: str) -> str:
    substitutions = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u00a0": " ",
        "\u2002": " ",
        "\u2003": " ",
        "\u2004": " ",
        "\u2005": " ",
        "\u2006": " ",
        "\u2007": " ",
        "\u2008": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u202f": " ",
        "\u205f": " ",
        "\u3000": " ",
    }
    return "".join(substitutions.get(char, char) for char in text.strip())


def _patch_line_matches(actual: str, expected: str) -> bool:
    return any(
        comparator(actual, expected)
        for comparator in (
            lambda left, right: left == right,
            lambda left, right: left.rstrip() == right.rstrip(),
            lambda left, right: left.strip() == right.strip(),
            lambda left, right: (
                _normalize_match_text(left) == _normalize_match_text(right)
            ),
        )
    )


def _read_utf8_bytes(path: Path) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MutationPlanningError(f"source is unreadable: {path}") from exc
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MutationPlanningError(f"unsupported encoding: {path}") from exc
    return data


def _decode_source_bytes(data: bytes) -> _DecodedFile:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MutationPlanningError("unsupported encoding in source bytes") from exc
    records: list[_LineRecord] = []
    endings: list[str] = []
    position = 0
    while position < len(text):
        end = position
        while end < len(text) and text[end] not in "\r\n":
            end += 1
        line_text = text[position:end]
        if end >= len(text):
            records.append(_LineRecord(text=line_text, ending=""))
            position = end
            break
        if text.startswith("\r\n", end):
            ending = "\r\n"
            position = end + 2
        elif text[end] == "\n":
            ending = "\n"
            position = end + 1
        else:
            ending = "\r"
            position = end + 1
        endings.append(ending)
        records.append(_LineRecord(text=line_text, ending=ending))
    if not records and not text:
        line_ending: Literal["cr", "crlf", "lf", "mixed", "none"] = "none"
        return _DecodedFile(
            records=(), line_ending=line_ending, has_final_newline=False
        )
    unique_endings = {ending for ending in endings if ending}
    if not unique_endings:
        line_ending = "none"
    elif unique_endings == {"\n"}:
        line_ending = "lf"
    elif unique_endings == {"\r"}:
        line_ending = "cr"
    elif unique_endings == {"\r\n"}:
        line_ending = "crlf"
    else:
        line_ending = "mixed"
    return _DecodedFile(
        records=tuple(records),
        line_ending=line_ending,
        has_final_newline=bool(records and records[-1].ending),
    )


def _encode_with_newline_policy(
    text: str, *, preferred_line_ending: str, has_final_newline: bool
) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
        has_final_newline = True
    ending = _NEWLINE_BY_LABEL.get(preferred_line_ending, "\n")
    if not normalized:
        return ending.encode("utf-8") if has_final_newline else b""
    encoded = ending.join(normalized.split("\n"))
    if has_final_newline:
        encoded += ending
    return encoded.encode("utf-8")


def _decode_postimage(postimage: bytes) -> _DecodedFile:
    return _decode_source_bytes(postimage)


def _build_mutation(
    *,
    kind: Literal["add", "delete", "move", "update"],
    source: _ValidatedTarget | None,
    target: _ValidatedTarget,
    postimage: bytes | None,
    decoded: _DecodedFile | None,
) -> PathMutation:
    if postimage is None:
        doc_family = _doc_family(target.relative_path)
        source_basename = _source_basename(target.relative_path)
        top_level_symbols: tuple[str, ...] = ()
        line_ending: Literal["cr", "crlf", "lf", "mixed", "none"] = "none"
        has_final_newline = False
    else:
        doc_family = _doc_family(target.relative_path)
        source_basename = _source_basename(target.relative_path)
        top_level_symbols = _top_level_symbols(
            target.relative_path, postimage.decode("utf-8")
        )
        if decoded is None:
            raise MutationPlanningError("decoded postimage metadata is missing")
        line_ending = decoded.line_ending
        has_final_newline = decoded.has_final_newline
    return PathMutation(
        kind=kind,
        target_relative_path=target.relative_path.as_posix(),
        source_relative_path=source.relative_path.as_posix() if source else None,
        target_absolute_path=str(target.physical_path),
        source_absolute_path=str(source.physical_path) if source else None,
        target_exists_before=target.exists,
        source_exists_before=source.exists if source else None,
        target_file_identity=target.file_identity,
        source_file_identity=source.file_identity if source else None,
        postimage_bytes=postimage,
        postimage_sha256=(
            hashlib.sha256(postimage).hexdigest() if postimage is not None else None
        ),
        doc_family=doc_family,
        source_basename=source_basename,
        top_level_symbols=top_level_symbols,
        line_ending=line_ending,
        has_final_newline=has_final_newline,
    )


def _doc_family(relative_path: Path) -> str | None:
    if (
        len(relative_path.parts) >= 2
        and relative_path.parts[0].lower() == "docs"
        and relative_path.suffix.lower() in _DOC_EXTENSIONS
    ):
        stem = relative_path.stem.strip()
        while True:
            updated = re.sub(
                r"(?i)(?:[-_ ]+v(?:ersion)?[-_ ]*\d+(?:\.\d+)*)$",
                "",
                stem,
            ).strip()
            if updated == stem:
                break
            stem = updated
        normalized = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        return normalized or relative_path.stem.lower()
    return None


def _source_basename(relative_path: Path) -> str | None:
    if relative_path.suffix.lower() not in _SOURCE_EXTENSIONS:
        return None
    basename = relative_path.name.lower()
    return None if basename in _RECURRING_BASENAMES else basename


def _top_level_symbols(relative_path: Path, text: str) -> tuple[str, ...]:
    suffix = relative_path.suffix.lower()
    if suffix not in _SOURCE_EXTENSIONS:
        return ()
    if suffix not in {".py", ".pyi"}:
        raise MutationPlanningError(
            f"no syntax-aware symbol parser for source extension: {suffix}"
        )
    try:
        module = ast.parse(text)
    except SyntaxError as exc:
        raise MutationPlanningError(
            "python source could not be parsed for symbols"
        ) from exc
    symbols: list[str] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
    return tuple(symbols)


def _remember_target(
    touched: list[str], seen_targets: set[str], relative_path: str
) -> None:
    if relative_path not in seen_targets:
        touched.append(relative_path)
        seen_targets.add(relative_path)


def _remember_operation_target(
    seen_operation_paths: dict[str, str], target: _ValidatedTarget
) -> None:
    key = target.file_identity or os.path.normcase(str(target.physical_path))
    previous = seen_operation_paths.get(key)
    relative_path = target.relative_path.as_posix()
    if previous is not None:
        raise MutationPlanningError(
            f"duplicate patch path collision: {relative_path} conflicts with {previous}"
        )
    seen_operation_paths[key] = relative_path
