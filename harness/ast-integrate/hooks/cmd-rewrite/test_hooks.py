#!/usr/bin/env python
"""Self-tests for inject-nopager.py and compress-output.py.

Run:   python test_hooks.py
All tests print PASS / FAIL and a summary at the end.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
INJECT = HERE / "inject-nopager.py"
COMPRESS = HERE / "compress-output.py"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_results: list[tuple[str, bool, str]] = []


def _run(script: Path, stdin_data: dict) -> tuple[int, str]:
    """Run *script* with *stdin_data* as JSON on stdin.  Returns (returncode, stdout)."""
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip()


def _check(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    status = PASS if passed else FAIL
    print(
        f"  [{status}] {name}"
        + (f"\n         {detail}" if detail and not passed else "")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hook A tests — inject-nopager.py
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Hook A: inject-nopager.py ===\n")


def test_a_basic_rewrite() -> None:
    """git log → git --no-pager log"""
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git log --oneline -5"}}
    )
    _check("A01 basic rewrite: git log", rc == 0, f"rc={rc}")
    data = json.loads(out)
    cmd = data["hookSpecificOutput"]["updatedInput"]["command"]
    _check("A01 command contains --no-pager", "--no-pager" in cmd, repr(cmd))
    _check(
        "A01 command starts with git --no-pager log",
        cmd.strip().startswith("git --no-pager log"),
        repr(cmd),
    )
    _check(
        "A01 permissionDecision is allow",
        data["hookSpecificOutput"]["permissionDecision"] == "allow",
    )
    _check(
        "A01 hookEventName is PreToolUse",
        data["hookSpecificOutput"]["hookEventName"] == "PreToolUse",
    )


def test_a_diff() -> None:
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git diff HEAD~1"}}
    )
    _check("A02 git diff rewrite", rc == 0 and out)
    cmd = json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
    _check("A02 result", cmd == "git --no-pager diff HEAD~1", repr(cmd))


def test_a_already_has_nopager() -> None:
    """Already has --no-pager → silent (no output)."""
    rc, out = _run(
        INJECT,
        {"tool_name": "Bash", "tool_input": {"command": "git --no-pager diff HEAD"}},
    )
    _check(
        "A03 already --no-pager: silent",
        rc == 0 and out == "",
        f"rc={rc} out={repr(out)}",
    )


def test_a_non_git() -> None:
    """Non-git command → silent."""
    rc, out = _run(INJECT, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    _check("A04 non-git: silent", rc == 0 and out == "", f"rc={rc} out={repr(out)}")


def test_a_non_pager_subcommand() -> None:
    """git commit → silent (not pager-prone)."""
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'test'"}}
    )
    _check("A05 git commit: silent", rc == 0 and out == "", f"rc={rc} out={repr(out)}")


def test_a_compound_mixed() -> None:
    """Compound: git log && echo done — only git segment rewritten."""
    rc, out = _run(
        INJECT,
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git log --oneline && echo done"},
        },
    )
    _check("A06 compound rewrite", rc == 0 and out)
    cmd = json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
    _check("A06 git log rewritten in compound", "git --no-pager log" in cmd, repr(cmd))
    _check("A06 echo preserved in compound", "echo done" in cmd, repr(cmd))


def test_a_compound_semicolon() -> None:
    """Semicolon compound."""
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git diff; echo ok"}}
    )
    _check("A07 semicolon compound", rc == 0 and out)
    cmd = json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
    _check("A07 git diff rewritten", "git --no-pager diff" in cmd, repr(cmd))


def test_a_malformed_json() -> None:
    """Malformed stdin → exit 0, no output."""
    result = subprocess.run(
        [sys.executable, str(INJECT)],
        input="NOT JSON {{{",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _check(
        "A08 malformed JSON: exit 0 silent",
        result.returncode == 0 and result.stdout.strip() == "",
        f"rc={result.returncode} out={repr(result.stdout)}",
    )


def test_a_non_bash_tool() -> None:
    """Non-Bash tool → silent."""
    rc, out = _run(INJECT, {"tool_name": "Edit", "tool_input": {"command": "git log"}})
    _check(
        "A09 non-Bash tool: silent", rc == 0 and out == "", f"rc={rc} out={repr(out)}"
    )


def test_a_empty_stdin() -> None:
    """Empty stdin → exit 0 silent."""
    result = subprocess.run(
        [sys.executable, str(INJECT)],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _check(
        "A10 empty stdin: exit 0 silent",
        result.returncode == 0 and result.stdout.strip() == "",
        f"rc={result.returncode}",
    )


def test_a_git_stash_list() -> None:
    """git stash list → rewritten (stash is pager-prone)."""
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git stash list"}}
    )
    _check("A11 git stash list: rewritten", rc == 0 and out)
    cmd = json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
    _check("A11 --no-pager injected for stash", "--no-pager" in cmd, repr(cmd))


def test_a_subshell_passthrough() -> None:
    """Command with $() subshell → silent (too risky to parse)."""
    rc, out = _run(
        INJECT, {"tool_name": "Bash", "tool_input": {"command": "git log $(cat file)"}}
    )
    _check(
        "A12 subshell: silent (fail-open)",
        rc == 0 and out == "",
        f"rc={rc} out={repr(out)}",
    )


for fn in [
    test_a_basic_rewrite,
    test_a_diff,
    test_a_already_has_nopager,
    test_a_non_git,
    test_a_non_pager_subcommand,
    test_a_compound_mixed,
    test_a_compound_semicolon,
    test_a_malformed_json,
    test_a_non_bash_tool,
    test_a_empty_stdin,
    test_a_git_stash_list,
    test_a_subshell_passthrough,
]:
    try:
        fn()
    except Exception as exc:
        _check(fn.__name__, False, f"EXCEPTION: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Hook B tests — compress-output.py
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Hook B: compress-output.py ===\n")


def _make_git_status(n_untracked: int = 300, n_modified: int = 5) -> str:
    """Produce realistic fake `git status` output."""
    lines = [
        "On branch main",
        "Your branch is up to date with 'origin/main'.",
        "",
        "Changes not staged for commit:",
        '  (use "git add <file>..." to update what will be committed)',
        "",
    ]
    for i in range(n_modified):
        lines.append(f"\tmodified:   src/module_{i:03d}.py")
    lines += [
        "",
        "Untracked files:",
        '  (use "git add <file>..." to include in what will be committed)',
        "",
    ]
    for i in range(n_untracked):
        lines.append(f"\tbuild/artifact_{i:04d}.o")
    lines.append("")
    lines.append('no changes added to commit (use "git add" and/or "git commit -a")')
    return "\n".join(lines)


def test_b_git_status_large() -> None:
    """Large git status → summarised."""
    big_output = _make_git_status(300, 5)
    assert len(big_output) > 4000, "Test setup: output must exceed threshold"
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "tool_response": {"type": "text", "text": big_output},
    }
    rc, out = _run(COMPRESS, payload)
    _check("B01 large git status: exit 0", rc == 0, f"rc={rc}")
    _check(
        "B01 output not empty", out != "", "hook was silent but should have compressed"
    )
    data = json.loads(out)
    compressed = data["hookSpecificOutput"]["updatedToolOutput"]
    _check(
        "B01 hookEventName is PostToolUse",
        data["hookSpecificOutput"]["hookEventName"] == "PostToolUse",
    )
    _check(
        "B01 branch line preserved",
        "On branch main" in compressed,
        repr(compressed[:200]),
    )
    _check(
        "B01 compressed shorter than original",
        len(compressed) < len(big_output),
        f"{len(compressed)} vs {len(big_output)}",
    )
    _check(
        "B01 untracked count mentioned",
        "untracked" in compressed.lower(),
        repr(compressed[:400]),
    )
    print(f"         compressed length: {len(compressed)} (was {len(big_output)})")


def test_b_short_output_passthrough() -> None:
    """Short output → silent (no compression)."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "tool_response": {"type": "text", "text": "On branch main\nnothing to commit"},
    }
    rc, out = _run(COMPRESS, payload)
    _check(
        "B02 short output: silent", rc == 0 and out == "", f"rc={rc} out={repr(out)}"
    )


def test_b_ansi_strip_large() -> None:
    """Large output with ANSI codes → codes stripped."""
    ansi_line = (
        "\x1b[32mPASS\x1b[0m test_something ... \x1b[31mFAIL\x1b[0m other_thing\n"
    )
    big_ansi = ansi_line * 300  # well above threshold
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": {"type": "text", "text": big_ansi},
    }
    rc, out = _run(COMPRESS, payload)
    _check("B03 ANSI strip large: exit 0", rc == 0, f"rc={rc}")
    _check(
        "B03 output not empty", out != "", "hook silent but should have stripped ANSI"
    )
    data = json.loads(out)
    compressed = data["hookSpecificOutput"]["updatedToolOutput"]
    _check("B03 no ESC in result", "\x1b" not in compressed, "ANSI codes still present")
    _check("B03 text content preserved", "PASS" in compressed and "FAIL" in compressed)


def test_b_malformed_json() -> None:
    """Malformed stdin → exit 0 silent."""
    result = subprocess.run(
        [sys.executable, str(COMPRESS)],
        input="NOTJSON",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _check(
        "B04 malformed JSON: exit 0 silent",
        result.returncode == 0 and result.stdout.strip() == "",
        f"rc={result.returncode} out={repr(result.stdout)}",
    )


def test_b_non_bash_tool() -> None:
    """Non-Bash tool → silent."""
    big = "x" * 5000
    payload = {
        "tool_name": "Edit",
        "tool_input": {"command": "git status"},
        "tool_response": {"type": "text", "text": big},
    }
    rc, out = _run(COMPRESS, payload)
    _check(
        "B05 non-Bash tool: silent", rc == 0 and out == "", f"rc={rc} out={repr(out)}"
    )


def test_b_tool_response_string() -> None:
    """tool_response as raw string (not dict) → handled."""
    big_output = _make_git_status(300)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "tool_response": big_output,  # raw string, not {"type":"text","text":...}
    }
    rc, out = _run(COMPRESS, payload)
    _check("B06 raw-string tool_response: exit 0", rc == 0, f"rc={rc}")
    _check(
        "B06 output not empty (was compressed)",
        out != "",
        "hook silent for raw-string response",
    )


def test_b_non_noisy_command_large() -> None:
    """Large non-noisy, non-ANSI output → silent (passthrough)."""
    big_plain = "some log line\n" * 400  # large but no ANSI, not git status
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "cat bigfile.txt"},
        "tool_response": {"type": "text", "text": big_plain},
    }
    rc, out = _run(COMPRESS, payload)
    _check(
        "B07 large plain non-noisy: silent",
        rc == 0 and out == "",
        f"rc={rc} out={repr(out[:100])}",
    )


def _temp_dir() -> str:
    """Same temp dir the hook resolves for dropped screenshots."""
    return os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()


def test_b_browser_large_image_dropped() -> None:
    """Browser MCP image ≥ 40KB decoded → placeholder + a real file on disk."""
    raw = b"A" * 50000  # 50 KB decoded, well over IMG_MIN_BYTES (40 KB)
    big_b64 = base64.b64encode(raw).decode("ascii")
    payload = {
        "tool_name": "mcp__playwright__browser_take_screenshot",
        "tool_input": {},
        "tool_response": {
            "content": [
                {"type": "text", "text": "clicked Submit"},
                {"type": "image", "data": big_b64, "mimeType": "image/png"},
            ]
        },
    }
    rc, out = _run(COMPRESS, payload)
    _check("B08 browser large image: exit 0", rc == 0, f"rc={rc}")
    _check("B08 output not empty (image dropped)", out != "", "hook was silent")
    data = json.loads(out)
    _check(
        "B08 hookEventName is PostToolUse",
        data["hookSpecificOutput"]["hookEventName"] == "PostToolUse",
    )
    compressed = data["hookSpecificOutput"]["updatedToolOutput"]
    _check(
        "B08 placeholder present",
        "[screenshot dropped:" in compressed,
        repr(compressed[:200]),
    )
    _check(
        "B08 raw base64 removed from context",
        big_b64 not in compressed,
        "the 50KB base64 blob is still in the output",
    )
    # The file the placeholder points at must really exist, with the exact bytes.
    digest = hashlib.sha1(raw, usedforsecurity=False).hexdigest()[:12]
    saved = os.path.join(_temp_dir(), f"screenshot_{digest}.png")
    _check(
        "B08 screenshot file written to disk", os.path.isfile(saved), f"missing {saved}"
    )
    if os.path.isfile(saved):
        _check(
            "B08 saved bytes match decoded image",
            os.path.getsize(saved) == len(raw),
            f"size {os.path.getsize(saved)} != {len(raw)}",
        )


def test_b_browser_data_uri_image_dropped() -> None:
    """A data:image/…;base64 URI over threshold is dropped too (not just MCP)."""
    raw = b"B" * 45000
    big_b64 = base64.b64encode(raw).decode("ascii")
    payload = {
        "tool_name": "mcp__chrome-devtools__take_screenshot",
        "tool_input": {},
        "tool_response": f'<img src="data:image/png;base64,{big_b64}">',
    }
    rc, out = _run(COMPRESS, payload)
    _check("B09 data-URI image: exit 0", rc == 0, f"rc={rc}")
    _check("B09 output not empty (data-URI dropped)", out != "", "hook was silent")
    if out:
        compressed = json.loads(out)["hookSpecificOutput"]["updatedToolOutput"]
        _check(
            "B09 placeholder present",
            "[screenshot dropped:" in compressed,
            repr(compressed[:200]),
        )
        _check("B09 base64 removed", big_b64 not in compressed, "base64 still present")


def test_b_browser_small_image_passthrough() -> None:
    """Browser image < 40KB decoded → passes through untouched (silent)."""
    small_b64 = base64.b64encode(b"A" * 1000).decode("ascii")  # 1 KB « 40 KB
    payload = {
        "tool_name": "mcp__playwright__browser_take_screenshot",
        "tool_input": {},
        "tool_response": {
            "content": [{"type": "image", "data": small_b64, "mimeType": "image/png"}]
        },
    }
    rc, out = _run(COMPRESS, payload)
    _check(
        "B10 small browser image: silent passthrough",
        rc == 0 and out == "",
        f"rc={rc} out={repr(out[:120])}",
    )


def test_b_browser_text_only_passthrough() -> None:
    """Browser a11y snapshot with NO image → passes through untouched (silent)."""
    a11y = 'button "Submit"\nlink "Home"\ntextbox "Search"\n' * 60  # text-only
    payload = {
        "tool_name": "mcp__claude-in-chrome__read_page",
        "tool_input": {},
        "tool_response": {"content": [{"type": "text", "text": a11y}]},
    }
    rc, out = _run(COMPRESS, payload)
    _check(
        "B11 a11y text-only: silent passthrough",
        rc == 0 and out == "",
        f"rc={rc} out={repr(out[:120])}",
    )


def test_b_bash_still_compresses_after_browser_rail() -> None:
    """Regression: the Bash rail still summarises git status (browser rail added)."""
    big_output = _make_git_status(300, 5)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "tool_response": {"type": "text", "text": big_output},
    }
    rc, out = _run(COMPRESS, payload)
    _check("B12 bash git-status still compresses: exit 0", rc == 0, f"rc={rc}")
    _check("B12 output not empty", out != "", "bash rail regressed to silent")
    if out:
        compressed = json.loads(out)["hookSpecificOutput"]["updatedToolOutput"]
        _check(
            "B12 compressed shorter than original",
            len(compressed) < len(big_output),
            f"{len(compressed)} vs {len(big_output)}",
        )


for fn in [
    test_b_git_status_large,
    test_b_short_output_passthrough,
    test_b_ansi_strip_large,
    test_b_malformed_json,
    test_b_non_bash_tool,
    test_b_tool_response_string,
    test_b_non_noisy_command_large,
    test_b_browser_large_image_dropped,
    test_b_browser_data_uri_image_dropped,
    test_b_browser_small_image_passthrough,
    test_b_browser_text_only_passthrough,
    test_b_bash_still_compresses_after_browser_rail,
]:
    try:
        fn()
    except Exception as exc:
        _check(fn.__name__, False, f"EXCEPTION: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in _results if ok)
total = len(_results)
print(f"Results: {passed}/{total} passed")
if passed < total:
    print("\nFailed tests:")
    for name, ok, detail in _results:
        if not ok:
            print(f"  FAIL  {name}  {detail}")
    sys.exit(1)
else:
    print("All tests passed.")
    sys.exit(0)
