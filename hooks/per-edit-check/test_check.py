#!/usr/bin/env python3
"""pytest tests for per-edit-check/check.py.

Run: pytest test_check.py -v

Required scenarios (spec):
  clean-file            → silent exit 0
  file-with-lint-error  → inject (exit 0 + additionalContext JSON)
  syntax-broken         → exit 2 (block) + decision:block JSON
  unknown-extension     → silent exit 0
  missing-checker-tool  → silent exit 0
  malformed stdin       → exit 0 (fail-open)
  opt-out               → exit 0

Subprocess is mocked throughout; real temp files are used so os.path.isfile
and os.path.getsize calls behave naturally.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

HERE = Path(__file__).resolve().parent


# ── module loader ────────────────────────────────────────────────────────────


def load_check():
    """Return a freshly exec'd copy of check.py (bypasses import cache)."""
    spec = importlib.util.spec_from_file_location("check_mod", HERE / "check.py")
    assert spec is not None, "check.py not found next to test_check.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ── helpers ──────────────────────────────────────────────────────────────────


def run_hook(
    mod,
    payload: dict,
    *,
    env_overrides: dict | None = None,
) -> tuple[int, str, str]:
    """Invoke mod.main() with fake stdin + optional env overrides.

    Returns (exit_code, captured_stdout_text, captured_stderr_text).
    Never raises: catches SystemExit and bare Exception.
    """
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO(json.dumps(payload))
    cap_out = io.StringIO()
    cap_err = io.StringIO()
    sys.stdout = cap_out
    sys.stderr = cap_err
    rc = 0
    try:
        with mock.patch.dict(os.environ, env_overrides or {}, clear=False):
            rc = mod.main()
    except SystemExit as exc:
        rc = int(exc.code) if exc.code is not None else 0
    except Exception:
        rc = 0
    finally:
        sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
    return rc, cap_out.getvalue(), cap_err.getvalue()


def make_event(fp: str, tool_name: str = "Edit") -> dict:
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": fp},
        "session_id": "test-sess",
    }


# ── mock subprocess return-value factories ───────────────────────────────────


def _proc(returncode: int, stdout: str = "", stderr: str = ""):
    return mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)


def _ruff_clean():
    return _proc(0)


def _ruff_lint(filename: str):
    return _proc(
        1,
        stdout=(f"{filename}:1:1: F401 `os` imported but unused\nFound 1 error.\n"),
    )


def _pycompile_syntax_err():
    return _proc(
        1,
        stderr=(
            "  File 'broken.py', line 1\n"
            "    def foo(\n"
            "          ^\n"
            "SyntaxError: unexpected EOF while parsing\n"
        ),
    )


def _node_syntax_err():
    return _proc(
        1,
        stderr=(
            "app.js:1\nconst x = ;\n          ^\n\nSyntaxError: Unexpected token ';'\n"
        ),
    )


# ── 1. clean file → silent exit 0 ───────────────────────────────────────────


def test_clean_python_ruff_silent(tmp_path: Path):
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_clean()),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


def test_clean_json_silent(tmp_path: Path):
    f = tmp_path / "config.json"
    f.write_text('{"key": "value", "num": 42}\n')
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


def test_clean_python_no_ruff_pycompile_silent(tmp_path: Path):
    """No ruff → py_compile fallback. py_compile clean → silent."""
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value=None),
        mock.patch("subprocess.run", return_value=_proc(0)),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


# ── 2. file with lint error → inject ────────────────────────────────────────


def test_python_lint_error_injects(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("import os\nx = 1\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_lint("bad.py")),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0, "lint errors must inject (exit 0), not block"
    parsed = json.loads(out.strip())
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert "issue" in ctx
    assert "bad.py" in ctx
    assert "F401" in ctx


def test_python_lint_error_write_tool_injects(tmp_path: Path):
    """Write tool is also matched by the hook."""
    f = tmp_path / "bad.py"
    f.write_text("import os\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_lint("bad.py")),
    ):
        rc, out, err = run_hook(mod, make_event(str(f), tool_name="Write"))
    assert rc == 0
    parsed = json.loads(out.strip())
    assert "additionalContext" in str(parsed)


def test_python_lint_error_multiedit_tool_injects(tmp_path: Path):
    """MultiEdit is also matched by the hook."""
    f = tmp_path / "bad.py"
    f.write_text("import os\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_lint("bad.py")),
    ):
        rc, out, err = run_hook(mod, make_event(str(f), tool_name="MultiEdit"))
    assert rc == 0
    parsed = json.loads(out.strip())
    assert "additionalContext" in str(parsed)


def test_inject_shows_filename_and_count(tmp_path: Path):
    """additionalContext must mention filename and issue count."""
    f = tmp_path / "mymodule.py"
    f.write_text("import os\nimport sys\n")
    mod = load_check()
    two_errors = _proc(
        1,
        stdout=(
            "mymodule.py:1:1: F401 `os` imported but unused\n"
            "mymodule.py:2:1: F401 `sys` imported but unused\n"
            "Found 2 errors.\n"
        ),
    )
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=two_errors),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    parsed = json.loads(out.strip())
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    assert "mymodule.py" in ctx
    assert "2" in ctx  # count present


# ── 3. syntax-broken → exit 2 (block) ───────────────────────────────────────


def test_python_syntax_error_blocks(tmp_path: Path):
    f = tmp_path / "broken.py"
    f.write_text("def foo(\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value=None),  # no ruff → py_compile
        mock.patch("subprocess.run", return_value=_pycompile_syntax_err()),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 2, "syntax error must block (exit 2)"
    assert out.strip() == "", "stdout must be empty on exit 2 (CC reads stderr)"
    assert err.strip(), "block reason must appear on stderr"
    assert "broken.py" in err


def test_json_syntax_error_blocks(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text('{"key": invalid}\n')
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 2, "JSON syntax error must block"
    assert out.strip() == "", "stdout must be empty on exit 2 (CC reads stderr)"
    assert err.strip(), "block reason must appear on stderr"
    assert "bad.json" in err


def test_js_syntax_error_blocks(tmp_path: Path):
    f = tmp_path / "app.js"
    f.write_text("const x = ;\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/node"),
        mock.patch("subprocess.run", return_value=_node_syntax_err()),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 2, "JS syntax error must block"
    assert out.strip() == "", "stdout must be empty on exit 2 (CC reads stderr)"
    assert err.strip(), "block reason must appear on stderr"


# ── 4. unknown extension → silent ───────────────────────────────────────────


@pytest.mark.parametrize("ext", [".xyz", ".rs", ".ts", ".tsx", ".go", ".rb", ".swift"])
def test_unknown_or_skipped_extension_silent(tmp_path: Path, ext: str):
    f = tmp_path / f"file{ext}"
    f.write_text("whatever content\n")
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


# ── 5. missing checker tool → silent exit 0 ─────────────────────────────────


def test_js_no_node_silent(tmp_path: Path):
    """If node is absent, JS files are silently skipped."""
    f = tmp_path / "app.js"
    f.write_text("const x = ;\n")  # would be syntax error if node ran
    mod = load_check()
    with mock.patch("shutil.which", return_value=None):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


def test_yaml_no_pyyaml_silent(tmp_path: Path):
    """If pyyaml is not installed, YAML files are silently skipped."""
    f = tmp_path / "config.yaml"
    f.write_text("key: : bad\n")  # invalid YAML
    mod = load_check()
    # Simulate pyyaml absent by making import raise ImportError
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return original_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=fake_import):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


# ── 6. malformed stdin → exit 0 (fail-open) ─────────────────────────────────


@pytest.mark.parametrize(
    "bad_input",
    [
        "{not valid json",
        "",
        "null",
        "42",
        "[]",
        "true",
    ],
)
def test_malformed_stdin_fail_open(bad_input: str):
    mod = load_check()
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(bad_input)
    sys.stdout = io.StringIO()
    rc = 0
    try:
        rc = mod.main()
    except SystemExit as exc:
        rc = int(exc.code) if exc.code is not None else 0
    except Exception:
        rc = 0
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    assert rc == 0


# ── 7. opt-out → exit 0 ─────────────────────────────────────────────────────


def test_env_opt_out_lowercase(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("import os\n")
    mod = load_check()
    rc, out, err = run_hook(
        mod, make_event(str(f)), env_overrides={"PER_EDIT_CHECK": "off"}
    )
    assert rc == 0
    assert out.strip() == ""


def test_env_opt_out_uppercase(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("import os\n")
    mod = load_check()
    rc, out, err = run_hook(
        mod, make_event(str(f)), env_overrides={"PER_EDIT_CHECK": "OFF"}
    )
    assert rc == 0
    assert out.strip() == ""


def test_disabled_sentinel_suppresses_check(tmp_path: Path):
    """.disabled file in HOOKDIR suppresses all checks."""
    f = tmp_path / "bad.py"
    f.write_text("import os\n")
    (tmp_path / ".disabled").touch()
    mod = load_check()
    mod.HOOKDIR = str(tmp_path)  # redirect the .disabled lookup
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_lint("bad.py")),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 0
    assert out.strip() == ""


# ── 8. non-Edit/Write/MultiEdit tools → silent ──────────────────────────────


@pytest.mark.parametrize("tool_name", ["Read", "Bash", "Grep", "Glob", "WebFetch"])
def test_non_write_tool_silent(tmp_path: Path, tool_name: str):
    f = tmp_path / "file.py"
    f.write_text("import os\n")
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(f), tool_name=tool_name))
    assert rc == 0
    assert out.strip() == ""


# ── 9. huge file → checker not invoked ──────────────────────────────────────


def test_huge_file_skipped(tmp_path: Path):
    """Files over MAX_FILE_BYTES (~512 KB) are skipped without running the checker."""
    f = tmp_path / "big.py"
    f.write_bytes(b"x = 1\n" * 100_000)  # ~600 KB
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run") as mock_sub,
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    mock_sub.assert_not_called()
    assert rc == 0
    assert out.strip() == ""


# ── 10. missing / nonexistent file_path → silent ────────────────────────────


def test_missing_file_path_key_silent():
    mod = load_check()
    rc, out, err = run_hook(
        mod, {"tool_name": "Edit", "tool_input": {}, "session_id": "s"}
    )
    assert rc == 0
    assert out.strip() == ""


def test_nonexistent_file_path_silent(tmp_path: Path):
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(tmp_path / "ghost.py")))
    assert rc == 0
    assert out.strip() == ""


# ── 11. M2a: exit-2 writes reason to stderr, stdout stays clean ─────────────


def test_exit_2_writes_reason_to_stderr_not_stdout(tmp_path: Path):
    """On exit 2 the block reason must go to stderr; stdout must be clean.

    Claude Code reads stderr when the hook exits with code 2.  Any JSON on
    stdout is silently ignored at that exit code — so mixing stdout-JSON with
    exit-2 means the actionable reason (which file / what error) is lost.
    """
    f = tmp_path / "bad.json"
    f.write_text('{"key": invalid}\n')
    mod = load_check()
    rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 2, "bad JSON must block (exit 2)"
    assert out.strip() == "", "stdout must be empty on exit 2"
    assert err.strip(), "human-readable reason must be on stderr"
    assert "bad.json" in err


# ── 12. M2b: ruff E999 → hard block (exit 2), not soft inject ───────────────


def _ruff_e999(filename: str):
    """Simulate ruff reporting an E999 syntax/parse error."""
    return _proc(
        1,
        stdout=(
            f"{filename}:1:9: E999 SyntaxError: unexpected token\nFound 1 error.\n"
        ),
    )


def test_python_ruff_e999_syntax_error_blocks(tmp_path: Path):
    """When ruff is on PATH and reports E999, the hook must block (exit 2).

    M2b bug: previously is_syntax_error was always False for ruff errors, so
    E999 (a genuine parse failure) was mis-classified as a soft lint issue and
    only soft-injected instead of blocked.
    """
    f = tmp_path / "broken.py"
    f.write_text("def foo(\n")
    mod = load_check()
    with (
        mock.patch("shutil.which", return_value="/usr/bin/ruff"),
        mock.patch("subprocess.run", return_value=_ruff_e999("broken.py")),
    ):
        rc, out, err = run_hook(mod, make_event(str(f)))
    assert rc == 2, "E999 via ruff must block (exit 2), not soft-inject"
    assert out.strip() == "", "stdout must be empty on exit 2"
    assert err.strip(), "block reason must appear on stderr"
    assert "broken.py" in err
