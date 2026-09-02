#!/usr/bin/env python3
"""Live transport x payload byte-equality matrix for TST-0060.

Named transports (catalog): Write tool, here-string, heredoc, -c inline.
Control transports: expanding heredoc and double-quoted -c (must be able to
show a red cell). Measurements are taken on this Linux bash box; pwsh is not
required and is recorded as absent when missing.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0060"

# Canonical adversarial script: nested quotes, backslashes, dollars, backticks.
# Trailing newline so quoted heredoc can be byte-exact when the delimiter is
# unique and quoted.
ADVERSARIAL = (
    "#!/usr/bin/env bash\n"
    "# TST-0060 adversarial payload: nested quotes, backslashes, dollars, backticks\n"
    "echo \"it's a \\\"quoted\\\" string\"\n"
    "echo $HOME and $(echo nest) and ${HOME:-missing}\n"
    "echo `uname -s` and \\`literal\\`\n"
    "echo C:\\\\Windows\\\\System32\\\\cmd.exe\n"
    "echo 'single with \"double\" inside'\n"
    "printf '%s\\n' \"dollar=$NotAVar\"\n"
    "cat <<'INNER'\n"
    "@'\n"
    "inner here-string lookalike\n"
    "'@\n"
    "INNER\n"
)

NAMED_TRANSPORTS = (
    "write_tool",
    "here_string",
    "heredoc",
    "c_inline",
)
CONTROL_TRANSPORTS = (
    "c_inline_double_quoted",
    "heredoc_expanding",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(
    argv: list[str],
    stdin: bytes | None = None,
    timeout: float = 12.0,
) -> tuple[int, bytes, bytes]:
    try:
        proc = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or b"", proc.stderr or b""
    except subprocess.TimeoutExpired:
        return 124, b"", b"TIMEOUT"
    except ValueError as exc:
        # argv/env cannot contain NUL; that is a real transport refusal.
        return 2, b"", f"ValueError: {exc}".encode()
    except OSError as exc:
        return 127, b"", f"{type(exc).__name__}: {exc}".encode()


def classify(intended: bytes, landed: bytes, rc: int) -> str:
    if landed == intended:
        return "equal"
    if rc not in (0, None) and landed == b"":
        return "transport_error"
    if landed == intended + b"\n":
        return "extra_trailing_newline"
    if not intended.endswith(b"\n") and landed == intended + b"\n":
        return "forced_trailing_newline"
    if intended and intended.endswith(b"\n") and landed == intended[:-1]:
        return "missing_trailing_newline"
    if b"\x00" in intended and b"\x00" not in landed:
        return "nul_truncation"
    if (b"$" in intended or b"`" in intended or b"$(" in intended) and intended not in landed:
        return "shell_expansion"
    return "other_mismatch"


def _land(
    dest: Path,
    payload: bytes,
    runner: Callable[[Path, bytes], tuple[int, bytes]],
) -> dict[str, Any]:
    if dest.exists():
        dest.unlink()
    rc, err = runner(dest, payload)
    landed = dest.read_bytes() if dest.is_file() else b""
    kind = classify(payload, landed, rc)
    return {
        "equal": landed == payload,
        "rc": rc,
        "intended_bytes": len(payload),
        "landed_bytes": len(landed),
        "intended_sha256": sha256_bytes(payload),
        "landed_sha256": sha256_bytes(landed) if dest.is_file() else None,
        "mismatch_kind": kind,
        "stderr_tail": err.decode("utf-8", errors="replace")[-400:],
    }


def _write_tool(dest: Path, payload: bytes) -> tuple[int, bytes]:
    dest.write_bytes(payload)
    return 0, b""


def _here_string(dest: Path, payload: bytes) -> tuple[int, bytes]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return 2, str(exc).encode()
    cmd = f"cat > {shlex.quote(str(dest))} <<< {shlex.quote(text)}"
    rc, _out, err = _run(["bash", "-c", cmd])
    return rc, err


def _heredoc_quoted(dest: Path, payload: bytes) -> tuple[int, bytes]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return 2, str(exc).encode()
    marker = "TST0060_" + sha256_bytes(payload)
    if marker in text:
        return 3, b"marker-collision"
    body = text if text.endswith("\n") else text + "\n"
    script = f"cat > {shlex.quote(str(dest))} <<'{marker}'\n{body}{marker}\n"
    rc, _out, err = _run(["bash"], stdin=script.encode())
    return rc, err


def _c_inline_quoted(dest: Path, payload: bytes) -> tuple[int, bytes]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return 2, str(exc).encode()
    cmd = f"printf '%s' {shlex.quote(text)} > {shlex.quote(str(dest))}"
    rc, _out, err = _run(["bash", "-c", cmd])
    return rc, err


def _c_inline_double_quoted(dest: Path, payload: bytes) -> tuple[int, bytes]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return 2, str(exc).encode()
    if "\x00" in text:
        return 2, b"nul-in-payload"
    # Naive inline: payload sits inside double quotes. $ and backticks expand.
    cmd = 'printf "%s" "' + text.replace("\\", "\\\\").replace('"', '\\"') + '" > '
    cmd += shlex.quote(str(dest))
    rc, _out, err = _run(["bash", "-c", cmd])
    return rc, err


def _heredoc_expanding(dest: Path, payload: bytes) -> tuple[int, bytes]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return 2, str(exc).encode()
    marker = "TST0060X_" + sha256_bytes(payload)[:16]
    if marker in text:
        return 3, b"marker-collision"
    body = text if text.endswith("\n") else text + "\n"
    script = f"cat > {shlex.quote(str(dest))} <<{marker}\n{body}{marker}\n"
    rc, _out, err = _run(["bash"], stdin=script.encode())
    return rc, err


RUNNERS: dict[str, Callable[[Path, bytes], tuple[int, bytes]]] = {
    "write_tool": _write_tool,
    "here_string": _here_string,
    "heredoc": _heredoc_quoted,
    "c_inline": _c_inline_quoted,
    "c_inline_double_quoted": _c_inline_double_quoted,
    "heredoc_expanding": _heredoc_expanding,
}


def corpus() -> list[dict[str, Any]]:
    """Deterministic payload corpus. Size is >=59 so here-string has a rate, not a sample."""
    rows: list[dict[str, Any]] = []

    def add(pid: str, data: bytes, tags: list[str]) -> None:
        rows.append({"id": pid, "bytes": data, "tags": tags, "sha256": sha256_bytes(data)})

    add("adversarial_script", ADVERSARIAL.encode("utf-8"), ["adversarial", "quotes", "dollar", "backtick", "backslash"])
    add("plain_nl", b"hello world\n", ["plain"])
    add("plain_no_nl", b"hello world", ["plain", "no-nl"])
    add("empty", b"", ["empty"])
    add("only_nl", b"\n", ["plain"])
    add("apos", b"it's a test\n", ["quotes"])
    add("nested_quotes", b"""echo "nested 'quotes' and \\"more\\""\n""", ["quotes"])
    add("dollar_home", b"echo $HOME and $(whoami) and ${PATH}\n", ["dollar"])
    add("backtick_date", b"echo `uname` and \\`more\\`\n", ["backtick"])
    add("mix_script", b"#!/bin/sh\necho \"it's $HOME\" && echo `uname` && echo \\\\back\\\\slash\n", ["quotes", "dollar", "backtick", "backslash"])
    add("ps_here_terminators", b"@'\npayload\n'@\n", ["here-string-terminator"])
    add("eof_line", b"foo\nEOF\nbar\n", ["heredoc-lookalike"])
    add("double_and_single", b'''printf '%s' "it's \\"x\\""\n''', ["quotes"])
    add("backslash_tail", b"ends-with-backslash\\\n", ["backslash"])
    add("tabs_and_spaces", b"a\tb  c\t\n", ["ws"])
    add("crlf_body", b"line1\r\nline2\r\n", ["eol"])
    add("nul_inside", b"aaa\x00bbb\n", ["nul", "binary"])
    add("latin1_bytes", bytes(range(0x80, 0xA0)) + b"\n", ["binary"])
    add("unicode", "echo café naïve — 日本語\n".encode("utf-8"), ["unicode"])
    add("long_dollar", (b"echo " + b"$x" * 40 + b"\n"), ["dollar"])
    add("cmd_subst", b"id=$(echo pwned); echo $id\n", ["dollar"])
    add("arith", b"echo $((1+2)) and $?\n", ["dollar"])
    add("history_bang", b"echo hi!\n", ["meta"])
    add("glob_stars", b"echo * ? [a-z]\n", ["meta"])
    add("and_or", b"false && echo x || echo y; echo done\n", ["meta"])
    add("pipe_semi", b"echo a | cat; echo b\n", ["meta"])
    add("hash_comment", b"# not a command\necho still-here\n", ["plain"])
    add("json_blob", b'{"k":"v with \'quotes\' and $HOME and `x`"}\n', ["quotes", "dollar", "backtick"])
    add("python_c_lookalike", b'python3 -c "print(\'it\\\'s $HOME\')"\n', ["quotes", "dollar"])
    add("grep_apos", b"grep -F \"it's\" file.txt\n", ["quotes"])
    add("multiline_no_final_nl", b"line1\nline2", ["no-nl"])
    add("many_newlines", b"\n" * 12, ["ws"])
    add("spaces_only", b"     \n", ["ws"])
    add("quoted_dollar_safe", b"echo '$HOME' and \"\\$HOME\"\n", ["dollar", "quotes"])
    add("here_string_bash", b"cat <<< 'inner'\n", ["here-string-terminator"])
    add("double_at", b"@@double@@\n", ["meta"])
    add("backslash_n_literal", b"echo \\n \\t \\\\\n", ["backslash"])
    add("nested_cmdsubst", b"echo $(echo $(echo inner))\n", ["dollar"])
    add("param_offset", b"echo ${HOME:0:1} ${#HOME}\n", ["dollar"])
    add("ansi_c", b"echo $'a\\nb'\n", ["dollar", "quotes"])

    # Pad to 59 with numbered adversarial variants (unique comment lines).
    while len(rows) < 59:
        n = len(rows)
        variant = ADVERSARIAL + f"# variant {n:02d} keep-quotes \"x\" '$y' `z` $HOME\n"
        add(f"adversarial_v{n:02d}", variant.encode("utf-8"), ["adversarial", "pad"])

    if len(rows) != 59:
        raise RuntimeError(f"corpus size {len(rows)} != 59")
    return rows


def host_info() -> dict[str, Any]:
    bash = shutil.which("bash")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    bash_ver = ""
    if bash:
        _rc, out, err = _run([bash, "--version"])
        bash_ver = ((out or err).decode("utf-8", errors="replace").splitlines() or [""])[0]
    uname = os.uname()
    return {
        "system": uname.sysname,
        "release": uname.release,
        "machine": uname.machine,
        "python": sys.version.split()[0],
        "bash_path": bash,
        "bash_version_line": bash_ver,
        "pwsh_path": pwsh,
        "pwsh_present": bool(pwsh),
        "cwd_repo": str(REPO),
    }


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cells)
    n_equal = sum(1 for c in cells if c["equal"])
    n_unequal = n - n_equal
    kinds: dict[str, int] = {}
    for c in cells:
        kinds[c["mismatch_kind"]] = kinds.get(c["mismatch_kind"], 0) + 1
    rate = (n_unequal / n) if n else 1.0
    return {
        "n": n,
        "n_equal": n_equal,
        "n_unequal": n_unequal,
        "failure_rate": round(rate, 6),
        "failure_rate_pct": round(rate * 100.0, 3),
        "mismatch_kinds": kinds,
    }


def run_matrix(
    transports: tuple[str, ...] | None = None,
    payload_ids: set[str] | None = None,
    workdir: Path | None = None,
) -> dict[str, Any]:
    transports = transports or (NAMED_TRANSPORTS + CONTROL_TRANSPORTS)
    payloads = corpus()
    if payload_ids is not None:
        payloads = [p for p in payloads if p["id"] in payload_ids]
        missing = payload_ids - {p["id"] for p in payloads}
        if missing:
            raise KeyError(f"unknown payload ids: {sorted(missing)}")

    own_tmp = workdir is None
    root = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="tst0060-"))
    cells: list[dict[str, Any]] = []
    try:
        for tr in transports:
            runner = RUNNERS[tr]
            tdir = root / tr
            tdir.mkdir(parents=True, exist_ok=True)
            for pay in payloads:
                dest = tdir / f"{pay['id']}.landed"
                result = _land(dest, pay["bytes"], runner)
                cells.append(
                    {
                        "transport": tr,
                        "payload_id": pay["id"],
                        "payload_tags": pay["tags"],
                        **result,
                    }
                )
    finally:
        if own_tmp:
            # Leave nothing behind; equality was recorded from bytes already read.
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                for name in filenames:
                    try:
                        Path(dirpath, name).unlink()
                    except OSError:
                        pass
                for name in dirnames:
                    try:
                        Path(dirpath, name).rmdir()
                    except OSError:
                        pass
            try:
                root.rmdir()
            except OSError:
                pass

    by_transport: dict[str, list[dict[str, Any]]] = {t: [] for t in transports}
    for cell in cells:
        by_transport[cell["transport"]].append(cell)

    red = [c for c in cells if not c["equal"]]
    green = [c for c in cells if c["equal"]]
    adv = [c for c in cells if c["payload_id"] == "adversarial_script"]
    return {
        "unit_id": UNIT,
        "host": host_info(),
        "payload_count": len(payloads),
        "transport_count": len(transports),
        "cell_count": len(cells),
        "by_transport": {t: summarize(by_transport[t]) for t in transports},
        "adversarial_cells": [
            {
                "transport": c["transport"],
                "equal": c["equal"],
                "mismatch_kind": c["mismatch_kind"],
                "intended_bytes": c["intended_bytes"],
                "landed_bytes": c["landed_bytes"],
                "intended_sha256": c["intended_sha256"],
                "landed_sha256": c["landed_sha256"],
                "rc": c["rc"],
            }
            for c in adv
        ],
        "red_sample": [
            {
                "transport": c["transport"],
                "payload_id": c["payload_id"],
                "mismatch_kind": c["mismatch_kind"],
                "intended_bytes": c["intended_bytes"],
                "landed_bytes": c["landed_bytes"],
            }
            for c in red[:16]
        ],
        "green_sample": [
            {
                "transport": c["transport"],
                "payload_id": c["payload_id"],
                "mismatch_kind": c["mismatch_kind"],
            }
            for c in green[:8]
        ],
        "red_count": len(red),
        "green_count": len(green),
        "cells": cells,
    }


def named_roundtrip(report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the four named transports against the adversarial payload only."""
    report = report or run_matrix(
        transports=NAMED_TRANSPORTS,
        payload_ids={"adversarial_script"},
    )
    by = {c["transport"]: c for c in report["adversarial_cells"]}
    missing = [t for t in NAMED_TRANSPORTS if t not in by]
    write_ok = bool(by.get("write_tool", {}).get("equal"))
    heredoc_ok = bool(by.get("heredoc", {}).get("equal"))
    c_ok = bool(by.get("c_inline", {}).get("equal"))
    here = by.get("here_string") or {}
    return {
        "transports_present": missing == [],
        "missing": missing,
        "write_tool_equal": write_ok,
        "heredoc_equal": heredoc_ok,
        "c_inline_equal": c_ok,
        "here_string_equal": bool(here.get("equal")),
        "here_string_kind": here.get("mismatch_kind"),
        "cells": report["adversarial_cells"],
        "pass": missing == [] and write_ok and heredoc_ok and c_ok and here != {},
    }


def red_cell_control(report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Both-states: write_tool silent on dollar payload; expanding transports fire."""
    report = report or run_matrix(
        transports=("write_tool", "c_inline_double_quoted", "heredoc_expanding", "here_string"),
        payload_ids={"dollar_home", "adversarial_script", "plain_nl"},
    )
    def cell(tr: str, pid: str) -> dict[str, Any] | None:
        for c in report["cells"]:
            if c["transport"] == tr and c["payload_id"] == pid:
                return c
        return None

    good = cell("write_tool", "dollar_home")
    bad_c = cell("c_inline_double_quoted", "dollar_home")
    bad_hd = cell("heredoc_expanding", "dollar_home")
    here = cell("here_string", "plain_nl")
    silent_good = bool(good and good["equal"])
    fired_c = bool(bad_c and not bad_c["equal"])
    fired_hd = bool(bad_hd and not bad_hd["equal"])
    fired_here = bool(here and not here["equal"])
    return {
        "silent_on_write_tool": silent_good,
        "fired_on_double_quoted_c": fired_c,
        "fired_on_expanding_heredoc": fired_hd,
        "fired_on_here_string_extra_nl": fired_here,
        "write_kind": (good or {}).get("mismatch_kind"),
        "c_kind": (bad_c or {}).get("mismatch_kind"),
        "heredoc_kind": (bad_hd or {}).get("mismatch_kind"),
        "here_kind": (here or {}).get("mismatch_kind"),
        "pass": silent_good and fired_c and fired_hd and fired_here,
        "red_count": report["red_count"],
    }


def public_report(full: dict[str, Any]) -> dict[str, Any]:
    """Receipt-safe subset (no raw payload bytes, no full cell dump)."""
    return {
        "unit_id": full["unit_id"],
        "host": full["host"],
        "payload_count": full["payload_count"],
        "transport_count": full["transport_count"],
        "cell_count": full["cell_count"],
        "by_transport": full["by_transport"],
        "adversarial_cells": full["adversarial_cells"],
        "red_sample": full["red_sample"],
        "green_sample": full["green_sample"],
        "red_count": full["red_count"],
        "green_count": full["green_count"],
        "named_transports": list(NAMED_TRANSPORTS),
        "control_transports": list(CONTROL_TRANSPORTS),
        "historical_note": (
            "Catalog cited here-string 8/59 (13.6%) vs Write tool 0/40 on a prior "
            "Windows/PowerShell measurement. This receipt is the live Linux bash "
            "matrix on this box, not a copy of those rates."
        ),
    }
