"""Live measurement of the installed client binary's non-interactive surface."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from flags import (
    CLAUDE_DOC_FLAGS,
    CLAUDE_DOC_SHORT,
    COMMANDS,
    CURSOR_DOC_FLAGS,
    CURSOR_DOC_SHORT,
    DUMMY_VALUE_ARGV,
    INVENTED_FLAG,
    VALUE_FLAGS,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DISPATCH = REPO / "command-center/p2-wave/seed-stage/dispatch_cursor.py"

UNKNOWN_RE = re.compile(r"unknown option|unknown command", re.I)
MISSING_RE = re.compile(r"argument missing", re.I)
INVALID_RE = re.compile(
    r"Invalid --|argument '.+' is invalid|Allowed (?:choices|values)", re.I
)
NO_PROMPT_RE = re.compile(r"No prompt provided for print mode", re.I)
DEPRECATED_RE = re.compile(r"deprecated", re.I)
DID_YOU_MEAN_RE = re.compile(r"Did you mean", re.I)
HELP_OPT_RE = re.compile(
    r"^[ \t]+(?:-([A-Za-z0-9]),[ \t]+)?(--[a-z0-9-]+)(?:[ \t]+[<\[][^>\]]+[>\]])?",
    re.M,
)
HELP_CMD_RE = re.compile(
    r"^[ \t]+([a-z][a-z0-9-]*(?:\|[a-z][a-z0-9-]*)*)[ \t]{2,}",
    re.M,
)
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|refresh.?token|access.?token)"
    r"\s*[:=]\s*\S+"
)

DEFAULT_TIMEOUT = 8.0


def redact(text: str, limit: int | None = 800) -> str:
    if not text:
        return ""
    out = SECRET_RE.sub(r"\1=<redacted>", text).replace("\r\n", "\n")
    if limit is None:
        return out
    return out[:limit]


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def which_agent() -> Path:
    env = os.environ.get("CURSOR_AGENT_BIN")
    if env and Path(env).is_file():
        return Path(env).resolve()
    fixture = HERE / "fixtures" / "bin" / "agent"
    if fixture.is_file():
        try:
            fixture.chmod(0o755)
        except OSError:
            pass
        return fixture.resolve()
    for c in (
        str(Path.home() / ".local" / "bin" / "agent"),
        str(Path.home() / ".local" / "bin" / "cursor-agent"),
        "/usr/local/bin/agent",
        "/usr/local/bin/cursor-agent",
    ):
        p = Path(c)
        if p.is_file():
            return p.resolve()
    found = shutil.which("agent") or shutil.which("cursor-agent")
    if not found:
        raise FileNotFoundError("installed agent binary not found")
    return Path(found).resolve()


def install_dir(bin_path: Path) -> Path:
    return bin_path.parent


def invoke(
    bin_path: Path,
    argv: list[str],
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    cmd = [str(bin_path), *argv]
    try:
        p = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
            cwd=str(REPO),
        )
        stdout = redact(p.stdout or "")
        stderr = redact(p.stderr or "")
        return {
            "argv": argv,
            "exit_code": p.returncode,
            "timed_out": False,
            "stdout_tail": stdout[-400:],
            "stderr_tail": stderr[-400:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = redact((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        stderr = redact((exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
        return {
            "argv": argv,
            "exit_code": None,
            "timed_out": True,
            "stdout_tail": stdout[-400:],
            "stderr_tail": stderr[-400:],
        }


def classify(run: dict[str, Any]) -> tuple[str, str]:
    text = f"{run.get('stderr_tail') or ''}\n{run.get('stdout_tail') or ''}"
    if UNKNOWN_RE.search(text):
        return "rejected", "unknown-option"
    if run.get("timed_out"):
        # Parser accepted the token; the process then blocked. Not an unknown flag.
        return "accepted", "parser-accepted-then-timeout"
    if MISSING_RE.search(text):
        return "accepted", "argument-missing"
    if INVALID_RE.search(text):
        return "accepted", "invalid-value"
    if NO_PROMPT_RE.search(text):
        return "accepted", "print-mode-no-prompt"
    if DEPRECATED_RE.search(text):
        return "accepted", "deprecated-known-flag"
    if "not a git repository" in text.lower():
        return "accepted", "known-flag-runtime-error"
    if "requires --output-format" in text:
        return "accepted", "known-flag-requires-peer"
    if run.get("exit_code") == 0:
        return "accepted", "exit-0"
    if DID_YOU_MEAN_RE.search(text) and UNKNOWN_RE.search(text):
        return "rejected", "unknown-option"
    return "accepted", "non-unknown-error"


def _kind(flag: str, sources: list[str], verdict: str) -> str:
    if flag == INVENTED_FLAG:
        return "negative-control"
    has_docs = any(s in sources for s in ("cursor-docs", "claude-docs", "runner", "help"))
    if verdict == "rejected" and has_docs:
        return "doc-vs-binary"
    if verdict == "accepted":
        if "help" in sources and "cursor-docs" in sources:
            return "capability"
        if "help" in sources:
            return "help-not-in-cursor-docs"
        if "claude-docs" in sources:
            return "other-product-doc-but-accepted"
        return "undocumented-accepted"
    return "undocumented-rejected"


def argv_for(flag: str) -> list[str]:
    if flag in DUMMY_VALUE_ARGV:
        return list(DUMMY_VALUE_ARGV[flag])
    if flag in VALUE_FLAGS:
        return [flag]
    return [flag]


def parse_help(text: str) -> dict[str, Any]:
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in HELP_OPT_RE.finditer(text):
        short = f"-{m.group(1)}" if m.group(1) else ""
        long = m.group(2)
        if long in seen:
            continue
        seen.add(long)
        options.append({"long": long, "short": short})
    commands: list[str] = []
    in_cmds = False
    for line in text.splitlines():
        if line.strip().startswith("Commands:"):
            in_cmds = True
            continue
        if in_cmds and line.strip() and not line.startswith(" "):
            in_cmds = False
        if in_cmds:
            m = HELP_CMD_RE.match(line)
            if m:
                for part in m.group(1).split("|"):
                    commands.append(part)
    return {"options": options, "commands": commands, "text": text}


def runner_flags() -> list[str]:
    if not DISPATCH.is_file():
        return []
    text = DISPATCH.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'"--([a-z0-9-]+)"', text)))


def byte_count(path: Path, needle: bytes) -> int:
    if not path.is_file():
        return 0
    try:
        return path.read_bytes().count(needle)
    except OSError:
        return 0


def scan_install_for(install: Path, needle: str) -> dict[str, Any]:
    n = needle.encode("utf-8")
    hits: list[dict[str, Any]] = []
    total = 0
    for p in sorted(install.glob("*.js")):
        c = byte_count(p, n)
        if c:
            hits.append({"path": p.name, "count": c})
            total += c
    return {"needle": needle, "file_hits": hits, "total": total}


def measure() -> dict[str, Any]:
    bin_path = which_agent()
    inst = install_dir(bin_path)
    claude_path = shutil.which("claude")
    help_run = invoke(bin_path, ["--help"], timeout=6)
    help_text = (help_run.get("stdout_tail") or "") + (help_run.get("stderr_tail") or "")
    # --help stdout can exceed the tail; re-read full help.
    full_help = invoke_full_help(bin_path)
    parsed = parse_help(full_help)
    help_sha = digest_text(full_help)
    version_run = invoke(bin_path, ["--version"], timeout=6)
    version = (version_run.get("stdout_tail") or "").strip().splitlines()[0] if version_run.get("exit_code") == 0 else ""

    help_longs = [o["long"] for o in parsed["options"]]
    help_shorts = [o["short"] for o in parsed["options"] if o.get("short")]
    runner = ["--" + x if not x.startswith("-") else x for x in runner_flags()]
    # Union of documented surfaces + live help + runner + invented control.
    to_run: list[str] = []
    for flag in (
        list(CURSOR_DOC_FLAGS)
        + list(CURSOR_DOC_SHORT)
        + list(CLAUDE_DOC_FLAGS)
        + list(CLAUDE_DOC_SHORT)
        + help_longs
        + help_shorts
        + runner
        + [INVENTED_FLAG, "--endpoint", "-e", "--auto-review", "--add-dir"]
    ):
        if flag and flag not in to_run:
            to_run.append(flag)

    rows: list[dict[str, Any]] = []
    for flag in to_run:
        argv = argv_for(flag)
        run = invoke(bin_path, argv)
        verdict, reason = classify(run)
        sources: list[str] = []
        if flag in CURSOR_DOC_FLAGS or flag in CURSOR_DOC_SHORT:
            sources.append("cursor-docs")
        if flag in CLAUDE_DOC_FLAGS or flag in CLAUDE_DOC_SHORT:
            sources.append("claude-docs")
        if flag in help_longs or flag in help_shorts:
            sources.append("help")
        if flag in runner:
            sources.append("runner")
        if flag == INVENTED_FLAG:
            sources.append("negative-control")
        kind = _kind(flag, sources, verdict)
        rows.append(
            {
                "flag": flag,
                "argv": argv,
                "sources": sources,
                "in_help": flag in help_longs or flag in help_shorts,
                "verdict": verdict,
                "reason": reason,
                "kind": kind,
                "exit_code": run["exit_code"],
                "timed_out": run["timed_out"],
                "stderr_tail": run["stderr_tail"],
            }
        )

    cmd_rows: list[dict[str, Any]] = []
    help_cmds = set(parsed["commands"])
    for cmd in COMMANDS:
        run = invoke(bin_path, [cmd, "--help"], timeout=6)
        verdict, reason = classify(run)
        cmd_rows.append(
            {
                "command": cmd,
                "argv": [cmd, "--help"],
                "in_help": cmd in help_cmds,
                "verdict": verdict,
                "reason": reason,
                "exit_code": run["exit_code"],
                "stderr_tail": run["stderr_tail"],
                "stdout_tail": run["stdout_tail"][:200],
            }
        )

    invented = next(r for r in rows if r["flag"] == INVENTED_FLAG)
    ctrl_req = scan_install_for(inst, "control_request")
    ctrl_resp = scan_install_for(inst, "control_response")
    perm_prompt = scan_install_for(inst, "permission-prompt-tool")

    of_ok = invoke(bin_path, ["--output-format", "stream-json"])
    of_bad = invoke(bin_path, ["--output-format", "res0015-not-a-format"])
    sandbox_bad = invoke(bin_path, ["--sandbox", "not-a-mode"])
    mode_bad = invoke(bin_path, ["--mode", "agent"])
    sandbox_ok_row = next((r for r in rows if r["flag"] == "--sandbox"), None)

    accepted = [r for r in rows if r["verdict"] == "accepted"]
    rejected = [r for r in rows if r["verdict"] == "rejected"]
    contradictions = [r for r in rows if r["kind"] == "doc-vs-binary"]
    runner_rows = [r for r in rows if "runner" in r["sources"]]

    return {
        "binary": {
            "path": str(bin_path),
            "install_dir": str(inst),
            "version": version,
            "version_exit": version_run["exit_code"],
            "claude_on_path": claude_path,
            "help_sha256": help_sha,
            "help_bytes": len(full_help.encode("utf-8")),
            "help_option_count": len(parsed["options"]),
            "help_command_count": len(parsed["commands"]),
            "help_options": parsed["options"],
            "help_commands": parsed["commands"],
        },
        "flag_table": rows,
        "command_table": cmd_rows,
        "counts": {
            "executed": len(rows),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "doc_vs_binary": len(contradictions),
            "commands_executed": len(cmd_rows),
        },
        "invented": invented,
        "runner_flags": runner_rows,
        "output_format": {
            "stream_json": {
                "verdict": classify(of_ok)[0],
                "reason": classify(of_ok)[1],
                "stderr_tail": of_ok["stderr_tail"],
            },
            "invented_value": {
                "verdict": classify(of_bad)[0],
                "reason": classify(of_bad)[1],
                "stderr_tail": of_bad["stderr_tail"],
            },
        },
        "sandbox": {
            "disabled_missing_arg": sandbox_ok_row,
            "invented_value": {
                "verdict": classify(sandbox_bad)[0],
                "reason": classify(sandbox_bad)[1],
                "stderr_tail": sandbox_bad["stderr_tail"],
            },
        },
        "mode_agent_value": {
            "verdict": classify(mode_bad)[0],
            "reason": classify(mode_bad)[1],
            "stderr_tail": mode_bad["stderr_tail"],
        },
        "control_request_scan": ctrl_req,
        "control_response_scan": ctrl_resp,
        "permission_prompt_tool_scan": perm_prompt,
        "help_run": {
            "exit_code": help_run["exit_code"],
            "timed_out": help_run["timed_out"],
        },
    }


def invoke_full_help(bin_path: Path) -> str:
    p = subprocess.run(
        [str(bin_path), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=8,
        start_new_session=True,
        cwd=str(REPO),
    )
    # Full --help must not use the 800-char invoke tail. Truncation previously
    # left help_option_count=5 and marked documented flags in_help=false.
    return redact((p.stdout or "") + (p.stderr or ""), limit=None)


def sh_invented(bin_path: Path) -> dict[str, Any]:
    """Second shell: /bin/sh, not Python subprocess argv array."""
    p = subprocess.run(
        ["/bin/sh", "-c", "exec \"$1\" --res0015-invented-flag-xyzzy", "sh", str(bin_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=8,
        start_new_session=True,
        cwd=str(REPO),
    )
    run = {
        "argv": ["--res0015-invented-flag-xyzzy"],
        "exit_code": p.returncode,
        "timed_out": False,
        "stdout_tail": redact(p.stdout or ""),
        "stderr_tail": redact(p.stderr or ""),
        "shell": "/bin/sh",
    }
    v, r = classify(run)
    run["verdict"] = v
    run["reason"] = r
    return run
