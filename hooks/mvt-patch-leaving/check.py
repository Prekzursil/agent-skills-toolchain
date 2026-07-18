#!/usr/bin/env python3
r"""MVT patch-leaving detector for PostToolUse + Stop.

The Marginal Value Theorem metaphor is simple: before leaving the current work
"patch", check that its intended value actually landed.  This hook covers one
high-cost failure mode without turning every dirty worktree into a warning:

* ``posttool`` silently records only THIS TURN'S explicit Edit/Write/MultiEdit/
  NotebookEdit operations, real patch-application commands, and Git commit attempts.
* ``stop`` injects context only when a patch application is still known-failed;
  a direct edit is known-failed despite a change request + completion claim; or
  a generated patch artifact with real target headers was never applied despite
  a change request + completion claim; or the user explicitly requested a commit,
  a turn-owned change landed, and no successful later commit covered it.

False-positive controls are deliberate:

* Never runs ``git status`` and never asks for a commit.  Unrelated user changes
  and non-git directories are therefore irrelevant.  Commit warnings exist only
  when the user explicitly requested one.
* A .patch/.diff artifact requested as the deliverable is not an error.  Nor are
  ``git apply --check`` and ``patch --dry-run`` read-only checks.
* A later landed attempt for the same target resolves an earlier failure.
* Unknown outcomes stay silent; only explicit tool failures are actionable.
* State/transcript reads are byte/record bounded, state is TTL/count-pruned on
  each new session, and findings are scoped to the latest genuine human turn.

Dispatcher interface::

    check.py posttool   # PostToolUse; records state, emits nothing
    check.py stop       # Stop; may emit additionalContext

Inject-only, never blocks, and every path is FAIL-OPEN (exit 0).  Opt out with
``MVT_PATCH_LEAVING=off`` or a sibling ``.disabled`` file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
STATE_DIR = Path(
    os.environ.get(
        "MVT_PATCH_STATE_DIR",
        str(Path(tempfile.gettempdir()) / "mvt-patch-leaving"),
    )
)

MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024
MAX_STATE_BYTES = 256 * 1024
MAX_RECORDS = 128
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TARGETS = 16
STATE_TTL_SECONDS = 14 * 24 * 60 * 60
MAX_STATE_FILES = 256
MAX_STATE_SCAN = 512

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

_PATCH_APPLY = re.compile(
    r"(?:^|[;&|]\s*)(?:"
    r"git(?:\s+-\S+)*\s+apply\b|"
    r"(?:[^\s;&|]+[\\/])?patch(?:\.exe)?\b|"
    r"apply_patch\b"
    r")",
    re.IGNORECASE | re.MULTILINE,
)
_PATCH_DRY_RUN = re.compile(
    r"\bgit(?:\s+-\S+)*\s+apply\b[^\r\n;&|]*(?:--check|--stat|--numstat|--summary)\b"
    r"|\bpatch(?:\.exe)?\b[^\r\n;&|]*--dry-run\b",
    re.IGNORECASE,
)
_SHELL_TOKEN = r'(?:"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s;&|]+)'
_GIT_GLOBAL_OPTIONS = (
    rf"(?:(?:-C|-c)\s+{_SHELL_TOKEN}\s+|"
    rf"--(?:git-dir|work-tree)(?:={_SHELL_TOKEN}|\s+{_SHELL_TOKEN})\s+|"
    r"--no-pager\s+)*"
)
_GIT_COMMIT = re.compile(
    rf"(?:^|[;&|]\s*)git\s+{_GIT_GLOBAL_OPTIONS}commit\b",
    re.IGNORECASE | re.MULTILINE,
)
_GIT_COMMIT_DRY_RUN = re.compile(
    r"\bgit\b[^\r\n;&|]{0,256}\bcommit\b[^\r\n;&|]*"
    r"(?:^|[ \t])--dry-run(?=$|[ \t;&|])",
    re.IGNORECASE,
)
_GIT_COMMIT_NOOP = re.compile(
    r"\b(?:nothing\s+to\s+commit|no\s+changes\s+added\s+to\s+commit|"
    r"nothing\s+added\s+to\s+commit)\b",
    re.IGNORECASE,
)
_PATCH_TARGET = re.compile(
    r"^(?:\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*|"
    r"(?:---|\+\+\+)\s+(?:[ab][\\/])?)([^\t\r\n]+)",
    re.IGNORECASE | re.MULTILINE,
)
_PATCH_FILE_TOKEN = re.compile(
    r'(?:"([^"\r\n]+\.(?:patch|diff))"|\'([^\'\r\n]+\.(?:patch|diff))\'|'
    r"([^\s;&|<>]+\.(?:patch|diff)))",
    re.IGNORECASE,
)
_FAILED_PATCH_TARGET = re.compile(
    r"patch\s+failed\s*:\s*([^\r\n]+?)(?::\d+\b)"
    r"|error\s*:\s*([^\r\n]+?)\s*:\s*patch\b",
    re.IGNORECASE,
)

_FAILURE = re.compile(
    r"(?:\b(?:invalid\s+context|patch\s+failed|hunk\s+#?\d*\s+failed|"
    r"does\s+not\s+apply|failed\s+to\s+(?:apply|edit|write|replace)|"
    r"old_string\s+(?:was\s+)?not\s+found|no\s+match\s+found|"
    r"permission\s+denied|access\s+is\s+denied|operation\s+not\s+permitted|"
    r"file\s+not\s+found|no\s+such\s+file|rejected\s+hunk|"
    r"no\s+(?:changes?|replacements?)\s+(?:were\s+)?made)\b"
    r"|(?:fatal|exception|error)\s*:|traceback\s*\()",
    re.IGNORECASE,
)
_BENIGN_PATCH = re.compile(
    r"\b(?:already\s+applied|patch\s+is\s+empty|nothing\s+to\s+apply)\b",
    re.IGNORECASE,
)
_SUCCESS = re.compile(
    r"\b(?:success(?:ful|fully)?|updated|written|created|applied|done|completed)\b",
    re.IGNORECASE,
)

_CHANGE_INTENT = re.compile(
    r"\b(?:apply|implement|fix|update|change|modify|edit|write|add|remove|"
    r"delete|rename|replace|wire|build|create)\b",
    re.IGNORECASE,
)
_NEGATED_CHANGE = re.compile(
    r"\b(?:do\s+not|don't|without)\s+(?:apply(?:ing)?|implement(?:ing)?|fix(?:ing)?|"
    r"updat(?:e|ing)|chang(?:e|ing)|modif(?:y|ying)|edit(?:ing)?|writ(?:e|ing)|"
    r"add(?:ing)?|remov(?:e|ing)|delet(?:e|ing)|renam(?:e|ing)|replac(?:e|ing)|"
    r"wir(?:e|ing)|build(?:ing)?|creat(?:e|ing))\b",
    re.IGNORECASE,
)
_READ_ONLY_INTENT = re.compile(
    r"\bread[- ]only\b|\b(?:how|whether)\s+to\s+(?:apply|implement|fix|"
    r"update|change|modify|edit|write|add|remove|delete|rename|replace|wire|build|create)\b"
    r"|\bcheck\s+whether\b|\bplan\s+only\b",
    re.IGNORECASE,
)
_COMPLETION = re.compile(
    r"\b(?:implemented|fixed|updated|changed|modified|edited|wrote|written|"
    r"added|removed|deleted|renamed|replaced|wired|built|created|applied|"
    r"completed|done|now\s+works?|landed|shipped)\b",
    re.IGNORECASE,
)
_ARTIFACT_REQUEST = re.compile(
    r"\b(?:create|write|generate|produce|prepare|save|export|provide|return|show|share)\b"
    r"[^\r\n]{0,100}\b(?:patch|diff|\.patch|\.diff)\b"
    r"|\b(?:patch|diff)\s+(?:file|artifact|for\s+review)\b"
    r"|\.(?:patch|diff)\b[^\r\n]{0,80}\b(?:artifact|review|share|send)\b",
    re.IGNORECASE,
)
_ARTIFACT_READ_ONLY = re.compile(
    r"\bread[- ]only\b|\bdry[- ]run\b|"
    r"\b(?:do\s+not|don't)\s+apply\b|\bwithout\s+applying\b",
    re.IGNORECASE,
)
_COMMIT_INTENT = re.compile(
    r"^\s*(?:please\s+)?commit\b|"
    r"\b(?:and|then|also|please)\s+commit\b|"
    r"\bcommit\s+(?:the\s+|these\s+|this\s+|all\s+)?"
    r"(?:changes?|work|files?|it|them)\b|"
    r"\b(?:create|make)\s+(?:a\s+)?commit\b|"
    r"(?:^|[.!?]\s+)commit\b",
    re.IGNORECASE | re.MULTILINE,
)
_NO_COMMIT_INTENT = re.compile(
    r"\b(?:do\s+not|don't)\s+commit\b|\bwithout\s+committing\b|"
    r"\bleave\s+(?:the\s+)?(?:changes?|work)\s+uncommitted\b",
    re.IGNORECASE,
)
_COMMIT_MESSAGE_LEAD = re.compile(
    r"^\s*(?:please\s+)?commit\s+message\b",
    re.IGNORECASE,
)


def _disabled() -> bool:
    try:
        return DISABLED.exists() or os.environ.get(
            "MVT_PATCH_LEAVING", ""
        ).lower() in {"off", "0", "false"}
    except Exception:
        return False


def _safe_session(session_id: str) -> str:
    raw = str(session_id or "default")
    visible = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:32] or "default"
    digest = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:12]
    return f"{visible}-{digest}"


def _state_file(session_id: str) -> Path:
    return STATE_DIR / f"{_safe_session(session_id)}.jsonl"


def _prune_state_dir(now: float | None = None) -> None:
    """Bound cross-session state by age and count with a capped directory scan."""
    try:
        if not STATE_DIR.is_dir():
            return
        if now is None:
            import time

            now = time.time()
        survivors: list[tuple[float, Path]] = []
        scanned = 0
        with os.scandir(STATE_DIR) as entries:
            for entry in entries:
                if scanned >= MAX_STATE_SCAN:
                    break
                scanned += 1
                if not entry.name.endswith(".jsonl") or not entry.is_file(
                    follow_symlinks=False
                ):
                    continue
                try:
                    modified = entry.stat(follow_symlinks=False).st_mtime
                    path = Path(entry.path)
                    if now - modified > STATE_TTL_SECONDS:
                        path.unlink(missing_ok=True)
                    else:
                        survivors.append((modified, path))
                except OSError:
                    continue
        if len(survivors) > MAX_STATE_FILES:
            survivors.sort(key=lambda item: item[0])
            for _, path in survivors[: len(survivors) - MAX_STATE_FILES]:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue
    except Exception:
        pass  # retention is advisory; cleanup errors never affect the hook


def _append_record(session_id: str, record: dict[str, Any]) -> None:
    """Append one small state record.  Storage failures deliberately propagate to main."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_file(session_id)
    if not path.exists():
        _prune_state_dir()  # once per new session, not on every high-frequency edit
    line = json.dumps(record, ensure_ascii=True, separators=(",", ":"))[:8192]
    if path.exists() and path.stat().st_size > MAX_STATE_BYTES:
        # Keep only the newest bounded tail.  A torn/partial first line is ignored by
        # _load_records; this state is advisory and therefore safely fail-open.
        with path.open("rb") as fh:
            fh.seek(max(0, path.stat().st_size - MAX_STATE_BYTES // 2))
            tail = fh.read(MAX_STATE_BYTES // 2)
        newline = tail.find(b"\n")
        if newline >= 0:
            tail = tail[newline + 1 :]
        path.write_bytes(tail)
    with path.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(line + "\n")


def _load_records(session_id: str) -> list[dict[str, Any]]:
    """Read at most MAX_STATE_BYTES and return at most MAX_RECORDS valid records."""
    path = _state_file(session_id)
    if not path.is_file():
        return []
    size = path.stat().st_size
    with path.open("rb") as fh:
        start = max(0, size - MAX_STATE_BYTES)
        fh.seek(start)
        raw = fh.read(MAX_STATE_BYTES)
    if start:
        newline = raw.find(b"\n")
        raw = raw[newline + 1 :] if newline >= 0 else b""
    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out[-MAX_RECORDS:]


def _tail_events(transcript_path: str) -> list[dict[str, Any]]:
    path = Path(transcript_path)
    if not path.is_file():
        return []
    size = path.stat().st_size
    with path.open("rb") as fh:
        start = max(0, size - MAX_TRANSCRIPT_BYTES)
        fh.seek(start)
        raw = fh.read(MAX_TRANSCRIPT_BYTES)
    if start:
        newline = raw.find(b"\n")
        raw = raw[newline + 1 :] if newline >= 0 else b""
    events: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return " ".join(parts)


def _is_human(event: dict[str, Any]) -> bool:
    message = event.get("message") or {}
    if not isinstance(message, dict):
        return False
    role = message.get("role") or event.get("role") or event.get("type")
    if role != "user":
        return False
    content = message.get("content", event.get("content"))
    if isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    ):
        return False
    return bool(_content_text(content).strip())


def _assistant_text(event: dict[str, Any]) -> str:
    message = event.get("message") or {}
    if not isinstance(message, dict):
        return ""
    role = message.get("role") or event.get("role")
    if not (role == "assistant" or event.get("type") == "assistant"):
        return ""
    return _content_text(message.get("content", event.get("content"))).strip()


def _turn_context(transcript_path: str) -> tuple[str, str, str]:
    """Return (turn key, latest genuine user request, latest assistant text)."""
    events = _tail_events(transcript_path)
    last_human = -1
    user_text = ""
    turn_seed = ""
    for index, event in enumerate(events):
        if _is_human(event):
            last_human = index
            message = event.get("message") or {}
            user_text = _content_text(message.get("content", event.get("content")))
            turn_seed = str(event.get("uuid") or event.get("id") or "")
    if last_human < 0:
        return "", "", ""
    if not turn_seed:
        turn_seed = hashlib.sha256(
            (str(last_human) + "\0" + user_text).encode("utf-8", "replace")
        ).hexdigest()[:24]
    final_text = ""
    for event in events[last_human + 1 :]:
        text = _assistant_text(event)
        if text:
            final_text = text
    return turn_seed[:80], user_text.strip(), final_text.strip()


def _target_key(path_value: Any, cwd: str) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        return ""
    path = Path(os.path.expandvars(os.path.expanduser(path_value.strip().strip('"'))))
    if not path.is_absolute():
        path = Path(cwd) / path
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return ""


def _direct_targets(tool_input: dict[str, Any], cwd: str) -> list[str]:
    candidates: list[Any] = []
    for key in ("file_path", "notebook_path", "path"):
        if tool_input.get(key):
            candidates.append(tool_input[key])
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits[:MAX_TARGETS]:
            if isinstance(edit, dict):
                candidates.append(edit.get("file_path") or edit.get("path"))
    out: list[str] = []
    for candidate in candidates:
        target = _target_key(candidate, cwd)
        if target and target not in out:
            out.append(target)
    return out[:MAX_TARGETS]


def _result_value(data: dict[str, Any]) -> Any:
    if "tool_result" in data:
        return data.get("tool_result")
    return data.get("tool_response")


def _result_text(value: Any) -> str:
    if isinstance(value, str):
        return value[:16384]
    try:
        return json.dumps(value, ensure_ascii=True, default=str)[:16384]
    except Exception:
        return str(value)[:16384]


def _result_flags(value: Any) -> tuple[bool, bool, str]:
    """Return (explicit failure, explicit success, bounded textual representation)."""
    text = _result_text(value)
    failed = False
    succeeded = False
    if isinstance(value, dict):
        if value.get("is_error") is True or value.get("success") is False:
            failed = True
        if value.get("error") not in (None, "", False):
            failed = True
        code = value.get("exit_code", value.get("returncode"))
        if isinstance(code, int):
            failed = failed or code != 0
            succeeded = succeeded or code == 0
        if value.get("success") is True or value.get("is_error") is False:
            succeeded = True
    if not _BENIGN_PATCH.search(text) and _FAILURE.search(text):
        failed = True
    if _SUCCESS.search(text):
        succeeded = True
    return failed, succeeded, text


def _read_small_text(path: str) -> str | None:
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size > MAX_FILE_BYTES:
        return None
    return file_path.read_text(encoding="utf-8", errors="replace")


def _verify_direct_landed(
    tool_name: str, tool_input: dict[str, Any], targets: list[str]
) -> bool:
    if not targets:
        return False
    if tool_name == "Write" and isinstance(tool_input.get("content"), str):
        body = _read_small_text(targets[0])
        return body is not None and body == tool_input["content"]
    if tool_name == "Edit":
        new = tool_input.get("new_string")
        if isinstance(new, str):
            body = _read_small_text(targets[0])
            return body is not None and new in body
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if isinstance(edits, list) and edits:
            body = _read_small_text(targets[0])
            expected = [
                edit.get("new_string")
                for edit in edits[:MAX_TARGETS]
                if isinstance(edit, dict) and isinstance(edit.get("new_string"), str)
            ]
            return body is not None and bool(expected) and all(x in body for x in expected)
    return False


def _add_patch_header_targets(text: str, cwd: str, out: list[str]) -> None:
    """Add normalized target paths from bounded unified/apply_patch headers."""
    for match in _PATCH_TARGET.finditer(text[:131072]):
        raw = match.group(1).strip().strip('"')
        if raw in {"/dev/null", "NUL", "nul"}:
            continue
        target = _target_key(raw, cwd)
        if target and target not in out:
            out.append(target)
        if len(out) >= MAX_TARGETS:
            break


def _patch_targets(command: str, result_text: str, cwd: str) -> list[str]:
    out: list[str] = []
    _add_patch_header_targets(command, cwd, out)

    # A normal ``git apply change.patch`` command does not carry headers inline.
    # Read only explicitly referenced, small patch artifacts and only to recover
    # their target paths.  The artifact's mere existence is never a warning.
    for match in _PATCH_FILE_TOKEN.finditer(command[:16384]):
        patch_name = next((group for group in match.groups() if group), "")
        patch_path = _target_key(patch_name, cwd)
        body = _read_small_text(patch_path) if patch_path else None
        if body:
            _add_patch_header_targets(body, cwd, out)
        if len(out) >= MAX_TARGETS:
            break

    # Tool errors often name the failed target even when the patch file is gone.
    for match in _FAILED_PATCH_TARGET.finditer(result_text[:16384]):
        raw = next((group for group in match.groups() if group), "")
        target = _target_key(raw.strip().strip('"'), cwd)
        if target and target not in out:
            out.append(target)
        if len(out) >= MAX_TARGETS:
            break
    return out


def _artifact_record(
    targets: list[str], turn: str, tool_name: str, cwd: str
) -> dict[str, Any] | None:
    """Return a pending artifact record when a landed .patch/.diff has real targets."""
    artifacts = [
        target
        for target in targets
        if Path(target).suffix.lower() in {".patch", ".diff"}
    ][:MAX_TARGETS]
    if not artifacts:
        return None
    patch_targets: list[str] = []
    for artifact in artifacts:
        body = _read_small_text(artifact)
        if body:
            _add_patch_header_targets(body, cwd, patch_targets)
        if len(patch_targets) >= MAX_TARGETS:
            break
    if not patch_targets:
        return None  # headerless/oversized artifact: conservative silence
    return {
        "v": 1,
        "turn": turn,
        "kind": "artifact",
        "status": "pending",
        "targets": patch_targets,
        "artifacts": artifacts,
        "tool": tool_name,
    }


def _record_posttool(data: dict[str, Any], turn: str) -> None:
    tool_name = str(data.get("tool_name") or "")
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return
    cwd = str(data.get("cwd") or os.getcwd())
    failed, succeeded, result_text = _result_flags(_result_value(data))

    session_id = str(data.get("session_id") or "default")

    if tool_name in EDIT_TOOLS:
        targets = _direct_targets(tool_input, cwd)
        if failed:
            status = "failed"
        elif _verify_direct_landed(tool_name, tool_input, targets) or succeeded:
            status = "landed"
        else:
            status = "unknown"
        artifact = (
            _artifact_record(targets, turn, tool_name, cwd)
            if status == "landed"
            else None
        )
        record = artifact or {
            "v": 1,
            "turn": turn,
            "kind": "edit",
            "status": status,
            "targets": targets,
            "tool": tool_name,
        }
    elif tool_name in SHELL_TOOLS:
        command = str(tool_input.get("command") or "")
        if not command:
            return
        actions: list[tuple[int, dict[str, Any]]] = []
        commit_match = _GIT_COMMIT.search(command)
        if commit_match and not _GIT_COMMIT_DRY_RUN.search(command):
            commit_failed = failed or bool(_GIT_COMMIT_NOOP.search(result_text))
            actions.append(
                (
                    commit_match.start(),
                    {
                        "v": 1,
                        "turn": turn,
                        "kind": "commit",
                        "status": "failed" if commit_failed else "landed",
                        "targets": [],
                        "tool": tool_name,
                    },
                )
            )
        patch_match = _PATCH_APPLY.search(command)
        if patch_match and not _PATCH_DRY_RUN.search(command):
            # A completed patch command with no explicit failure is treated as landed.
            # This intentionally prefers silence over a speculative false positive.
            actions.append(
                (
                    patch_match.start(),
                    {
                        "v": 1,
                        "turn": turn,
                        "kind": "patch",
                        "status": "failed" if failed else "landed",
                        "targets": _patch_targets(command, result_text, cwd),
                        "tool": tool_name,
                    },
                )
            )
        if not actions:
            return
        for _, action in sorted(actions, key=lambda item: item[0]):
            _append_record(session_id, action)
        return
    else:
        return
    _append_record(session_id, record)


def _resolved(records: list[dict[str, Any]], failed_index: int) -> bool:
    failed = records[failed_index]
    targets = {str(x) for x in failed.get("targets") or [] if x}
    for later in records[failed_index + 1 :]:
        if later.get("status") != "landed" or later.get("kind") not in {
            "patch",
            "edit",
        }:
            continue
        later_targets = {str(x) for x in later.get("targets") or [] if x}
        if targets and targets.intersection(later_targets):
            return True
        if not targets:
            return True  # targetless failure: any later landed attempt may be the recovery
    return False


def _artifact_resolved(records: list[dict[str, Any]], artifact_index: int) -> bool:
    artifact_targets = {
        str(target) for target in records[artifact_index].get("targets") or [] if target
    }
    if not artifact_targets:
        return True  # headerless artifacts are never actionable
    for later in records[artifact_index + 1 :]:
        if later.get("status") != "landed" or later.get("kind") not in {
            "patch",
            "edit",
        }:
            continue
        later_targets = {
            str(target) for target in later.get("targets") or [] if target
        }
        if artifact_targets.intersection(later_targets):
            return True
    return False


def _display_targets(records: list[dict[str, Any]]) -> str:
    shown: list[str] = []
    for record in records:
        for target in record.get("targets") or []:
            name = Path(str(target)).name or str(target)
            if name and name not in shown:
                shown.append(name)
            if len(shown) >= 6:
                break
    return ", ".join(shown) if shown else "target not identified"


def _display_artifacts(records: list[dict[str, Any]]) -> str:
    shown: list[str] = []
    for record in records:
        for artifact in record.get("artifacts") or []:
            name = Path(str(artifact)).name or str(artifact)
            if name and name not in shown:
                shown.append(name)
    artifact_text = ", ".join(shown[:4]) if shown else "patch artifact"
    return f"{artifact_text} -> {_display_targets(records)}"


def _has_change_intent(user_text: str) -> bool:
    cleaned = _NEGATED_CHANGE.sub("", user_text)
    return bool(_CHANGE_INTENT.search(cleaned)) and not bool(
        _READ_ONLY_INTENT.search(cleaned)
    )


def _explicit_artifact_request(user_text: str) -> bool:
    return bool(
        _ARTIFACT_REQUEST.search(user_text) or _ARTIFACT_READ_ONLY.search(user_text)
    )


def _has_commit_intent(user_text: str) -> bool:
    if _NO_COMMIT_INTENT.search(user_text):
        return False
    lead = _COMMIT_MESSAGE_LEAD.match(user_text)
    candidate = user_text[lead.end() :] if lead else user_text
    return bool(_COMMIT_INTENT.search(candidate))


def _uncommitted_change(
    records: list[dict[str, Any]], user_text: str
) -> dict[str, Any] | None:
    """Return the last landed turn-owned change when an explicit commit is still owed."""
    if not _has_commit_intent(user_text):
        return None
    last_change_index = -1
    for index, record in enumerate(records):
        if record.get("status") == "landed" and record.get("kind") in {
            "edit",
            "patch",
        }:
            last_change_index = index
    if last_change_index < 0:
        return None  # do not attribute unrelated/pre-existing work to this turn
    if any(
        record.get("kind") == "commit" and record.get("status") == "landed"
        for record in records[last_change_index + 1 :]
    ):
        return None
    return records[last_change_index]


def _stop_message(
    records: list[dict[str, Any]], user_text: str, final_text: str
) -> str:
    unresolved: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if record.get("status") != "failed" or _resolved(records, index):
            continue
        unresolved.append(record)
    patch_failures = [record for record in unresolved if record.get("kind") == "patch"]
    edit_failures = [record for record in unresolved if record.get("kind") == "edit"]
    pending_artifacts = [
        record
        for index, record in enumerate(records)
        if record.get("kind") == "artifact"
        and record.get("status") == "pending"
        and not _artifact_resolved(records, index)
    ]
    uncommitted = _uncommitted_change(records, user_text)

    parts: list[str] = []
    if patch_failures:
        parts.append(
            "an unapplied patch attempt is still unresolved "
            f"({_display_targets(patch_failures)})"
        )
    if (
        edit_failures
        and _has_change_intent(user_text)
        and bool(_COMPLETION.search(final_text))
    ):
        parts.append(
            "the intended change did not land despite the completion claim "
            f"({_display_targets(edit_failures)})"
        )
    if (
        pending_artifacts
        and not patch_failures
        and _has_change_intent(user_text)
        and bool(_COMPLETION.search(final_text))
        and not _explicit_artifact_request(user_text)
    ):
        parts.append(
            "a generated patch artifact appears left unapplied "
            f"({_display_artifacts(pending_artifacts)})"
        )
    if uncommitted is not None:
        parts.append(
            "an uncommitted intended change remains after the explicit commit request "
            f"({_display_targets([uncommitted])})"
        )
    if not parts:
        return ""
    return (
        "[mvt-patch-leaving] Before leaving this work patch, verify the actual "
        + "; and ".join(parts)
        + ". Re-apply or repair the intended delta, then inspect the named target(s). "
        "This is an inject-only reminder; no commit is inferred unless the user explicitly "
        "requested it, and unrelated working-tree changes were not inspected."
    )


def _handle_stop(data: dict[str, Any], turn: str, user_text: str, final_text: str) -> None:
    session_id = str(data.get("session_id") or "default")
    records = [
        record
        for record in _load_records(session_id)
        if str(record.get("turn") or "") == turn
    ]
    if not records or any(record.get("kind") == "warned" for record in records):
        return
    message = _stop_message(records, user_text, final_text)
    if not message:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": message,
                }
            }
        )
    )
    _append_record(
        session_id,
        {"v": 1, "turn": turn, "kind": "warned", "status": "landed", "targets": []},
    )


def main(argv: list[str] | None = None) -> int:
    """Run one hook phase.  Any exception is swallowed: this hook is always fail-open."""
    try:
        if _disabled():
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if not isinstance(data, dict):
            return 0
        mode = str((argv or [""])[0] or "").lower()
        if not mode:
            event = str(data.get("hook_event_name") or "").lower()
            mode = "posttool" if event == "posttooluse" else event
        if mode in {"posttooluse", "post-tool", "post_tool"}:
            mode = "posttool"
        transcript_path = str(data.get("transcript_path") or "")
        turn, user_text, final_text = _turn_context(transcript_path)
        if not turn:
            return 0  # no reliable per-turn scope -> conservative silence
        if mode == "posttool":
            _record_posttool(data, turn)
        elif mode == "stop":
            if data.get("stop_hook_active"):
                return 0
            _handle_stop(data, turn, user_text, final_text)
    except BaseException:
        pass  # fail-open: hook bugs, I/O errors, and malformed payloads never block Claude
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
