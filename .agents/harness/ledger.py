from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]

try:
    from .redaction import redact_text
    from .storage import atomic_write_json, atomic_write_text, read_json
except ImportError:  # pragma: no cover
    from redaction import redact_text
    from storage import atomic_write_json, atomic_write_text, read_json


def default_state_root() -> Path:
    configured = os.environ.get("AGENT_HARNESS_STATE_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agents" / "state" / "harness"


def _safe_component(value: str, limit: int = 36) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in value)
    return safe.strip("-.")[:limit] or "project"


_UNIDENTIFIED_SESSION_IDS = {"", "unknown"}


def _session_isolatable(session_id: str | None) -> bool:
    """Whether a session_id identifies one session well enough to isolate it.

    The event adapter defaults a missing session_id to the literal "unknown",
    which every unidentified session shares. Writing a per-session goal under
    it would silently re-merge concurrent sessions (the exact stomping bug this
    module prevents), so treat those as non-isolatable: callers then decline
    isolation instead of faking it with a shared slot.
    """
    return bool(session_id) and str(session_id) not in _UNIDENTIFIED_SESSION_IDS


def canonical_project_path(cwd: str) -> str:
    """Resolve a stable repository/worktree root without spawning git."""
    candidate = Path(os.path.abspath(str(cwd or ".")))
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        try:
            if (parent / ".git").exists():
                return str(parent)
        except OSError:
            break
    return str(candidate)


def project_key(cwd: str) -> str:
    normalized = os.path.normcase(canonical_project_path(cwd))
    digest = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:12]
    return f"project-{digest}"


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return redact_text(value, redact_paths=True, max_chars=1000)
    if depth >= 5:
        return redact_text(repr(value), redact_paths=True, max_chars=1000)
    if isinstance(value, dict):
        return {
            redact_text(str(key), redact_paths=True, max_chars=120): _sanitize_value(
                nested, depth + 1
            )
            for key, nested in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(nested, depth + 1) for nested in list(value)[:100]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(repr(value), redact_paths=True, max_chars=1000)


# ---------------------------------------------------------------------------
# A1 · Typed receipts (SI-1) + B4 · taint propagation (SI-5-adjacent).
#
# This module owns the FOUNDATION data + storage + query half only. The pure
# classifier below is imported by modules.py (LedgerModule stamps the receipt_*
# fields + kind=="mutation" events at the PostToolUse call site; ClaimWarning
# v2 gates on has_fresh_receipt / receipt_for_fingerprint). The claim/falsify
# TRIGGERS (note.py, fresh-context-verify) live in modules.py and are out of
# scope here. Names are load-bearing — other lanes depend on them verbatim.
# ---------------------------------------------------------------------------

RECEIPT_CLASSES: tuple[str, ...] = (
    "test",
    "build",
    "lint",
    "typecheck",
    "coverage",
    "run",
    "e2e",
    "health",
)

# Claim family -> receipt classes that would substantiate it. has_fresh_receipt
# reads the tuple as ANY-of (one fresh pass substantiates), matching the
# has_verification any-green back-compat shim.
CLAIM_RECEIPT_MAP: dict[str, tuple[str, ...]] = {
    "tests_pass": ("test",),
    "fixed": ("test", "run"),
    "builds": ("build", "typecheck"),
    "type_clean": ("typecheck",),
    "lint_clean": ("lint",),
    "coverage": ("coverage",),
    "healthy": ("health",),
    "e2e_pass": ("e2e",),
}

# Standards-of-proof stake tiers (SI-1): risk class -> burden-of-proof label.
STAKE_TIERS: dict[str, str] = {
    "routine": "preponderance",
    "multifile": "clear_and_convincing",
    "irreversible": "beyond_reasonable_doubt",
}

# Bounded, chronological windows for the receipt/taint queries. Kept small so a
# hook never reparses a large ledger; replay() itself caps at 200.
_RECEIPT_SCAN_LIMIT = 120
_TAINT_SCAN_LIMIT = 200


@dataclass(frozen=True)
class Receipt:
    """A typed verification receipt (SI-1).

    ``seq``/``ts`` are 0/'' at classification time — classify_receipt is a pure
    function that runs before the ledger event exists; the stored event's own
    seq/ts are authoritative when a receipt is reconstructed from storage via
    receipt_for_fingerprint / has_fresh_receipt.
    """

    receipt_class: str
    status: str  # "pass" | "fail" | "unknown"
    passed: int
    failed: int
    fingerprint: str
    seq: int
    ts: str


# Ordered (most-specific first) class signatures. First match wins so that e.g.
# `pytest --cov` is coverage, `python -m pytest` is test, `npm run build` is
# build. Multi-char tokens (containing a space/symbol) match literally; bare
# alnum tokens are word-bounded to avoid "latest"->test / "runtime"->run hits.
_RECEIPT_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "coverage",
        ("--cov", "cov-report", "--coverage", "coverage.py", "nyc", "c8", "codecov"),
    ),
    (
        "e2e",
        (
            "playwright",
            "cypress",
            "e2e",
            "nightwatch",
            "puppeteer",
            "selenium",
            "webdriverio",
        ),
    ),
    (
        "typecheck",
        ("tsc", "mypy", "pyright", "basedpyright", "type-check", "typecheck"),
    ),
    (
        "lint",
        (
            "eslint",
            "ruff",
            "flake8",
            "pylint",
            "prettier",
            "biome",
            "clippy",
            "golangci",
            "opengrep",
            "semgrep",
            "--check",
            "lint",
        ),
    ),
    (
        "test",
        (
            "pytest",
            "jest",
            "vitest",
            "mocha",
            "unittest",
            "rspec",
            "phpunit",
            "go test",
            "cargo test",
            "npm test",
            "test",
        ),
    ),
    (
        "build",
        (
            "cargo build",
            "go build",
            "webpack",
            "vite build",
            "electron-builder",
            "cmake",
            "gradle",
            "mvn",
            "msbuild",
            "meson",
            "ninja",
            "compile",
            "make",
            "build",
        ),
    ),
    (
        "run",
        (
            "python",
            "node",
            "npm start",
            "cargo run",
            "go run",
            "uv run",
            "pnpm start",
            "bun run",
            "deno run",
            "dotnet run",
            "./",
            "run",
        ),
    ),
)


def _token_in(command: str, token: str) -> bool:
    """Word-bounded match for bare alnum tokens; literal substring otherwise."""
    if not token.isalnum():
        return token in command
    return (
        re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", command)
        is not None
    )


# Tool names that actually EXECUTE a command. A receipt is proof-of-execution,
# so ONLY an executing tool may mint one: `tool_name` is authority, the payload
# is merely where the argv lives. Before this gate the tool name was discarded
# and ANY payload carrying command/cmd/script/argv (or a bare string) minted an
# authoritative receipt — classify_receipt("WebSearch", "pytest status",
# "success") and ("mcp__tasks__create", {"command": "pytest", ...}) both
# returned test/pass without anything ever running. Fail-CLOSED: an unrecognized
# tool yields no receipt (the claim gate then asks for real proof) rather than a
# fabricated green.
_COMMAND_TOOL_NAMES = frozenset(
    {
        "bash",
        "bashoutput",
        "cmd",
        "container.exec",
        "exec",
        "execute",
        "execute_command",
        "executecommand",
        "fish",
        "local_shell",
        "powershell",
        "pwsh",
        "run",
        "run_command",
        "run_terminal_cmd",
        "runcommand",
        "sh",
        "shell",
        "shell_command",
        "shellcommand",
        "terminal",
        "zsh",
    }
)
_COMMAND_TOOL_HINT = re.compile(
    r"(?:^|[^a-z])(?:bash|shell|pwsh|powershell|terminal|exec|command)(?:[^a-z]|$)"
)


def _is_command_tool(tool_name: str) -> bool:
    """True only for tools that RUN a command (so may mint a typed receipt)."""
    name = str(tool_name or "").strip().lower()
    if not name:
        return False
    if name in _COMMAND_TOOL_NAMES:
        return True
    # MCP tools arrive namespaced (mcp__server__tool): judge the leaf verb, so
    # mcp__x__run_command counts and mcp__tasks__create does not.
    leaf = name.rsplit("__", 1)[-1]
    if leaf in _COMMAND_TOOL_NAMES:
        return True
    return _COMMAND_TOOL_HINT.search(leaf) is not None


def _receipt_command(tool_name: str, tool_input: Any) -> str:
    """Extract a runnable argv/command string, or '' for non-command tools.

    ``tool_name`` is part of the SI-1 signature and is the AUTHORITY for whether
    anything ran: a non-executing tool yields '' regardless of its payload. For
    an executing tool the command is resolved from the input payload
    (Bash/PowerShell carry it under ``command``; a bare string input IS the
    command; write/read tools carry no command and yield '' so they never mint a
    receipt).
    """
    if not _is_command_tool(tool_name):
        return ""
    if isinstance(tool_input, str):
        return tool_input.strip()
    if isinstance(tool_input, dict):
        for key in ("command", "cmd", "script", "argv"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (list, tuple)) and value:
                return " ".join(str(part) for part in value).strip()
    return ""


def _is_health_command(lower: str) -> bool:
    if any(
        token in lower
        for token in (
            "healthz",
            "readyz",
            "livez",
            "/health",
            "healthcheck",
            "health-check",
        )
    ):
        return True
    if _token_in(lower, "ping"):
        return True
    return _token_in(lower, "curl") and any(
        word in lower for word in ("health", "ready", "live", "status")
    )


# Read-only / display heads whose ARGUMENTS must never pick the receipt class:
# the signature scan matches a token anywhere in the string, so `echo test` and
# `cat test.log` classified as "test" and minted a green test receipt.
_NON_EXECUTING_HEADS = frozenset(
    {
        "bat",
        "cat",
        "dir",
        "echo",
        "env",
        "find",
        "grep",
        "head",
        "less",
        "ls",
        "more",
        "printenv",
        "printf",
        "rg",
        "tail",
        "type",
        "where",
        "which",
    }
)
# Informational invocations: the verifier binary is present but nothing was
# verified (`pytest --version`, `pytest --collect-only`). Case-sensitive so the
# version flag -V is not confused with pytest's verbose -v.
_INFORMATIONAL_FLAG = re.compile(
    r"(?:^|\s)(?:--version|-V|--help|--usage|-h|--collect-only|--co|--dry-run"
    r"|--dry_run|--list-tests)(?:[\s=]|$)"
)
# Exit-code laundering: `cmd || true`, `cmd | tee log`. The shell reports 0 no
# matter what the verifier did, so the exit code carries no verdict.
_EXIT_LAUNDERED = re.compile(
    r"\|\|\s*(?::|true|exit\s+0)|;\s*(?:true|exit\s+0)\s*$|\|\s*tee\b"
)
# "the suite ran zero tests" — exit 0 here proves nothing was verified.
_NO_TESTS_RAN = re.compile(
    r"no test files|no tests? (?:ran|were run|found|to run|executed)"
    r"|collected 0 items|0 tests? ran|tests:\s+0 total",
    re.I,
)
_TEST_FAMILY = frozenset({"test", "e2e", "coverage"})


def _command_head(lower: str) -> str:
    for part in lower.split():
        token = part.strip("\"'`(")
        if not token or "=" in token:
            continue
        return token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return ""


def _classify_command(command: str) -> str | None:
    lower = command.lower()
    if _command_head(lower) in _NON_EXECUTING_HEADS:
        return None
    if _INFORMATIONAL_FLAG.search(command):
        return None
    if _is_health_command(lower):
        return "health"
    for receipt_class, tokens in _RECEIPT_SIGNATURES:
        if any(_token_in(lower, token) for token in tokens):
            return receipt_class
    return None


def _result_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=repr)
    except (TypeError, ValueError):
        return repr(result)


def _exit_code(result: Any) -> int | None:
    if isinstance(result, dict):
        for key in ("exit_code", "exitCode", "returncode"):
            value = result.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value)
    return None


_COUNT_PASSED = re.compile(r"(\d+)\s+pass(?:ed)?", re.I)
_COUNT_FAILED = re.compile(r"(\d+)\s+(?:fail(?:ed|ures?)?|errors?)", re.I)


def _sum_matches(pattern: re.Pattern[str], text: str) -> int:
    total = 0
    for match in pattern.finditer(text):
        try:
            total += int(match.group(1))
        except (TypeError, ValueError):
            continue
    return total


def _parse_counts(result: Any, text: str | None = None) -> tuple[int, int]:
    if text is None:
        text = _result_text(result)
    return _sum_matches(_COUNT_PASSED, text), _sum_matches(_COUNT_FAILED, text)


def _receipt_status(
    result: Any,
    passed: int,
    failed: int,
    *,
    receipt_class: str = "",
    command: str = "",
    text: str | None = None,
) -> str:
    if failed > 0:
        return "fail"
    if text is None:
        text = _result_text(result)
    # A test-family run that executed zero tests is not proof of anything, even
    # though the runner exits 0 (`go test ./...` -> "[no test files]").
    if receipt_class in _TEST_FAMILY and passed == 0 and _NO_TESTS_RAN.search(text):
        return "unknown"
    exit_code = _exit_code(result)
    # `pytest … || true` always exits 0; the code is not a verdict, so fall
    # through to the parsed counts instead of minting a green.
    if exit_code is not None and not _EXIT_LAUNDERED.search(command):
        return "pass" if exit_code == 0 else "fail"
    if passed > 0:
        return "pass"
    # Prose is only ever the PRIMARY signal for a health probe (curl prints
    # "status: healthy" and no counts). For every other class, inferring a pass
    # from the word "success" appearing in arbitrary output was how prose alone
    # minted an authoritative test receipt.
    if receipt_class == "health":
        positive = re.search(
            r"\b(?:success|succeeded|healthy|ready|ok|pass(?:ed)?)\b", text, re.I
        )
        negative = re.search(
            r"\b(?:fail(?:ed|ure)?|error|traceback|exception)\b", text, re.I
        )
        if positive and not negative:
            return "pass"
    return "unknown"


def argv_fingerprint(command: str) -> str:
    """sha256 of whitespace-normalized argv — the failing-command identity used
    by the repro-fingerprint fix-gate. Case-preserving (distinct commands stay
    distinct); only runs of whitespace are collapsed. Pure hex, so it survives
    the ledger's secret/path sanitizer untouched."""
    normalized = " ".join(str(command or "").split())
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()


def classify_receipt(
    tool_name: str, tool_input: Any, tool_result: Any
) -> Receipt | None:
    """Pure argv+exit+parsed-count heuristic -> a typed Receipt, or None when the
    tool carries no runnable command or the command is unclassifiable (SI-1)."""
    command = _receipt_command(tool_name, tool_input)
    if not command:
        return None
    receipt_class = _classify_command(command)
    if receipt_class is None:
        return None
    # Materialize the (possibly multi-MB) result text ONCE and share it with the
    # status pass; it used to be rendered twice per classification.
    text = _result_text(tool_result)
    passed, failed = _parse_counts(tool_result, text)
    return Receipt(
        receipt_class=receipt_class,
        status=_receipt_status(
            tool_result,
            passed,
            failed,
            receipt_class=receipt_class,
            command=command,
            text=text,
        ),
        passed=passed,
        failed=failed,
        fingerprint=argv_fingerprint(command),
        seq=0,
        ts="",
    )


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _receipt_from_event(event: dict[str, Any]) -> Receipt | None:
    """Reconstruct a Receipt from a stored tool_result event's receipt_* fields,
    binding the event's own seq/ts. Returns None for events with no (valid)
    typed receipt so legacy tool_result events are ignored by the receipt path."""
    receipt_class = str(event.get("receipt_class") or "")
    if receipt_class not in RECEIPT_CLASSES:
        return None
    return Receipt(
        receipt_class=receipt_class,
        status=str(event.get("receipt_status") or "unknown"),
        passed=_as_int(event.get("receipt_passed")),
        failed=_as_int(event.get("receipt_failed")),
        fingerprint=str(event.get("receipt_fp") or ""),
        seq=_as_int(event.get("seq")),
        ts=str(event.get("ts") or ""),
    )


class _FileLock:
    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = path
        self.timeout = timeout
        self.handle = None

    def _ensure_lock_file(self) -> None:
        assert self.handle is not None
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)

    def _acquire(self) -> None:
        assert self.handle is not None
        if os.name == "nt" and msvcrt is not None:
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        if fcntl is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        raise OSError("no file-lock backend available")

    def _release(self) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt" and msvcrt is not None:
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except (OSError, ValueError):
            pass

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            self._ensure_lock_file()
        except BaseException:
            try:
                self.handle.close()
            except (OSError, ValueError):
                pass
            self.handle = None
            raise
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._acquire()
                return self
            except OSError as exc:
                if time.monotonic() >= deadline:
                    try:
                        self.handle.close()
                    except (OSError, ValueError):
                        pass
                    self.handle = None
                    raise TimeoutError("ledger lock unavailable") from exc
                time.sleep(0.005)

    def __exit__(self, *_args):
        self._release()
        if self.handle is not None:
            try:
                self.handle.close()
            except (OSError, ValueError):
                pass
            self.handle = None


# --- goal_short distillation (DISPLAY-ONLY; never read by goal-reinjection) ------
# Deterministic, LLM-free. PURE function of its input. The `goal` field is written
# byte-for-byte unchanged; this only ADDS a sibling `goal_short` key, and only when a
# real objective survives distillation (else the key is omitted -> the status line
# falls back to cleaning `goal` itself).
_GS_TAG = re.compile(r"<[^>]*>")
_GS_WS = re.compile(r"\s+")
# First-clause boundary: a sentence terminator followed by space/end, or a spaced
# dash/colon. "modules.py" is safe (its '.' is not followed by whitespace).
_GS_CLAUSE = re.compile(r"[.!?]+(?:\s|$)|\s[-–—:]\s")
# Wrapper preambles that carry NO user objective -> distil to "" (omit, not garbage).
_GS_BOILERPLATE = (
    re.compile(r"(?i)^you are summarizing a claude code session"),
    re.compile(
        r"(?i)^you are (?:a|an|the)\b[^.!?]*\b(?:assistant|agent|subagent|model|summariz)"
    ),
    re.compile(r"(?i)^(?:please\s+)?summariz(?:e|ing)\b"),
    re.compile(r"(?i)^this (?:session|conversation) is being summariz"),
    re.compile(r"(?i)^(?:system|assistant)\s*:"),
)


def distill_goal_short(text: Any, *, max_len: int = 40) -> str:
    """Short (<= max_len char) objective label distilled deterministically from a raw
    goal, for status-line DISPLAY only. Returns "" when the input is pure
    wrapper/boilerplate with no objective signal. Pure and idempotent:
    distill_goal_short(distill_goal_short(x)) == distill_goal_short(x)."""
    if not text:
        return ""
    s = _GS_TAG.sub(" ", str(text))
    s = _GS_WS.sub(" ", s).strip()
    if not s or not any(ch.isalpha() for ch in s):
        return ""
    if any(pattern.search(s) for pattern in _GS_BOILERPLATE):
        return ""
    clause = _GS_CLAUSE.split(s, maxsplit=1)[0].strip()
    if not clause:
        return ""
    if len(clause) <= max_len:
        return clause
    short = clause[:max_len].rstrip()
    if " " in short:
        short = short[: short.rfind(" ")].rstrip()
    return short


class EventLedger:
    """Append-only, secret-redacted event facts shared by both providers."""

    def __init__(
        self,
        state_root: Path | str | None = None,
        *,
        legacy_root: Path | str | None = None,
    ):
        self.root = Path(state_root or default_state_root()).expanduser() / "ledger"
        self.legacy_root = Path(
            legacy_root or Path.home() / ".claude" / "event-ledger"
        ).expanduser()
        self._legacy_cache: dict[str, tuple[dict[str, Any], Path | None]] = {}

    def _dir(self, cwd: str) -> Path:
        return self.root / project_key(cwd)

    def _events(self, cwd: str) -> Path:
        return self._dir(cwd) / "events.jsonl"

    def _state_path(self, cwd: str) -> Path:
        return self._dir(cwd) / "state.json"

    def _shared_event_paths(self, cwd: str) -> list[Path]:
        target = self._events(cwd)
        digest = project_key(cwd).removeprefix("project-")
        try:
            compatible = list(self.root.glob(f"*-{digest}/events.jsonl"))
            compatible.extend(self.root.glob(f"project-{digest}-legacy-*/events.jsonl"))
        except OSError:
            compatible = []
        paths = list(dict.fromkeys(path for path in compatible if path != target))
        if target.exists():
            paths.append(target)
        return paths

    def _load_state(self, cwd: str) -> dict[str, Any]:
        default = {
            "schema_version": 1,
            "project": project_key(cwd),
            "seq": 0,
            "goal": None,
            "goal_ts": None,
            "decisions": [],
            "open_failures": [],
            "last_event_ts": None,
            # A1 freshness anchor: newest file-mutation position (see reducers).
            "last_mutation_seq": 0,
            "last_mutation_ts": None,
        }
        loaded = read_json(self._state_path(cwd), default)
        if not isinstance(loaded, dict):
            return default
        return default | loaded

    def _shared_events(self, cwd: str, *, repair: bool = False) -> list[dict[str, Any]]:
        valid: list[dict[str, Any]] = []
        target = self._events(cwd)
        for path in self._shared_event_paths(cwd):
            invalid = False
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            path_valid: list[dict[str, Any]] = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    invalid = True
                    continue
                if isinstance(item, dict):
                    path_valid.append(item)
                else:
                    invalid = True
            valid.extend(path_valid)
            if repair and invalid and path == target:
                content = "".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for item in path_valid
                )
                atomic_write_text(path, content)
        return valid

    @staticmethod
    def _tail_bytes(path: Path, max_bytes: int) -> tuple[bytes, bool]:
        try:
            size = path.stat().st_size
            start = max(0, size - max(1, int(max_bytes)))
            with path.open("rb") as handle:
                handle.seek(start)
                data = handle.read()
        except OSError:
            return b"", False
        if start:
            boundary = data.find(b"\n")
            if boundary < 0:
                return b"", False
            data = data[boundary + 1 :]
        return data, start == 0

    @classmethod
    def _last_event_from_path(cls, path: Path) -> dict[str, Any] | None:
        data, _ = cls._tail_bytes(path, 1024 * 1024)
        for raw_line in reversed(data.splitlines()):
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(item, dict):
                return item
        return None

    @classmethod
    def _last_shared_seq(cls, paths: list[Path]) -> int:
        latest = 0
        for path in paths:
            item = cls._last_event_from_path(path)
            if item is not None:
                latest = max(latest, int(item.get("seq") or 0))
        return latest

    @classmethod
    def _last_shared_marker(cls, paths: list[Path]) -> tuple[int, str]:
        candidates = [
            item
            for path in paths
            if (item := cls._last_event_from_path(path)) is not None
        ]
        if not candidates:
            return 0, ""
        latest = max(
            candidates,
            key=lambda item: (int(item.get("seq") or 0), str(item.get("ts") or "")),
        )
        return int(latest.get("seq") or 0), str(latest.get("ts") or "")

    @staticmethod
    def _find_event_by_id(paths: list[Path], event_id: str) -> dict[str, Any] | None:
        encoded = event_id.encode("ascii")
        pattern = re.compile(rb'"event_id"\s*:\s*"' + re.escape(encoded) + rb'"')
        for path in paths:
            try:
                data = path.read_bytes()
            except OSError:
                continue
            for match in pattern.finditer(data):
                start = data.rfind(b"\n", 0, match.start()) + 1
                end = data.find(b"\n", match.end())
                if end < 0:
                    end = len(data)
                try:
                    item = json.loads(data[start:end])
                except (UnicodeDecodeError, ValueError):
                    continue
                if isinstance(item, dict) and item.get("event_id") == event_id:
                    return item
        return None

    @classmethod
    def _tail_events_from_path(
        cls, path: Path, *, max_bytes: int
    ) -> list[dict[str, Any]]:
        data, _ = cls._tail_bytes(path, max_bytes)
        result: list[dict[str, Any]] = []
        for raw_line in data.splitlines():
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    @classmethod
    def _recent_shared_events(
        cls, paths: list[Path], *, after_seq: int, through_seq: int
    ) -> tuple[list[dict[str, Any]], bool]:
        gap = max(0, through_seq - after_seq)
        if gap == 0:
            return [], True
        if gap > 1000:
            return [], False
        budget = max(64 * 1024, min(16 * 1024 * 1024, (gap + 8) * 16 * 1024))
        events: list[dict[str, Any]] = []
        for path in paths:
            events.extend(cls._tail_events_from_path(path, max_bytes=budget))
        events = [item for item in events if int(item.get("seq") or 0) > after_seq]
        events.sort(
            key=lambda item: (int(item.get("seq") or 0), str(item.get("ts") or ""))
        )
        if not events:
            return [], False
        covered = {int(item.get("seq") or 0) for item in events}
        complete = all(seq in covered for seq in range(after_seq + 1, through_seq + 1))
        return events, complete

    @classmethod
    def _bounded_shared_events(
        cls, paths: list[Path], limit: int
    ) -> list[dict[str, Any]]:
        budget = max(256 * 1024, min(8 * 1024 * 1024, max(1, limit) * 16 * 1024))
        events: list[dict[str, Any]] = []
        for path in paths:
            events.extend(cls._tail_events_from_path(path, max_bytes=budget)[-limit:])
        events.sort(
            key=lambda item: (str(item.get("ts") or ""), int(item.get("seq") or 0))
        )
        return events[-limit:]

    @staticmethod
    def _ensure_append_boundary(path: Path) -> None:
        try:
            if not path.exists() or path.stat().st_size == 0:
                return
            with path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                terminated = handle.read(1) == b"\n"
            if not terminated:
                with path.open("ab") as handle:
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
        except OSError:
            return

    def _apply_events_to_state(
        self, cwd: str, fallback: dict[str, Any], events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        state = dict(fallback)
        state.update(
            {
                "schema_version": 1,
                "project": project_key(cwd),
                "seq": int(fallback.get("seq") or 0),
                "goal": fallback.get("goal"),
                "goal_ts": fallback.get("goal_ts"),
                "decisions": list(fallback.get("decisions") or []),
                "open_failures": list(fallback.get("open_failures") or []),
                "last_event_ts": fallback.get("last_event_ts"),
                "last_mutation_seq": int(fallback.get("last_mutation_seq") or 0),
                "last_mutation_ts": fallback.get("last_mutation_ts"),
            }
        )
        for event in events:
            seq = int(event.get("seq") or 0)
            if seq <= int(state["seq"]):
                continue
            state["seq"] = seq
            if event.get("ts"):
                state["last_event_ts"] = event["ts"]
            kind = event.get("kind")
            if kind == "goal" and event.get("text"):
                state["goal"] = event["text"]
                state["goal_ts"] = event.get("ts")
            elif kind == "decision":
                state["decisions"].append({"seq": seq, "text": event.get("text", "")})
            elif kind == "failure":
                state["open_failures"].append(
                    {
                        "seq": seq,
                        "text": event.get("text", ""),
                        "preconditions": event.get("preconditions", ""),
                    }
                )
            elif kind == "milestone":
                supersedes = set(event.get("supersedes_failures") or [])
                if supersedes:
                    state["open_failures"] = [
                        item
                        for item in state["open_failures"]
                        if item.get("seq") not in supersedes
                    ]
            elif kind == "mutation":
                # A1 freshness source: track the newest file-mutation position so
                # has_fresh_receipt can reject stale-green receipts. Additive to
                # the decision/failure/milestone reducers — never mutates them.
                state["last_mutation_seq"] = max(
                    int(state.get("last_mutation_seq") or 0), seq
                )
                if event.get("ts"):
                    state["last_mutation_ts"] = event["ts"]
        state["decisions"] = state["decisions"][-20:]
        state["open_failures"] = state["open_failures"][-20:]
        return state

    def _project_state(
        self,
        cwd: str,
        events: list[dict[str, Any]],
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback = fallback or {}
        state: dict[str, Any] = {
            "schema_version": 1,
            "project": project_key(cwd),
            "seq": 0,
            "goal": fallback.get("goal"),
            "goal_ts": fallback.get("goal_ts"),
            "decisions": [],
            "open_failures": [],
            "last_event_ts": fallback.get("last_event_ts"),
            "last_mutation_seq": int(fallback.get("last_mutation_seq") or 0),
            "last_mutation_ts": fallback.get("last_mutation_ts"),
        }
        failures: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        for event in events:
            seq = int(event.get("seq") or 0)
            state["seq"] = max(int(state["seq"]), seq)
            if event.get("ts"):
                state["last_event_ts"] = event["ts"]
            kind = event.get("kind")
            if kind == "goal" and event.get("text"):
                state["goal"] = event["text"]
                state["goal_ts"] = event.get("ts")
            elif kind == "decision":
                decisions.append({"seq": seq, "text": event.get("text", "")})
            elif kind == "failure":
                failures.append(
                    {
                        "seq": seq,
                        "text": event.get("text", ""),
                        "preconditions": event.get("preconditions", ""),
                    }
                )
            elif kind == "milestone":
                supersedes = set(event.get("supersedes_failures") or [])
                if supersedes:
                    failures = [
                        item for item in failures if item.get("seq") not in supersedes
                    ]
            elif kind == "mutation":
                state["last_mutation_seq"] = max(
                    int(state.get("last_mutation_seq") or 0), seq
                )
                if event.get("ts"):
                    state["last_mutation_ts"] = event["ts"]
        state["decisions"] = decisions[-20:]
        state["open_failures"] = failures[-20:]
        return state

    def append(
        self,
        cwd: str,
        kind: str,
        *,
        dedupe_key: str | None = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        directory = self._dir(cwd)
        directory.mkdir(parents=True, exist_ok=True)
        with _FileLock(directory / ".lock"):
            persisted = self._load_state(cwd)
            paths = self._shared_event_paths(cwd)
            tail_seq = self._last_shared_seq(paths)
            recent, state_complete = self._recent_shared_events(
                paths,
                after_seq=int(persisted.get("seq") or 0),
                through_seq=tail_seq,
            )
            state = (
                self._apply_events_to_state(cwd, persisted, recent)
                if state_complete
                else persisted
            )
            event_id = ""
            if dedupe_key:
                event_id = hashlib.sha256(
                    dedupe_key.encode("utf-8", "replace")
                ).hexdigest()
                if self._find_event_by_id(paths, event_id) is not None:
                    if state_complete and state != persisted:
                        atomic_write_json(self._state_path(cwd), state)
                    return None

            seq = max(tail_seq, int(persisted.get("seq") or 0)) + 1
            event: dict[str, Any] = {
                "schema_version": 1,
                "seq": seq,
                "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "kind": _safe_component(str(kind), 32),
            }
            if event_id:
                event["event_id"] = event_id
            # Additive fields flow through verbatim (secret/path-sanitized): the
            # A1 receipt_* fields + kind=="mutation" {path} are stamped by the
            # modules.py PostToolUse call site, and the B4 derived_from:list
            # provenance edge is stored here and indexed by taint_dependents().
            for key, value in fields.items():
                clean_key = _safe_component(str(key), 48)
                event[clean_key] = _sanitize_value(value)

            target = self._events(cwd)
            self._ensure_append_boundary(target)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())

            if state_complete:
                state = self._apply_events_to_state(cwd, state, [event])
                atomic_write_json(self._state_path(cwd), state)
            return event

    def replay(self, cwd: str, limit: int = 40) -> list[dict[str, Any]]:
        requested = max(1, min(int(limit), 200))
        result = self._bounded_shared_events(self._shared_event_paths(cwd), requested)
        combined = self._legacy_events(cwd) + result
        deduped: dict[str, dict[str, Any]] = {}
        for item in combined:
            identity = str(
                item.get("event_id")
                or json.dumps(
                    {
                        "ts": item.get("ts"),
                        "kind": item.get("kind"),
                        "text": item.get("text"),
                        "seq": item.get("seq"),
                        "tool": item.get("tool"),
                        "result_hash": item.get("result_hash"),
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            deduped[identity] = item
        return sorted(
            deduped.values(),
            key=lambda item: (str(item.get("ts") or ""), int(item.get("seq") or 0)),
        )[-requested:]

    def state(self, cwd: str) -> dict[str, Any]:
        persisted = self._load_state(cwd)
        paths = self._shared_event_paths(cwd)
        tail_seq, tail_ts = self._last_shared_marker(paths)
        state_matches_tail = (
            int(persisted.get("seq") or 0) >= tail_seq
            and str(persisted.get("last_event_ts") or "") == tail_ts
        )
        if state_matches_tail:
            shared_events: list[dict[str, Any]] = []
            shared = persisted
        else:
            shared_events = self._shared_events(cwd)
            shared = self._project_state(cwd, shared_events, persisted)
        legacy, _ = self._find_legacy(cwd)
        events = self._legacy_events(cwd)
        decisions = [
            {"seq": item.get("seq"), "text": item.get("text", "")}
            for item in events
            if item.get("kind") == "decision"
        ]
        shared["goal"] = self._latest_goal(
            shared_events=shared_events,
            legacy_events=events,
            shared_state=persisted,
            legacy_state=legacy,
        )
        shared["decisions"] = (decisions + list(shared.get("decisions") or []))[-20:]
        shared["open_failures"] = (
            list(legacy.get("open_failures") or [])
            + list(shared.get("open_failures") or [])
        )[-20:]
        shared["legacy_seq"] = int(legacy.get("seq") or 0)
        return shared

    @staticmethod
    def _timestamp(value: Any) -> float:
        if not value:
            return 0.0
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError):
            return 0.0

    def _latest_goal(
        self,
        *,
        shared_events: list[dict[str, Any]],
        legacy_events: list[dict[str, Any]],
        shared_state: dict[str, Any],
        legacy_state: dict[str, Any],
    ) -> str | None:
        candidates: list[tuple[float, int, str]] = []
        for order, event in enumerate(legacy_events + shared_events):
            if event.get("kind") == "goal" and event.get("text"):
                candidates.append(
                    (self._timestamp(event.get("ts")), order, str(event["text"]))
                )
        if legacy_state.get("goal") and not any(
            event.get("kind") == "goal" and event.get("text") for event in legacy_events
        ):
            candidates.append(
                (
                    self._timestamp(legacy_state.get("last_event_ts")),
                    -2,
                    str(legacy_state["goal"]),
                )
            )
        if shared_state.get("goal") and not any(
            event.get("kind") == "goal" and event.get("text") for event in shared_events
        ):
            candidates.append(
                (
                    self._timestamp(
                        shared_state.get("goal_ts") or shared_state.get("last_event_ts")
                    ),
                    -1,
                    str(shared_state["goal"]),
                )
            )
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[0], item[1]))[2]

    def _session_goal_path(self, session_id: str) -> Path:
        token = hashlib.sha256(
            str(session_id or "").encode("utf-8", "replace")
        ).hexdigest()[:20]
        return self.root.parent / "session-goals" / f"{token}.json"

    def _read_session_goal(self, session_id: str) -> str:
        data = read_json(self._session_goal_path(session_id), {})
        if isinstance(data, dict):
            goal = data.get("goal")
            if goal:
                return str(goal)
        return ""

    def _write_session_goal(self, session_id: str, text: str) -> None:
        payload: dict[str, Any] = {
            "goal": text,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        short = distill_goal_short(text)
        if short:
            payload["goal_short"] = short
        atomic_write_json(self._session_goal_path(session_id), payload)

    def set_goal(self, cwd: str, text: str, session_id: str | None = None) -> None:
        clean = redact_text(text, redact_paths=True, max_chars=500).strip()
        if not clean:
            return
        # The append keeps a durable project audit trail; the active goal used
        # for re-injection/replay is resolved per-session to stop concurrent
        # sessions in one cwd from stomping each other's goal.
        self.append(cwd, "goal", text=clean)
        if _session_isolatable(session_id):
            self._write_session_goal(cast(str, session_id), clean)

    def goal(self, cwd: str, session_id: str | None = None) -> str:
        # A provided session_id requests STRICT per-session isolation: return
        # that session's own goal or empty, never another session's. An
        # unidentified session ("unknown"/empty) cannot be isolated, so decline
        # rather than serve a shared goal. Only the no-session form (None, for
        # legacy inspection) falls back to the project-latest goal.
        if session_id is not None:
            if _session_isolatable(session_id):
                return self._read_session_goal(session_id)
            return ""
        goal = self.state(cwd).get("goal")
        if goal:
            return str(goal)
        return ""

    def pointer(self, cwd: str) -> dict[str, Any]:
        state = self.state(cwd)
        return {
            "project": project_key(cwd),
            "seq": int(state.get("seq") or 0),
            "legacy_seq": int(state.get("legacy_seq") or 0),
        }

    # ------------------------------------------------------------------
    # A1 · receipt + freshness query surface (SI-1) and B4 · taint (SI-5-adj).
    # All additive + read-mostly; consumed by modules.py (ClaimWarning v2) and
    # by the external falsification trigger. Bounded, chronological scans.
    # ------------------------------------------------------------------

    def _scan_events(
        self, cwd: str, *, limit: int = _RECEIPT_SCAN_LIMIT
    ) -> list[dict[str, Any]]:
        """Bounded, ts+seq-sorted recent events for the receipt/taint queries."""
        return self.replay(cwd, limit=limit)

    def last_mutation_seq(self, cwd: str, turn_id: str = "") -> int:
        """Highest seq of a kind=='mutation' event (optionally scoped to a turn).

        Powers freshness ordering: a receipt is 'fresh' only if it post-dates the
        last file mutation of the turn (kills stale-green). Mirrors the lenient
        turn match used by has_verification (an empty turn_id counts for any turn).
        """
        latest = 0
        for item in self._scan_events(cwd):
            if item.get("kind") != "mutation":
                continue
            if turn_id and item.get("turn_id") not in {"", turn_id}:
                continue
            latest = max(latest, _as_int(item.get("seq")))
        return latest

    def _receipts(self, cwd: str, turn_id: str = "") -> list[Receipt]:
        receipts: list[Receipt] = []
        for item in self._scan_events(cwd):
            if item.get("kind") != "tool_result":
                continue
            # EVIDENCE is matched STRICTLY: unlike the mutation floor (where a
            # blank turn stays a wildcard so unattributed writes still
            # invalidate), an unattributed receipt must not substantiate some
            # other turn's claim. Asymmetric on purpose — both directions
            # fail closed.
            if turn_id and str(item.get("turn_id") or "") != turn_id:
                continue
            receipt = _receipt_from_event(item)
            if receipt is not None:
                receipts.append(receipt)
        return receipts

    def has_fresh_receipt(
        self,
        cwd: str,
        turn_id: str,
        required_classes: tuple[str, ...],
        *,
        min_seq: int | None = None,
    ) -> bool:
        """True when the LATEST fresh receipt of some required class passed.

        Fresh means seq strictly greater than the last mutation in this cwd (and
        than min_seq, when given) — the stale-green killer (SI-1 freshness rule).
        ANY-of over required_classes — one fresh passing class substantiates,
        matching the has_verification any-green shim — but only the newest
        receipt PER CLASS is consulted, so a later failing rerun revokes an
        earlier green instead of being outvoted by it. The mutation floor is
        cwd-wide, not turn-scoped: a write from another turn/session changed the
        same tree, so it invalidates the receipt too."""
        required = {name for name in (required_classes or ()) if name}
        if not required:
            return False
        floor = self.last_mutation_seq(cwd)
        if min_seq is not None:
            floor = max(floor, _as_int(min_seq))
        latest: dict[str, Receipt] = {}
        for receipt in self._receipts(cwd, turn_id):
            if receipt.receipt_class not in required or receipt.seq <= floor:
                continue
            current = latest.get(receipt.receipt_class)
            if current is None or receipt.seq >= current.seq:
                latest[receipt.receipt_class] = receipt
        return any(receipt.status == "pass" for receipt in latest.values())

    def receipt_for_fingerprint(self, cwd: str, fingerprint: str) -> Receipt | None:
        """Most-recent typed receipt whose argv-fingerprint matches (repro-gate)."""
        if not fingerprint:
            return None
        target = str(fingerprint)
        match: Receipt | None = None
        for item in self._scan_events(cwd):
            if item.get("kind") != "tool_result":
                continue
            if str(item.get("receipt_fp") or "") != target:
                continue
            receipt = _receipt_from_event(item)
            if receipt is not None:
                match = receipt
        return match

    def last_failed_fingerprint(self, cwd: str, turn_id: str = "") -> str | None:
        """Argv-fingerprint of the most recent FAILED typed receipt, or None.

        The repro-fingerprint fix-gate reads this to learn WHICH failing command
        a 'fixed' claim must prove green, then pairs it with
        receipt_for_fingerprint to check for a later passing rerun of that same
        argv. Scans the same bounded, ts+seq-ordered window as the sibling
        receipt queries and returns the fingerprint of the LATEST tool_result
        whose reconstructed receipt is a fail with a non-empty fingerprint. Turn
        scoping mirrors last_mutation_seq (an empty turn_id counts for any turn).
        Fail-open: a scan/parse error yields None rather than raising into the
        hook."""
        try:
            match: str | None = None
            for item in self._scan_events(cwd):
                if item.get("kind") != "tool_result":
                    continue
                if turn_id and item.get("turn_id") not in {"", turn_id}:
                    continue
                receipt = _receipt_from_event(item)
                if (
                    receipt is not None
                    and receipt.status == "fail"
                    and receipt.fingerprint
                ):
                    match = receipt.fingerprint
            return match
        except Exception:
            return None

    def _has_legacy_verification(self, cwd: str, turn_id: str = "") -> bool:
        # Pre-receipt behavior, kept verbatim: any tool_result flagged
        # verified==True (no typed receipt fields). Ledgers written before the
        # modules.py receipt-stamping lane lands still satisfy the done-gate.
        # The "no typed receipt fields" half is now ENFORCED, not just
        # documented: an event from the receipt lane is judged by its receipt
        # (has_fresh_receipt) alone. Otherwise the coarse verified flag — which
        # the caller stamps on every event — overrode the very stale-green and
        # fail-revokes-pass rules it sits beside (a receipt_status=="fail" event
        # still answered True here).
        for item in reversed(self.replay(cwd, limit=60)):
            if item.get("kind") != "tool_result":
                continue
            if turn_id and item.get("turn_id") not in {"", turn_id}:
                continue
            if any(key.startswith("receipt_") for key in item):
                continue
            if item.get("verified") is True:
                return True
        return False

    def has_verification(self, cwd: str, turn_id: str = "") -> bool:
        # Thin back-compat shim (SI-1): delegate to has_fresh_receipt over ALL
        # receipt classes, falling back to the legacy verified==True signal for
        # events written before receipt fields existed. test_modules.py asserts it.
        if self.has_fresh_receipt(cwd, turn_id, RECEIPT_CLASSES):
            return True
        return self._has_legacy_verification(cwd, turn_id)

    def taint_dependents(self, cwd: str, falsified_ref: str) -> list[int]:
        """B4: return seqs of events whose derived_from lists falsified_ref, and
        drop a kind=='taint' marker (fail-open). Single-level by design — the
        external falsification TRIGGER (note.py / fresh-context-verify) owns DAG
        traversal by re-invoking with each dependent's own identifier."""
        if not falsified_ref:
            return []
        ref = str(falsified_ref)
        dependents: list[int] = []
        for item in self._scan_events(cwd, limit=_TAINT_SCAN_LIMIT):
            derived = item.get("derived_from")
            if not isinstance(derived, list):
                continue
            if any(str(entry) == ref for entry in derived):
                seq = _as_int(item.get("seq"))
                if seq:
                    dependents.append(seq)
        dependents = sorted(set(dependents))
        try:
            self.append(
                cwd,
                "taint",
                dedupe_key=f"taint:{ref}:{dependents}",
                falsified_ref=ref,
                tainted_seqs=dependents,
            )
        except Exception:
            # Advisory marker only — never let taint bookkeeping raise into a hook.
            pass
        return dependents

    def _find_legacy(self, cwd: str) -> tuple[dict[str, Any], Path | None]:
        key = project_key(cwd)
        if key in self._legacy_cache:
            return self._legacy_cache[key]
        if not self.legacy_root.exists():
            result = ({}, None)
            self._legacy_cache[key] = result
            return result
        target = os.path.normcase(canonical_project_path(cwd))
        try:
            candidates = list(self.legacy_root.glob("*/state.json"))
        except OSError:
            result = ({}, None)
            self._legacy_cache[key] = result
            return result
        for path in candidates[:200]:
            raw_state = read_json(path, {})
            if not isinstance(raw_state, dict):
                continue
            paths = [raw_state.get("project"), *(raw_state.get("aliases") or [])]
            for candidate in paths:
                if (
                    candidate
                    and os.path.normcase(canonical_project_path(str(candidate)))
                    == target
                ):
                    safe_state = _sanitize_value(raw_state)
                    result = (
                        safe_state if isinstance(safe_state, dict) else {},
                        path.parent,
                    )
                    self._legacy_cache[key] = result
                    return result
        result = ({}, None)
        self._legacy_cache[key] = result
        return result

    def _legacy_events(self, cwd: str) -> list[dict[str, Any]]:
        _, directory = self._find_legacy(cwd)
        if directory is None:
            return []
        path = directory / "events.jsonl"
        if not path.exists():
            return []
        lines: list[str] = []
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.strip():
                        lines.append(line)
        except OSError:
            return []
        result: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            cleaned = _sanitize_value(item)
            if isinstance(cleaned, dict):
                result.append(cleaned)
        return result
