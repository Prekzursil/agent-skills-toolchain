from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .models import HookEvent, HookResult
    from .workspace_index import (
        MutationOp,
        MutationPlan as IndexMutationPlan,
        WorkspaceIndex,
        WorkspaceIndexFailure,
        resolve_repo_identity,
    )
    from .workspace_mutation import (
        MutationPlanningError,
        PathMutation,
        ResolvedTarget,
        build_mutation_plan,
    )
except ImportError:  # pragma: no cover
    from models import HookEvent, HookResult
    from workspace_index import (
        MutationOp,
        MutationPlan as IndexMutationPlan,
        WorkspaceIndex,
        WorkspaceIndexFailure,
        resolve_repo_identity,
    )
    from workspace_mutation import (
        MutationPlanningError,
        PathMutation,
        ResolvedTarget,
        build_mutation_plan,
    )


_MUTATION_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "apply_patch"})
_SHELL_TOOLS = frozenset({"PowerShell", "Bash", "Shell"})
_POST_EVENTS = frozenset({"PostToolUse", "PostToolUseFailure", "PermissionDenied"})
_UNIDENTIFIED_SESSION_IDS = frozenset({"", "unknown", "none", "null"})
_VCS_METADATA_DIRS = frozenset({".git", ".hg", ".svn"})
_WINDOWS_DEVICE_PREFIX = ("\\\\.\\", "\\\\?\\", "//./", "//?/")
_WINDOWS_WILDCARDS = frozenset({"*", "?"})
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "COM¹",
        "COM²",
        "COM³",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
        "LPT¹",
        "LPT²",
        "LPT³",
    }
)
_SHELL_FORBIDDEN_CHARS = frozenset(
    {'"', "`", "$", "@", "{", "}", "[", "]", "(", ")", ";", "|", ">", "<", "#", "%"}
)
_UNICODE_LINE_SEPARATORS = frozenset({"\u2028", "\u2029"})
_ALLOWED_SHELL_PAYLOAD_KEYS = frozenset(
    {
        "cmd",
        "command",
        "workdir",
        "sandbox_permissions",
        "additional_permissions",
        "justification",
        "prefix_rule",
    }
)
_LITERAL_RG_METACHARS = frozenset({"\\", ".", "^", "$", "*", "+", "?", "[", "]", "{", "}", "(", ")", "|"})
_TRUSTED_CERTUTIL_NAME = "certutil.exe"
_SHELL_GRAMMAR_CONTEXT = (
    "Allowed PowerShell grammar only: & '<absolute pinned exe>' <exact approved arguments>.",
    "Allowed executables: pinned git, pinned rg, and System32 certutil only.",
    "Allowed forms: rg --no-config --files|--line-number --no-heading --color=never --regexp <literal>; git status|diff|show|log|rev-parse with the exact read-only flags; certutil -hashfile <repo file> SHA256.",
)
_SAFE_GIT_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_MAX_SHELL_COMMAND_CHARS = 4096
_MAX_MUTATION_PAYLOAD_BYTES = 1_000_000
_OUTCOME_ALLOWED_TERMINAL = frozenset({"completed", "invalidated", "resolved", "needs_refresh"})
_OUTCOME_UNKNOWN_TERMINAL = frozenset({"missing", "unknown"})


@dataclass(frozen=True)
class _ShellToken:
    value: str
    quoted: bool


@dataclass(frozen=True)
class _ShellCommand:
    executable: Path
    arguments: tuple[_ShellToken, ...]


class _BlockWorkspace(Exception):
    def __init__(
        self,
        reason_code: str,
        *,
        additional_context: list[str] | None = None,
    ):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.additional_context = list(additional_context or [])


def _identified_session(session_id: str) -> bool:
    return str(session_id or "").strip().lower() not in _UNIDENTIFIED_SESSION_IDS


def _normcase_path(path: Path) -> str:
    return os.path.normcase(str(path))


def _commonpath_contains(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath([_normcase_path(root), _normcase_path(candidate)]) == _normcase_path(root)
    except ValueError:
        return False


def _has_ads(raw: str) -> bool:
    if raw.startswith(("\\\\", "//")):
        return ":" in raw[2:]
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        return ":" in raw[3:]
    return ":" in raw


def _is_windows_drive_relative(raw: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:(?![\\/])", raw))


def _has_reserved_device_component(raw: str) -> bool:
    for component in re.split(r"[\\/]+", raw):
        if not component or component in {".", ".."}:
            continue
        if re.fullmatch(r"[A-Za-z]:", component):
            continue
        normalized = component.rstrip(" .")
        if not normalized:
            continue
        stem = normalized.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            return True
    return False


def _has_trailing_dot_space_component(raw: str) -> bool:
    for component in re.split(r"[\\/]+", raw):
        if not component or re.fullmatch(r"[A-Za-z]:", component):
            continue
        if component.endswith((" ", ".")):
            return True
    return False


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


class WorkspaceIntegrityModule:
    """Fail-closed orchestration over workspace_mutation + workspace_index."""

    name = "workspace_integrity"
    failure_policy = "closed"

    def __init__(
        self,
        state_root: Path | str | None = None,
        *,
        git_executable: Path | str | None = None,
        rg_executable: Path | str | None = None,
        certutil_executable: Path | str | None = None,
    ):
        self.state_root = Path(state_root) if state_root else Path(".")
        self._deadline_monotonic: float | None = None
        self.git_executable = self._resolve_pinned_executable(
            candidate=git_executable,
            which_name="git",
            required_name="git.exe",
        )
        self.rg_executable = self._resolve_pinned_executable(
            candidate=rg_executable,
            which_name="rg",
            required_name="rg.exe",
        )
        self.certutil_executable = self._resolve_certutil_executable(certutil_executable)

    @staticmethod
    def applies(event: HookEvent) -> bool:
        if event.event == "SessionStart":
            return True
        if event.event == "PreToolUse":
            return event.tool.name in (_MUTATION_TOOLS | _SHELL_TOOLS | {"NotebookEdit"})
        if event.event in _POST_EVENTS:
            return event.tool.name in _MUTATION_TOOLS
        return False

    @staticmethod
    def failure_result(
        event: HookEvent,
        phase: str,
        *,
        reason_code: str = "workspace_integrity_unknown",
        additional_context: list[str] | None = None,
    ) -> HookResult:
        context = [f"Workspace integrity is unknown during {phase}."]
        if additional_context:
            context.extend(additional_context)
        return HookResult(
            status=f"FAILED:hook-{event.event.lower()}",
            action="block",
            reason_code=reason_code,
            additional_context=context,
            continuation=None,
        )

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        self._deadline_monotonic = deadline_monotonic

    def run(self, event: HookEvent) -> HookResult:
        try:
            return self._run(event)
        except _BlockWorkspace as exc:
            return HookResult.success(
                action="block",
                reason_code=exc.reason_code,
                additional_context=exc.additional_context,
            )
        except WorkspaceIndexFailure as exc:
            return self.failure_result(
                event,
                "workspace index",
                reason_code=exc.code,
                additional_context=[f"{exc.code}: {exc}"],
            )
        except Exception as exc:
            return self.failure_result(
                event,
                "execution",
                additional_context=[f"{type(exc).__name__}: {exc}"],
            )

    def cancel_pre(self, event: HookEvent) -> bool:
        if event.event != "PreToolUse" or event.tool.name not in _MUTATION_TOOLS:
            return False
        if not _identified_session(event.session_id):
            return False
        tool_id = str(event.tool.id or "").strip()
        if not tool_id:
            return False
        try:
            index = self._index_for_event(event)
        except WorkspaceIndexFailure:
            return False
        return index.resolve(owner=self._owner(event), operation_id=tool_id)

    def _run(self, event: HookEvent) -> HookResult:
        self._check_deadline()
        if event.event == "SessionStart":
            return self._on_session_start(event)
        if event.event == "PreToolUse":
            return self._on_pre_tool_use(event)
        if event.event in _POST_EVENTS:
            return self._on_post_event(event)
        return HookResult.success()

    def _on_session_start(self, event: HookEvent) -> HookResult:
        self._require_identified_session(event)
        index = self._index_for_event(event, allow_nonrepo=True)
        if index is None:
            return HookResult.success()
        self._ensure_fresh(index)
        return HookResult.success()

    def _on_pre_tool_use(self, event: HookEvent) -> HookResult:
        if event.tool.name == "NotebookEdit":
            self._block("workspace_notebook_edit_blocked")
        self._require_identified_session(event)
        self._require_tool_id(event)
        if event.tool.name in _SHELL_TOOLS:
            self._check_shell(event)
            return HookResult.success()
        if event.tool.name not in _MUTATION_TOOLS:
            return HookResult.success()
        index = self._index_for_event(event)
        self._ensure_fresh(index)
        self._check_mutation_payload_size(event.tool.input)
        base_dir = self._canonical_existing_path(Path(event.cwd), require_directory=True)
        try:
            plan = build_mutation_plan(
                tool_name=event.tool.name,
                payload=event.tool.input,
                owner=self._owner(event),
                tool_use_id=str(event.tool.id).strip(),
                repo_root=index.repo.repo_root,
                base_dir=base_dir,
                resolve_target=self._planning_resolve_target,
                policy="workspace_strict",
                line_ending_mode="preserve",
            )
        except MutationPlanningError as exc:
            self._block(self._planning_reason(event.tool.name, exc))
        self._reserve(index, self._index_plan(plan))
        return HookResult.success()

    def _on_post_event(self, event: HookEvent) -> HookResult:
        if event.tool.name not in _MUTATION_TOOLS:
            return HookResult.success()
        if not _identified_session(event.session_id):
            return self.failure_result(
                event,
                "post reconciliation",
                additional_context=["Session identity is missing for the terminal event."],
            )
        operation_id = str(event.tool.id or "").strip()
        if not operation_id:
            return self.failure_result(
                event,
                "post reconciliation",
                additional_context=["Tool id is missing for the terminal event."],
            )
        try:
            index = self._index_for_event(event)
        except WorkspaceIndexFailure as exc:
            return self.failure_result(
                event,
                "post index construction",
                additional_context=[f"{exc.code}: {exc}"],
            )
        owner = self._owner(event)
        try:
            if event.event == "PostToolUse":
                outcome = self._normalize_post_outcome(
                    index.finalize_success(owner=owner, operation_id=operation_id)
                )
            elif event.event == "PermissionDenied":
                outcome = self._normalize_post_outcome(
                    index.resolve(owner=owner, operation_id=operation_id)
                )
            else:
                outcome = self._normalize_post_outcome(
                    index.mark_needs_refresh(
                        owner=owner,
                        operation_id=operation_id,
                        reason=f"{event.event}: {event.tool.name}",
                    )
                )
        except WorkspaceIndexFailure as exc:
            return self.failure_result(
                event,
                "post reconciliation",
                additional_context=[f"{exc.code}: {exc}"],
            )
        if outcome in _OUTCOME_ALLOWED_TERMINAL:
            return HookResult.success()
        if outcome in _OUTCOME_UNKNOWN_TERMINAL:
            return self.failure_result(
                event,
                "post reconciliation",
                additional_context=[
                    f"Reservation state could not be reconciled for {owner}/{operation_id}."
                ],
            )
        return self.failure_result(
            event,
            "post reconciliation",
            additional_context=[f"Unexpected reservation outcome {outcome!r} for {owner}/{operation_id}."],
        )

    def _check_shell(self, event: HookEvent) -> None:
        if event.tool.name != "PowerShell":
            self._shell_block("workspace_shell_transport", "Only the PowerShell tool transport is accepted.")
        if event.provider != "codex":
            self._shell_block("workspace_shell_provider", "Only codex-owned shell events are accepted.")
        if event.permission_mode != "workspace-write":
            self._shell_block("workspace_shell_permission", "Shell requires exact workspace-write permission mode.")
        payload = event.tool.input
        if not isinstance(payload, dict):
            self._shell_block("workspace_shell_invalid", "Shell payload must be an object.")
        if set(payload) - _ALLOWED_SHELL_PAYLOAD_KEYS:
            self._shell_block("workspace_shell_invalid", "Unexpected shell payload fields were provided.")
        if not self._shell_permissions_are_default(payload):
            self._shell_block("workspace_shell_permission", "Escalation and permission overrides are not allowed.")
        anchor_index = self._index_for_event(event, repo_path=event.cwd)
        self._ensure_fresh(anchor_index)
        repo_root = anchor_index.repo.repo_root
        workdir = self._shell_workdir(event, payload, repo_root=repo_root)
        command = self._parse_shell_command(self._shell_command(payload))
        executable = self._trusted_shell_executable(command.executable, repo_root=repo_root)
        if self._same_path(executable, self.git_executable):
            self._validate_git_command(command.arguments, repo_root=repo_root, workdir=workdir)
            return
        if self._same_path(executable, self.rg_executable):
            self._validate_rg_command(command.arguments, repo_root=repo_root, workdir=workdir)
            return
        if self._same_path(executable, self.certutil_executable):
            self._validate_certutil_command(command.arguments, repo_root=repo_root, workdir=workdir)
            return
        self._shell_block("workspace_shell_unverified", "Executable is not one of the pinned shell allowlist binaries.")

    def _shell_permissions_are_default(self, payload: dict[str, Any]) -> bool:
        sandbox = payload.get("sandbox_permissions")
        if sandbox is not None and not isinstance(sandbox, str):
            self._shell_block("workspace_shell_invalid", "sandbox_permissions must be a string when provided.")
        if sandbox not in (None, "", "use_default"):
            return False
        additional = payload.get("additional_permissions")
        if additional is not None and not isinstance(additional, dict):
            self._shell_block("workspace_shell_invalid", "additional_permissions must be an object when provided.")
        if additional not in (None, {}):
            return False
        justification = payload.get("justification")
        if justification is not None and not isinstance(justification, str):
            self._shell_block("workspace_shell_invalid", "justification must be a string when provided.")
        if isinstance(justification, str) and justification.strip():
            return False
        prefix_rule = payload.get("prefix_rule")
        if prefix_rule is not None and not isinstance(prefix_rule, (list, tuple)):
            self._shell_block("workspace_shell_invalid", "prefix_rule must be a list when provided.")
        if prefix_rule not in (None, [], ()):
            return False
        return True

    def _shell_command(self, payload: dict[str, Any]) -> str:
        cmd = payload.get("cmd")
        command = payload.get("command")
        if cmd is not None and command is not None and cmd != command:
            self._shell_block("workspace_shell_invalid", "cmd and command disagree.")
        raw = cmd if cmd is not None else command
        if not isinstance(raw, str) or not raw.strip():
            self._shell_block("workspace_shell_invalid", "Shell command string is required.")
        stripped = raw.strip()
        if len(stripped) > _MAX_SHELL_COMMAND_CHARS:
            self._shell_block("workspace_shell_invalid", "Shell command exceeds the maximum allowed length.")
        return stripped

    def _shell_workdir(
        self,
        event: HookEvent,
        payload: dict[str, Any],
        *,
        repo_root: Path,
    ) -> Path:
        base_dir = self._canonical_existing_path(Path(event.cwd), require_directory=True)
        raw_workdir = payload.get("workdir")
        if raw_workdir in (None, ""):
            return base_dir
        if not isinstance(raw_workdir, str) or not raw_workdir.strip():
            self._shell_block("workspace_shell_invalid", "Shell workdir must be a non-empty string.")
        workdir = self._resolve_existing_repo_path(
            raw_path=raw_workdir,
            base_dir=base_dir,
            repo_root=repo_root,
            require_directory=True,
            cross_repo_code="workspace_shell_workdir_repo",
        )
        try:
            identity = resolve_repo_identity(
                workdir,
                git_executable=self.git_executable,
                deadline_monotonic=self._deadline_monotonic,
            )
        except WorkspaceIndexFailure:
            self._shell_block("workspace_shell_workdir_repo", "Shell workdir must stay inside the cwd-anchored repository.")
        if not self._same_path(identity.repo_root, repo_root):
            self._shell_block("workspace_shell_workdir_repo", "Shell workdir must stay inside the cwd-anchored repository.")
        return workdir

    def _parse_shell_command(self, command: str) -> _ShellCommand:
        if not command:
            self._shell_block("workspace_shell_invalid", "Shell command string is required.")
        tokens: list[_ShellToken] = []
        index = 0
        length = len(command)
        while index < length:
            self._check_deadline()
            current = command[index]
            codepoint = ord(current)
            if codepoint < 32 or 127 <= codepoint <= 159 or current in _UNICODE_LINE_SEPARATORS:
                self._shell_block("workspace_shell_invalid", "Shell command contains unsupported control or separator characters.")
            if current.isspace():
                index += 1
                continue
            if current == "'":
                end = command.find("'", index + 1)
                if end == -1:
                    self._shell_block("workspace_shell_invalid", "Single-quoted shell literal is unterminated.")
                literal = command[index + 1 : end]
                if not literal:
                    self._shell_block("workspace_shell_invalid", "Single-quoted shell literal cannot be empty.")
                for ch in literal:
                    codepoint = ord(ch)
                    if codepoint < 32 or 127 <= codepoint <= 159 or ch in _UNICODE_LINE_SEPARATORS:
                        self._shell_block("workspace_shell_invalid", "Shell command contains unsupported control or separator characters.")
                tokens.append(_ShellToken(literal, quoted=True))
                index = end + 1
                continue
            start = index
            while index < length:
                self._check_deadline()
                current = command[index]
                codepoint = ord(current)
                if codepoint < 32 or 127 <= codepoint <= 159 or current in _UNICODE_LINE_SEPARATORS:
                    self._shell_block("workspace_shell_invalid", "Shell command contains unsupported control or separator characters.")
                if current.isspace():
                    break
                if current in _SHELL_FORBIDDEN_CHARS:
                    self._shell_block("workspace_shell_unverified", "Shell command contains forbidden PowerShell syntax.")
                if current == "'":
                    self._shell_block("workspace_shell_invalid", "Unexpected quote inside a bare shell token.")
                index += 1
            tokens.append(_ShellToken(command[start:index], quoted=False))
        if len(tokens) < 2 or tokens[0] != _ShellToken("&", quoted=False) or not tokens[1].quoted:
            self._shell_block(
                "workspace_shell_unverified",
                "Shell command must use the exact form & '<absolute pinned exe>' ...",
            )
        if any(token.value == "&" for token in tokens[1:]):
            self._shell_block("workspace_shell_unverified", "Only a single leading call operator is allowed.")
        try:
            executable = self._canonical_existing_path(Path(tokens[1].value), require_file=True)
        except (FileNotFoundError, WorkspaceIndexFailure):
            self._shell_block("workspace_shell_unverified", "Shell executable must resolve to a real trusted file.")
        if not executable.is_absolute():
            self._shell_block("workspace_shell_unverified", "Shell executable must be an absolute path.")
        return _ShellCommand(executable=executable, arguments=tuple(tokens[2:]))

    def _trusted_shell_executable(self, executable: Path, *, repo_root: Path) -> Path:
        if not executable.is_file():
            self._shell_block("workspace_shell_unverified", "Shell executable must resolve to a real file.")
        if _commonpath_contains(repo_root, executable):
            self._shell_block("workspace_shell_unverified", "Repo-local executables are not trusted for shell allowlisting.")
        return executable

    def _validate_git_command(
        self,
        arguments: tuple[_ShellToken, ...],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        prefix = [
            "--no-pager",
            "--no-optional-locks",
            "-c",
            "color.ui=never",
            "--literal-pathspecs",
        ]
        if len(arguments) < len(prefix) or [token.value for token in arguments[:5]] != prefix:
            self._shell_block("workspace_shell_unverified", "Git command does not match the required read-only prefix.")
        tail = list(arguments[5:])
        if not tail or tail[0].quoted:
            self._shell_block("workspace_shell_unverified", "Git subcommand is missing.")
        subcommand = tail[0].value
        remainder = tail[1:]
        if subcommand == "status":
            self._validate_git_status(remainder, repo_root=repo_root, workdir=workdir)
            return
        if subcommand == "diff":
            self._validate_git_diff(remainder, repo_root=repo_root, workdir=workdir)
            return
        if subcommand == "show":
            self._validate_git_show(remainder)
            return
        if subcommand == "log":
            self._validate_git_log(remainder, repo_root=repo_root, workdir=workdir)
            return
        if subcommand == "rev-parse":
            self._validate_git_rev_parse(remainder)
            return
        self._shell_block("workspace_shell_unverified", f"Git subcommand {subcommand!r} is not in the allowlist.")

    def _validate_git_status(
        self,
        arguments: list[_ShellToken],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        required = ["--short", "--branch", "--untracked-files=all"]
        if len(arguments) == len(required) and [token.value for token in arguments] == required:
            return
        if len(arguments) < len(required) + 2 or [token.value for token in arguments[:3]] != required or arguments[3] != _ShellToken("--", quoted=False):
            self._shell_block("workspace_shell_unverified", "Git status must use the exact approved read-only form.")
        self._validate_path_operands(arguments[4:], repo_root=repo_root, workdir=workdir)

    def _validate_git_diff(
        self,
        arguments: list[_ShellToken],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        required = ["--no-ext-diff", "--no-textconv", "--stat", "--"]
        if len(arguments) < len(required) + 1 or [token.value for token in arguments[:4]] != required:
            self._shell_block("workspace_shell_unverified", "Git diff must use the exact approved read-only form.")
        self._validate_path_operands(arguments[4:], repo_root=repo_root, workdir=workdir)

    def _validate_git_show(self, arguments: list[_ShellToken]) -> None:
        required = ["--no-ext-diff", "--no-textconv", "--stat", "--format=medium"]
        if len(arguments) != len(required) + 1 or [token.value for token in arguments[:4]] != required:
            self._shell_block("workspace_shell_unverified", "Git show must use the exact approved read-only form.")
        self._validate_git_ref(arguments[4])

    def _validate_git_log(
        self,
        arguments: list[_ShellToken],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        required = ["--no-ext-diff", "--no-textconv", "--format=medium", "-n"]
        if len(arguments) < len(required) + 3 or [token.value for token in arguments[:4]] != required:
            self._shell_block("workspace_shell_unverified", "Git log must use the exact approved read-only form.")
        count = arguments[4]
        if count.quoted or not count.value.isdigit() or int(count.value) <= 0:
            self._shell_block("workspace_shell_unverified", "Git log count must be a positive integer.")
        if arguments[5] != _ShellToken("--", quoted=False):
            self._shell_block("workspace_shell_unverified", "Git log must terminate options with --.")
        self._validate_path_operands(arguments[6:], repo_root=repo_root, workdir=workdir)

    def _validate_git_rev_parse(self, arguments: list[_ShellToken]) -> None:
        required = ["--verify", "--revs-only"]
        if len(arguments) != len(required) + 1 or [token.value for token in arguments[:2]] != required:
            self._shell_block("workspace_shell_unverified", "Git rev-parse must use the exact approved read-only form.")
        self._validate_git_ref(arguments[2])

    def _validate_git_ref(self, token: _ShellToken) -> None:
        if token.quoted or not _SAFE_GIT_REF_RE.fullmatch(token.value):
            self._shell_block("workspace_shell_unverified", "Git ref tokens must be simple literal refs only.")

    def _validate_rg_command(
        self,
        arguments: tuple[_ShellToken, ...],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        tokens = list(arguments)
        if not tokens or tokens[0] != _ShellToken("--no-config", quoted=False):
            self._shell_block("workspace_shell_unverified", "rg must start with --no-config.")
        tail = tokens[1:]
        if len(tail) >= 2 and tail[0] == _ShellToken("--files", quoted=False) and tail[1] == _ShellToken("--", quoted=False):
            self._validate_path_operands(tail[2:], repo_root=repo_root, workdir=workdir)
            return
        required = [
            _ShellToken("--line-number", quoted=False),
            _ShellToken("--no-heading", quoted=False),
            _ShellToken("--color=never", quoted=False),
            _ShellToken("--regexp", quoted=False),
        ]
        if len(tail) < len(required) + 3 or tail[:4] != required:
            self._shell_block("workspace_shell_unverified", "rg must use one of the exact approved read-only forms.")
        self._validate_literal_rg_pattern(tail[4])
        if tail[5] != _ShellToken("--", quoted=False):
            self._shell_block("workspace_shell_unverified", "rg must terminate options with --.")
        self._validate_path_operands(tail[6:], repo_root=repo_root, workdir=workdir)

    def _validate_literal_rg_pattern(self, token: _ShellToken) -> None:
        if not token.quoted or not token.value:
            self._shell_block("workspace_shell_unverified", "rg pattern must be a single-quoted literal.")
        if any(char in _LITERAL_RG_METACHARS for char in token.value):
            self._shell_block("workspace_shell_unverified", "rg pattern must be a literal string, not a regex program.")

    def _validate_certutil_command(
        self,
        arguments: tuple[_ShellToken, ...],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        if len(arguments) != 3 or arguments[0] != _ShellToken("-hashfile", quoted=False) or arguments[2] != _ShellToken("SHA256", quoted=False):
            self._shell_block("workspace_shell_unverified", "certutil must use the exact approved SHA256 form.")
        target = self._resolve_existing_repo_path(
            raw_path=arguments[1].value,
            base_dir=workdir,
            repo_root=repo_root,
            require_file=True,
            cross_repo_code="workspace_shell_unverified",
        )
        if not target.is_file():
            self._shell_block("workspace_shell_unverified", "certutil target must be a regular file inside the repo.")

    def _validate_path_operands(
        self,
        operands: list[_ShellToken],
        *,
        repo_root: Path,
        workdir: Path,
    ) -> None:
        if not operands:
            self._shell_block("workspace_shell_unverified", "At least one contained path operand is required.")
        for operand in operands:
            self._resolve_existing_repo_path(
                raw_path=operand.value,
                base_dir=workdir,
                repo_root=repo_root,
                require_directory=False,
                require_file=False,
                allow_current_dir=True,
                cross_repo_code="workspace_shell_unverified",
            )

    def _index_plan(self, plan: Any) -> IndexMutationPlan:
        operations = tuple(self._index_operation(mutation) for mutation in plan.mutations)
        return IndexMutationPlan(
            owner=str(plan.owner),
            operation_id=str(plan.operation_id),
            operations=operations,
        )

    def _index_operation(self, mutation: PathMutation) -> MutationOp:
        postimage: str | None = None
        if mutation.postimage_bytes is not None:
            postimage = mutation.postimage_bytes.decode("utf-8", errors="strict")
            digest = hashlib.sha256(mutation.postimage_bytes).hexdigest()
            if mutation.postimage_sha256 and digest != mutation.postimage_sha256:
                raise ValueError("postimage sha mismatch")
        elif mutation.kind != "delete":
            raise ValueError("postimage required for non-delete mutation")
        return MutationOp(
            kind=mutation.kind,
            path=mutation.target_relative_path,
            postimage=postimage,
            source_path=mutation.source_relative_path,
        )

    def _resolve_target(
        self,
        *,
        raw_target: str,
        base_dir: Path,
        repo_root: Path,
    ) -> ResolvedTarget:
        absolute_path = self._resolve_candidate_path(
            raw_path=raw_target,
            base_dir=base_dir,
            repo_root=repo_root,
            must_exist=False,
            require_directory=False,
            require_file=False,
            allow_current_dir=False,
            cross_repo_code="workspace_target_cross_repo",
            escape_code="workspace_target_escape",
            invalid_code="workspace_target_invalid",
            protected_code="workspace_target_protected",
        )
        try:
            relative = absolute_path.relative_to(repo_root)
        except ValueError as exc:
            raise MutationPlanningError("workspace_target_escape") from exc
        if any(part.lower() in _VCS_METADATA_DIRS for part in relative.parts):
            raise MutationPlanningError("workspace_target_protected")
        return ResolvedTarget(
            relative_path=relative,
            absolute_path=absolute_path,
            exists=absolute_path.exists(),
        )

    def _planning_reason(self, tool_name: str, exc: MutationPlanningError) -> str:
        reason = str(exc).strip()
        if reason.startswith("workspace_"):
            return reason
        lowered = reason.lower()
        if "travers" in lowered or ".." in reason:
            return "workspace_target_escape"
        if tool_name == "apply_patch":
            return "workspace_patch_invalid"
        if tool_name in {"Edit", "MultiEdit"} and reason.endswith("target is missing"):
            return "workspace_target_missing"
        return "workspace_target_invalid"

    def _owner(self, event: HookEvent) -> str:
        return f"{event.provider}:{str(event.session_id).strip()}"

    def _require_identified_session(self, event: HookEvent) -> None:
        if not _identified_session(event.session_id):
            self._block("workspace_session_unidentified")

    def _require_tool_id(self, event: HookEvent) -> None:
        if not str(event.tool.id or "").strip():
            self._block("workspace_tool_id_missing")

    def _index_for_event(
        self,
        event: HookEvent,
        *,
        repo_path: Path | str | None = None,
        allow_nonrepo: bool = False,
    ) -> WorkspaceIndex | None:
        target = repo_path if repo_path is not None else event.cwd
        try:
            return WorkspaceIndex(
                state_root=self.state_root,
                repo_path=target,
                git_executable=self.git_executable,
                deadline_monotonic=self._deadline_monotonic,
            )
        except WorkspaceIndexFailure as exc:
            if allow_nonrepo and exc.code == "workspace_repo_unavailable":
                return None
            raise

    def _repo_root_for_existing_path(self, candidate: Path) -> Path | None:
        try:
            identity = resolve_repo_identity(
                candidate,
                git_executable=self.git_executable,
                deadline_monotonic=self._deadline_monotonic,
            )
        except WorkspaceIndexFailure:
            return None
        return identity.repo_root

    def _reserve(self, index: WorkspaceIndex, plan: IndexMutationPlan) -> None:
        try:
            receipt = index.reserve(plan)
        except WorkspaceIndexFailure as exc:
            if exc.code not in {"workspace_index_missing", "workspace_index_stale"}:
                if exc.code == "workspace_path_conflict" and index.resolve(
                    owner=plan.owner,
                    operation_id=plan.operation_id,
                ):
                    self._block("workspace_replay_blocked")
                if exc.code in {"workspace_index_conflict", "workspace_retry_mismatch"}:
                    self._block("workspace_replay_blocked")
                raise
            index.refresh()
            receipt = index.reserve(plan)
        status = getattr(receipt, "status", "reserved")
        if status in {"replayed", "resolved", "completed", "abandoned"}:
            self._block("workspace_replay_blocked")

    def _ensure_fresh(self, index: WorkspaceIndex) -> None:
        try:
            index.assert_fresh()
        except WorkspaceIndexFailure as exc:
            if exc.code not in {"workspace_index_missing", "workspace_index_stale"}:
                raise
            index.refresh()

    def _resolve_existing_repo_path(
        self,
        *,
        raw_path: str,
        base_dir: Path,
        repo_root: Path,
        require_directory: bool = False,
        require_file: bool = False,
        allow_current_dir: bool = False,
        cross_repo_code: str,
    ) -> Path:
        return self._resolve_candidate_path(
            raw_path=raw_path,
            base_dir=base_dir,
            repo_root=repo_root,
            must_exist=True,
            require_directory=require_directory,
            require_file=require_file,
            allow_current_dir=allow_current_dir,
            cross_repo_code=cross_repo_code,
            escape_code="workspace_shell_unverified",
            invalid_code="workspace_shell_invalid",
            protected_code="workspace_shell_unverified",
        )

    def _resolve_candidate_path(
        self,
        *,
        raw_path: str,
        base_dir: Path,
        repo_root: Path,
        must_exist: bool,
        require_directory: bool,
        require_file: bool,
        allow_current_dir: bool,
        cross_repo_code: str,
        escape_code: str,
        invalid_code: str,
        protected_code: str,
    ) -> Path:
        self._check_deadline()
        text = str(raw_path).strip()
        if not text:
            self._path_block(invalid_code)
        if text == ".":
            if not allow_current_dir:
                self._path_block(escape_code)
            return base_dir
        if any(ch in text for ch in _WINDOWS_WILDCARDS):
            self._path_block(invalid_code)
        if "\x00" in text or text.startswith(_WINDOWS_DEVICE_PREFIX) or text.startswith(("\\\\", "//")):
            self._path_block(invalid_code)
        if _is_windows_drive_relative(text) or _has_ads(text):
            self._path_block(invalid_code)
        if _has_trailing_dot_space_component(text) or _has_reserved_device_component(text):
            self._path_block(invalid_code)
        candidate = Path(text)
        if any(part in {".", ".."} for part in candidate.parts):
            self._path_block(escape_code)
        if any(part.lower() in _VCS_METADATA_DIRS for part in candidate.parts):
            self._path_block(protected_code)
        absolute = candidate if candidate.is_absolute() else (base_dir / candidate)
        lexical = Path(os.path.abspath(str(absolute)))
        if not _commonpath_contains(repo_root, lexical):
            other_repo = self._repo_root_for_existing_path(self._nearest_existing_ancestor(lexical))
            if other_repo is not None and not self._same_path(other_repo, repo_root):
                self._path_block(cross_repo_code)
        physical = self._physical_candidate(absolute)
        if not _commonpath_contains(repo_root, physical):
            other_repo = self._repo_root_for_existing_path(self._nearest_existing_ancestor(physical))
            if other_repo is not None and not self._same_path(other_repo, repo_root):
                self._path_block(cross_repo_code)
            self._path_block(escape_code)
        if must_exist and not physical.exists():
            self._path_block(invalid_code)
        if physical.exists() and _is_reparse_point(physical):
            self._path_block(invalid_code)
        if require_directory and (not physical.exists() or not physical.is_dir()):
            self._path_block(invalid_code)
        if require_file and (not physical.exists() or not physical.is_file()):
            self._path_block(invalid_code)
        return physical

    def _physical_candidate(self, absolute: Path) -> Path:
        chain = [absolute, *absolute.parents]
        for current in chain:
            self._check_deadline()
            if current.exists():
                resolved = self._canonical_existing_path(current, require_directory=current.is_dir(), require_file=current.is_file())
                if current == absolute:
                    return resolved
                relative_suffix = absolute.relative_to(current)
                return resolved.joinpath(*relative_suffix.parts)
        return Path(os.path.abspath(str(absolute)))

    def _nearest_existing_ancestor(self, candidate: Path) -> Path:
        for current in (candidate, *candidate.parents):
            if current.exists():
                return current
        if candidate.anchor:
            return Path(candidate.anchor)
        return candidate

    def _canonical_existing_path(
        self,
        candidate: Path,
        *,
        require_directory: bool = False,
        require_file: bool = False,
    ) -> Path:
        resolved = candidate.resolve(strict=True)
        if require_directory and not resolved.is_dir():
            raise FileNotFoundError(str(candidate))
        if require_file and not resolved.is_file():
            raise FileNotFoundError(str(candidate))
        if _is_reparse_point(resolved):
            raise WorkspaceIndexFailure("workspace_index_uncertain", f"reparse point detected: {resolved}")
        return resolved

    def _check_mutation_payload_size(self, payload: Any) -> None:
        self._check_deadline()
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        except (TypeError, ValueError):
            encoded = repr(payload).encode("utf-8", "replace")
        if len(encoded) > _MAX_MUTATION_PAYLOAD_BYTES:
            self._block("workspace_op_limit")

    def _planning_resolve_target(
        self,
        raw_target: str,
        base_dir: Path,
        repo_root: Path,
    ) -> ResolvedTarget:
        self._check_deadline()
        return self._resolve_target(
            raw_target=raw_target,
            base_dir=base_dir,
            repo_root=repo_root,
        )

    def _normalize_post_outcome(self, outcome: Any) -> str:
        if isinstance(outcome, bool):
            return "completed" if outcome else "unknown"
        if isinstance(outcome, str):
            return outcome.strip().lower() or "unknown"
        status = getattr(outcome, "status", None)
        if isinstance(status, str):
            return status.strip().lower() or "unknown"
        if isinstance(outcome, dict):
            raw_status = outcome.get("status")
            if isinstance(raw_status, str):
                return raw_status.strip().lower() or "unknown"
        return "unknown"

    def _resolve_pinned_executable(
        self,
        *,
        candidate: Path | str | None,
        which_name: str,
        required_name: str,
    ) -> Path:
        raw = candidate
        if raw is None:
            raw = shutil.which(which_name)
        if raw is None or not str(raw).strip():
            raise ValueError(f"trusted executable for {which_name} is unavailable")
        path = Path(raw)
        if not path.is_absolute():
            found = shutil.which(str(raw))
            if not found:
                raise ValueError(f"trusted executable for {which_name} is unavailable")
            path = Path(found)
        resolved = path.resolve(strict=True)
        if resolved.name.lower() != required_name.lower():
            raise ValueError(f"unexpected executable name for {which_name}: {resolved.name}")
        if not resolved.is_file():
            raise ValueError(f"trusted executable for {which_name} is not a file")
        return resolved

    def _resolve_certutil_executable(self, candidate: Path | str | None) -> Path:
        if candidate is not None:
            resolved = Path(candidate).resolve(strict=True)
            if resolved.name.lower() != _TRUSTED_CERTUTIL_NAME:
                raise ValueError(f"unexpected executable name for certutil: {resolved.name}")
            return resolved
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        return (system_root / "System32" / _TRUSTED_CERTUTIL_NAME).resolve(strict=True)

    def _shell_block(self, reason_code: str, detail: str) -> None:
        self._block(
            reason_code,
            additional_context=[detail, *_SHELL_GRAMMAR_CONTEXT],
        )

    def _path_block(self, reason_code: str) -> None:
        if reason_code.startswith("workspace_target_"):
            raise MutationPlanningError(reason_code)
        self._shell_block(reason_code, "Shell path operands must stay inside the cwd-anchored repository.")

    def _same_path(self, left: Path, right: Path) -> bool:
        return _normcase_path(left.resolve(strict=True)) == _normcase_path(right.resolve(strict=True))

    def _check_deadline(self) -> None:
        if self._deadline_monotonic is not None and time.monotonic() >= self._deadline_monotonic:
            raise WorkspaceIndexFailure(
                "workspace_index_deadline",
                "deadline exceeded before workspace integrity processing",
            )

    def _block(
        self,
        reason_code: str,
        *,
        additional_context: list[str] | None = None,
    ) -> None:
        raise _BlockWorkspace(reason_code, additional_context=additional_context)
