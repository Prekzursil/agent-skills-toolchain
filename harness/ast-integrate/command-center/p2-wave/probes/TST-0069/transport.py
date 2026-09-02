#!/usr/bin/env python3
"""Transport-selection rule for apostrophe-bearing agent commands.

A naive Bash tool wraps the agent command in single quotes. A literal
apostrophe in a python -c body, a grep pattern, or a heredoc closes that
outer quote and the call dies before the intended payload bytes run.

Rule: if the payload (or the command body) contains an apostrophe, a
here-string terminator, or a control byte, do not inline it. Write the
bytes with the Write tool (or Path.write_bytes) and pass a path via
argv, grep -F -f, or -F (git commit -F shape).

This module both REPRODUCES the wrap failure (control) and lints
agent-authored command strings so the file route is selected.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
APOSTROPHE = "'"
HERE_STRING_OPEN = "@" + APOSTROPHE
HERE_STRING_CLOSE = APOSTROPHE + "@"
# Commit-message / prose payload that has broken sessions in the estate.
PAYLOAD = "don't ship; it's not ready"

INLINE_SHAPES = (
    "python-c",
    "grep",
    "heredoc",
)

_INLINE_RE = (
    re.compile(r"python3?\s+-c\b"),
    re.compile(r"(?<!\s-f)\bgrep\b"),
    re.compile(r"<<"),
    re.compile(r"\bcommit\b[^\n]*\s-m\b"),
)
_FILE_RE = (
    re.compile(r"(?:^|\s)-F\s+\S+"),
    re.compile(r"\bgrep\s+-F\s+-f\s+\S+"),
    re.compile(r"python3?\s+\S+\.py\b(?!\s+-c\b)"),
)


def payload_sha256(text: str = PAYLOAD) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def needs_file_transport(text: str) -> bool:
    if APOSTROPHE in text:
        return True
    if HERE_STRING_OPEN in text or HERE_STRING_CLOSE in text:
        return True
    for ch in text:
        if ord(ch) < 32 and ch not in "\t\n":
            return True
    return False


def select_transport(text: str) -> str:
    return "file" if needs_file_transport(text) else "inline"


def naive_bash_tool_wrap(command: str) -> str:
    """Parent-shell script a naive Bash tool emits: bash -c '<command>'."""
    return "bash -c " + APOSTROPHE + command + APOSTROPHE


def run_wrapped(command: str, *, timeout: float = 8) -> dict:
    """Run the naive wrap via argv so THIS process is not the thing that breaks.

    An unclosed quote/heredoc that hangs is itself the wrap defect: treat
    TimeoutExpired as a non-zero wrap failure rather than crashing the probe.
    """
    script = naive_bash_tool_wrap(command)
    try:
        proc = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = "TimeoutExpired: naive single-quote wrap hung (unclosed quote/heredoc)"
        returncode = 124
    return {
        "command": command,
        "wrapped_script": script,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_empty": stdout == "",
        "payload_in_stdout": PAYLOAD in stdout,
        "ok": returncode == 0,
    }


def inline_python_c(payload: str = PAYLOAD) -> str:
    """Agent-typical python -c with single-quoted code and an apostrophe payload."""
    return "python3 -c " + APOSTROPHE + "print(" + json.dumps(payload) + ")" + APOSTROPHE


def inline_grep(payload: str, haystack: Path) -> str:
    return "grep -F " + APOSTROPHE + payload + APOSTROPHE + " " + str(haystack)


def inline_heredoc(payload: str = PAYLOAD) -> str:
    return (
        "python3 - <<"
        + APOSTROPHE
        + "EOF"
        + APOSTROPHE
        + "\n"
        + payload
        + "\nEOF\n"
    )


def looks_inline(command: str) -> bool:
    return any(rx.search(command) for rx in _INLINE_RE)


def looks_file_route(command: str) -> bool:
    return any(rx.search(command) for rx in _FILE_RE)


def lint_command(command: str, payload: str | None = None) -> dict:
    """Flag agent-authored commands that would break naive single-quote wrap."""
    hits: list[str] = []
    if payload is not None and needs_file_transport(payload) and payload in command:
        hits.append("payload-inlined")
    if APOSTROPHE in command:
        if looks_inline(command):
            hits.append("apostrophe-in-inline-form")
        elif not looks_file_route(command):
            hits.append("apostrophe-in-command-body")
        else:
            # A file-route command that still contains an apostrophe (path or
            # leftover payload) is wrap-unsafe; the path itself must be clean.
            hits.append("apostrophe-in-file-route-command")
    transport = "file" if (hits or (payload is not None and needs_file_transport(payload))) else "inline"
    return {
        "command": command,
        "hits": hits,
        "ok": not hits,
        "select_transport": transport,
    }


def load_corpus(path: Path | None = None) -> dict:
    target = path or (HERE / "fixtures" / "agent-commands.json")
    return json.loads(target.read_text(encoding="utf-8"))


def lint_corpus(corpus: dict | None = None) -> dict:
    doc = corpus if corpus is not None else load_corpus()
    bad_rows = []
    good_rows = []
    for row in doc.get("bad") or []:
        rec = lint_command(row["command"], row.get("payload"))
        rec["id"] = row["id"]
        rec["expected_ok"] = False
        rec["matched_expectation"] = rec["ok"] is False
        bad_rows.append(rec)
    for row in doc.get("good") or []:
        rec = lint_command(row["command"], row.get("payload"))
        rec["id"] = row["id"]
        rec["expected_ok"] = True
        rec["matched_expectation"] = rec["ok"] is True
        good_rows.append(rec)
    return {
        "bad": bad_rows,
        "good": good_rows,
        "bad_all_fired": all(r["matched_expectation"] for r in bad_rows) and bool(bad_rows),
        "good_all_silent": all(r["matched_expectation"] for r in good_rows) and bool(good_rows),
        "ok": (
            bool(bad_rows)
            and bool(good_rows)
            and all(r["matched_expectation"] for r in bad_rows)
            and all(r["matched_expectation"] for r in good_rows)
        ),
    }


def prepare_workspace(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    payload_path = root / "payload.txt"
    payload_path.write_text(PAYLOAD, encoding="utf-8")
    haystack = root / "haystack.txt"
    haystack.write_text("alpha\n" + PAYLOAD + "\nomega\n", encoding="utf-8")
    pattern = root / "pattern.txt"
    pattern.write_text(PAYLOAD + "\n", encoding="utf-8")
    echo_py = HERE / "echo_payload.py"
    consumer = HERE / "dash_f_consumer.py"
    return {
        "payload": payload_path,
        "haystack": haystack,
        "pattern": pattern,
        "echo_py": echo_py,
        "consumer": consumer,
    }


def run_inline_controls(haystack: Path) -> dict:
    cases = {
        "python-c": inline_python_c(PAYLOAD),
        "grep": inline_grep(PAYLOAD, haystack),
        "heredoc": inline_heredoc(PAYLOAD),
    }
    out = {}
    for name, command in cases.items():
        rec = run_wrapped(command)
        rec["shape"] = name
        rec["lint"] = lint_command(command, PAYLOAD)
        rec["control_holds"] = (
            rec["returncode"] != 0
            and not rec["payload_in_stdout"]
            and rec["lint"]["ok"] is False
        )
        out[name] = rec
    return out


def run_file_routes(paths: dict[str, Path]) -> dict:
    cases = {
        "python-argv": f"python3 {paths['echo_py']} {paths['payload']}",
        "dash-F": f"python3 {paths['consumer']} -F {paths['payload']}",
        "grep-f": f"grep -F -f {paths['pattern']} {paths['haystack']}",
    }
    out = {}
    for name, command in cases.items():
        rec = run_wrapped(command)
        rec["shape"] = name
        rec["lint"] = lint_command(command, PAYLOAD)
        if name == "grep-f":
            rec["round_trip"] = PAYLOAD in rec["stdout"]
        else:
            rec["round_trip"] = rec["stdout"] == PAYLOAD
        rec["file_route_holds"] = (
            rec["ok"] is True
            and rec["round_trip"] is True
            and rec["lint"]["ok"] is True
            and APOSTROPHE not in command
        )
        out[name] = rec
    return out


def measure_windows_shell_heading(repo: Path | None = None) -> dict:
    path = (repo or REPO) / "rules" / "common" / "windows-shell.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    heading = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {"## 10", "## 10.", "# 10"} or stripped.startswith("## 10 "):
            heading = True
            break
        if re.match(r"^##\s+10\b", stripped):
            heading = True
            break
    return {
        "path": "rules/common/windows-shell.md",
        "present": path.is_file(),
        "bytes": len(text.encode("utf-8")) if text else 0,
        "heading_10_present": heading,
        "note": (
            "Catalog cites rules/common/windows-shell.md#10. Live file documents "
            "8b (git archive CRLF) only; the apostrophe wrap rule is enforced by "
            "this unit's lint rather than by that missing heading."
            if not heading
            else "Section 10 heading present."
        ),
    }


def run_matrix(tmp: Path, repo: Path | None = None) -> dict:
    paths = prepare_workspace(tmp)
    inline = run_inline_controls(paths["haystack"])
    files = run_file_routes(paths)
    lint = lint_corpus()
    heading = measure_windows_shell_heading(repo)
    inline_ok = all(row["control_holds"] for row in inline.values())
    file_ok = all(row["file_route_holds"] for row in files.values())
    return {
        "payload": PAYLOAD,
        "payload_sha256": payload_sha256(),
        "select_transport": select_transport(PAYLOAD),
        "inline": inline,
        "file": files,
        "lint": lint,
        "windows_shell": heading,
        "inline_control_holds": inline_ok,
        "file_route_holds": file_ok,
        "lint_holds": lint["ok"],
        "ok": inline_ok and file_ok and lint["ok"] and select_transport(PAYLOAD) == "file",
    }


def compact_inline(inline: dict) -> dict:
    return {
        name: {
            "returncode": row["returncode"],
            "stdout_empty": row["stdout_empty"],
            "payload_in_stdout": row["payload_in_stdout"],
            "wrapped_script": row["wrapped_script"],
            "stderr_head": (row["stderr"] or "")[:240],
            "control_holds": row["control_holds"],
            "lint_hits": row["lint"]["hits"],
        }
        for name, row in inline.items()
    }


def compact_file(files: dict) -> dict:
    return {
        name: {
            "returncode": row["returncode"],
            "round_trip": row["round_trip"],
            "wrapped_script": row["wrapped_script"],
            "file_route_holds": row["file_route_holds"],
            "lint_ok": row["lint"]["ok"],
        }
        for name, row in files.items()
    }


def fn_anchor(name: str) -> str:
    text = (HERE / "transport.py").read_text(encoding="utf-8")
    needle = f"def {name}("
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"command-center/p2-wave/probes/TST-0069/transport.py:{i}"
    return "command-center/p2-wave/probes/TST-0069/transport.py:1"


def bash_version() -> str:
    proc = subprocess.run(
        ["bash", "--version"],
        capture_output=True,
        text=True,
        timeout=8,
    )
    first = ((proc.stdout or "").splitlines() or ["bash"])[0].strip()
    return first[:96] or "bash"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(prog="transport")
    parser.add_argument("--lint", action="store_true")
    args = parser.parse_args(argv)
    if args.lint:
        rec = lint_corpus()
        print(json.dumps({"ok": rec["ok"], "bad_all_fired": rec["bad_all_fired"], "good_all_silent": rec["good_all_silent"]}, sort_keys=True))
        if not rec["ok"]:
            print("FAILED:TST-0069-lint corpus")
            return 1
        print("SUCCESS:TST-0069-lint both-states over agent-authored commands")
        return 0
    with tempfile.TemporaryDirectory(prefix="tst0069-cli-") as tmp:
        matrix = run_matrix(Path(tmp))
    print(json.dumps({"ok": matrix["ok"], "payload_sha256": matrix["payload_sha256"]}, sort_keys=True))
    if not matrix["ok"]:
        print("FAILED:TST-0069-matrix")
        return 1
    print("SUCCESS:TST-0069-matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

