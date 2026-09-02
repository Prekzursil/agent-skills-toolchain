"""mcp__codex__codex contract rail: prompt-by-file, foreground, AND-gate.

Logical argv is always the MCP tool line (recorded). Spawn is a local backend
that implements the same AND-gate. Exit 0 alone is severed-stream, not SUCCESS.
Never parse the [codex] progress stream as a result. Never convert 429/529
into REFUTED. Never --background.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from record_schema import validation_result  # noqa: E402
from windows_argv import OS_ERROR_206, exceeds_win_arg_limit, win_command_line  # noqa: E402

MCP_TOOL = "mcp__codex__codex"
BACKGROUND_MARKERS = ("started in the background", "Check /codex:status")


def build_mcp_argv(
    *,
    prompt_file: Path | None,
    prompt_inline: str | None,
    output_last_message: Path,
    ignore_user_config: bool = True,
    background: bool = False,
) -> list[str]:
    argv = [MCP_TOOL]
    if ignore_user_config:
        argv.append("--ignore-user-config")
    if background:
        argv.append("--background")
    if prompt_file is not None:
        argv.extend(["--prompt-file", str(prompt_file)])
    elif prompt_inline is not None:
        argv.extend(["--prompt", prompt_inline])
    else:
        raise ValueError("prompt_file or prompt_inline required")
    argv.extend(["--output-last-message", str(output_last_message)])
    return argv


def _and_gate(
    exit_code: int,
    output_path: Path,
    *,
    command_string: str,
) -> dict[str, Any]:
    if "--background" in command_string.split():
        return {
            "classification": "background-ban",
            "schema_validation": {"ok": False, "errors": ["not-run"]},
            "verdict": None,
            "record": None,
            "output_bytes": 0,
            "note": "blocking foreground only; --background is forbidden",
        }
    if exit_code in (429, 529):
        return {
            "classification": "vendor-quota",
            "schema_validation": {"ok": False, "errors": ["not-run"]},
            "verdict": None,
            "record": None,
            "output_bytes": output_path.stat().st_size if output_path.is_file() else 0,
            "note": "vendor-side 429/529 is not a REFUTED",
        }
    if exit_code != 0:
        return {
            "classification": f"exit-{exit_code}",
            "schema_validation": {"ok": False, "errors": ["not-run"]},
            "verdict": None,
            "record": None,
            "output_bytes": output_path.stat().st_size if output_path.is_file() else 0,
        }
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        return {
            "classification": "severed-stream",
            "schema_validation": {"ok": False, "errors": ["missing-or-empty-output-last-message"]},
            "verdict": None,
            "record": None,
            "output_bytes": 0,
            "note": "exit 0 alone is SEVERED, not SUCCESS",
        }
    text = output_path.read_text(encoding="utf-8")
    if any(m in text for m in BACKGROUND_MARKERS):
        return {
            "classification": "severed-stream",
            "schema_validation": {"ok": False, "errors": ["fire-and-forget-markers"]},
            "verdict": None,
            "record": None,
            "output_bytes": len(text.encode("utf-8")),
            "note": "output-last-message is a progress/status stream, not a record",
        }
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return {
            "classification": "severed-stream",
            "schema_validation": {"ok": False, "errors": ["unparsable-output-last-message"]},
            "verdict": None,
            "record": None,
            "output_bytes": len(text.encode("utf-8")),
            "note": "never parse the [codex] progress stream as a result",
        }
    schema = validation_result(doc)
    if not schema["ok"]:
        return {
            "classification": "schema-invalid",
            "schema_validation": schema,
            "verdict": None,
            "record": doc if isinstance(doc, dict) else None,
            "output_bytes": len(text.encode("utf-8")),
        }
    verdict = doc.get("verdict") if isinstance(doc, dict) else None
    return {
        "classification": "SUCCESS",
        "schema_validation": schema,
        "verdict": verdict,
        "record": doc,
        "output_bytes": len(text.encode("utf-8")),
    }


def dispatch(
    *,
    prompt_file: Path | None = None,
    prompt_inline: str | None = None,
    output_last_message: Path,
    backend: str = "confirm",
    ignore_user_config: bool = True,
    background: bool = False,
    claim_id: str = "",
) -> dict[str, Any]:
    argv = build_mcp_argv(
        prompt_file=prompt_file,
        prompt_inline=prompt_inline,
        output_last_message=output_last_message,
        ignore_user_config=ignore_user_config,
        background=background,
    )
    cmdline = win_command_line(argv)
    rec: dict[str, Any] = {
        "claim_id": claim_id,
        "tool": MCP_TOOL,
        "command_string": cmdline,
        "argv": argv,
        "prompt_file_path": None if prompt_file is None else str(prompt_file).replace("\\", "/"),
        "output_last_message_path": str(output_last_message).replace("\\", "/"),
        "ignore_user_config": ignore_user_config,
        "background": background,
        "cmdline_chars": len(cmdline),
    }
    if background:
        rec.update(
            {
                "exit_code": None,
                "output_bytes": 0,
                "schema_validation": {"ok": False, "errors": ["not-run"]},
                "classification": "background-ban",
                "verdict": None,
                "record": None,
            }
        )
        return rec
    if exceeds_win_arg_limit(cmdline):
        rec.update(
            {
                "exit_code": OS_ERROR_206,
                "output_bytes": 0,
                "schema_validation": {"ok": False, "errors": ["not-run"]},
                "classification": "win-arg-limit",
                "verdict": None,
                "record": None,
                "note": (
                    "CreateProcessW cap 32767 including NUL; inline prompt not spawned. "
                    "Retry once with --ignore-user-config and --prompt-file."
                ),
            }
        )
        return rec

    output_last_message.parent.mkdir(parents=True, exist_ok=True)
    if output_last_message.exists():
        output_last_message.unlink()
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "confirmer.py"),
        "--prompt-file",
        str(prompt_file or HERE / "fixtures" / "empty-prompt.json"),
        "--output-last-message",
        str(output_last_message),
        "--mode",
        backend,
    ]
    proc = subprocess.run(cmd, cwd=str(HERE.parents[3]), capture_output=True, text=True, timeout=60)
    rec["backend_argv"] = cmd
    rec["backend_stdout_ignored"] = (proc.stdout or "")[-500:]
    rec["backend_stderr"] = (proc.stderr or "")[-2000:]
    rec["exit_code"] = proc.returncode
    rec.update(_and_gate(proc.returncode, output_last_message, command_string=cmdline))
    return rec
