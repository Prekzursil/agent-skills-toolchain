#!/usr/bin/env python3
"""Both-states standalone tests for the bounded ``hookrun`` launcher.

Run:  python test_hookrun.py

This is intentionally a standalone suite, matching ``test_completion.py``.  Each
case records its pre-change failure: with only this test overlaid on main,
``hookrun.py`` is absent, so every launcher behavior below is unavailable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
import time
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
HOOKS_ROOT = HERE.parent
HOOKRUN = HERE / "hookrun.py"


class PlatformInapplicable(unittest.SkipTest):
    """A case exercises semantics that do not exist on this platform.

    Subclasses unittest.SkipTest so BOTH runners agree. This file is a standalone script with its
    own __main__ runner, which catches this and reports SKIP — but the same file under pytest saw a
    raised exception and reported FAIL, so the identical platform gap read as green in one runner
    and red in the other. unittest.SkipTest is honoured natively by pytest as a skip and is still an
    ordinary Exception, so the standalone handler below is unchanged.
    """


def _load_hookrun() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hookrun_under_test", HOOKRUN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {HOOKRUN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _invoke(
    root: Path,
    hook: str,
    *hook_args: str,
    stdin: str = "",
    timeout: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(HOOKRUN), "--root", str(root)]
    if timeout is not None:
        command.extend(("--timeout", timeout))
    command.extend((hook, *hook_args))
    child_env = os.environ.copy()
    child_env.update(env or {})
    return subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        timeout=5,
        check=False,
    )


def test_exact_resolver_has_positive_control_and_contains_lookup() -> None:
    """Broken on main: no resolver exists, including for known-present completion.py."""
    hookrun = _load_hookrun()
    known = hookrun.resolve_hook(HOOKS_ROOT, "_shared/completion.py")
    assert known == (HERE / "completion.py").resolve()

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        root = base / "root"
        root.mkdir()
        _write(base / "outside.py", "raise SystemExit(0)\n")

        try:
            hookrun.resolve_hook(root, "missing.py")
        except hookrun.LaunchError as exc:
            assert exc.exit_code == hookrun.EXIT_NOT_FOUND
        else:
            raise AssertionError("missing exact path was accepted")

        try:
            hookrun.resolve_hook(root, "../outside.py")
        except hookrun.LaunchError as exc:
            assert exc.exit_code == hookrun.EXIT_CANNOT_EXECUTE
        else:
            raise AssertionError("path outside --root was accepted")


def test_interpreter_selection_is_explicit() -> None:
    """Broken on main: there is no suffix-to-interpreter launch policy."""
    hookrun = _load_hookrun()

    def fake_which(name: str) -> str:
        return f"/runtime/{name}"

    assert hookrun.build_command(Path("x.py"), ["a"], which=fake_which) == [
        sys.executable,
        "x.py",
        "a",
    ]
    assert hookrun.build_command(Path("x.mjs"), [], which=fake_which) == [
        "/runtime/node",
        "x.mjs",
    ]
    # `.sh` selects the bash RUNTIME with no extra prefix args — that is this test's subject.
    # WHICH bash is a separate policy with its own dedicated test below: on Windows find_bash
    # deliberately prefers Git Bash and rejects the WSL shim at /windows/system32/bash.exe,
    # because that shim mangles Windows paths and rejects CRLF. Hard-coding "/runtime/bash" here
    # asserted the suffix policy AND the platform policy at once, so it passed only on non-Windows.
    assert hookrun.build_command(Path("x.sh"), [], which=fake_which) == [
        hookrun.find_bash(which=fake_which),
        "x.sh",
    ]
    assert hookrun.build_command(Path("x.ps1"), ["a"], which=fake_which) == [
        "/runtime/pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "x.ps1",
        "a",
    ]
    first_git_bash = hookrun._WINDOWS_GIT_BASH[0]
    selected = hookrun.find_bash(
        platform="win32",
        is_file=lambda path: path == first_git_bash,
        which=lambda _name: "C:/Windows/System32/bash.exe",
    )
    assert selected == str(first_git_bash)
    rejected = hookrun.find_bash(
        platform="win32",
        is_file=lambda _path: False,
        which=lambda _name: r"C:\Windows\System32\bash.exe",
    )
    assert rejected is None
    assert hookrun._shell_status(-15) == 143
    assert hookrun._parser().parse_args(["x.py"]).timeout == 30.0


def test_python_hook_preserves_process_context_and_streams() -> None:
    """Broken on main: a non-executable Python hook cannot run through hookrun."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "røøt with spaces"
        hook = _write(
            root / "écho.py",
            """import json
import os
import sys

print(json.dumps({
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "env": os.environ.get("HOOKRUN_TEST_VALUE"),
    "stdin": sys.stdin.read(),
}))
print("fixture-stderr", file=sys.stderr)
""",
        )
        hook.chmod(0o600)
        payload = '{"hook": "input"}\n'
        result = _invoke(
            root,
            hook.name,
            "two words",
            "$HOME",
            "a;b",
            stdin=payload,
            env={"HOOKRUN_TEST_VALUE": "inherited"},
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == "fixture-stderr\n"
        assert json.loads(result.stdout) == {
            "argv": ["two words", "$HOME", "a;b"],
            "cwd": os.getcwd(),
            "env": "inherited",
            "stdin": payload,
        }


def test_silent_success_stays_silent_and_successful() -> None:
    """Broken on main: no shim preserves an artifactless hook's silent exit 0."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "silent.py", "raise SystemExit(0)\n")
        result = _invoke(root, "silent.py", stdin="ignored")
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_native_exit_124_is_not_reported_as_a_timeout() -> None:
    """Broken on main: no shim distinguishes child exit 124 from its own deadline."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "native-124.py", "raise SystemExit(124)\n")
        result = _invoke(root, "native-124.py")
        assert (result.returncode, result.stdout, result.stderr) == (124, "", "")


def test_blocking_exit_and_stderr_are_preserved() -> None:
    """Broken on main: there is no shim preserving unique exit-2 block evidence."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root / "block.py",
            "import sys\nprint('unique block reason', file=sys.stderr)\nraise SystemExit(2)\n",
        )
        result = _invoke(root, "block.py")
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr == "unique block reason\n"


def test_non_executable_shell_hook_uses_bash() -> None:
    """Broken on main: a bare non-executable .sh has no interpreter-explicit shim."""
    hookrun = _load_hookrun()
    if hookrun.find_bash() is None:
        raise RuntimeError("required Bash interpreter is unavailable")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "shell root"
        hook = _write(
            root / "echo.sh",
            """#!/usr/bin/env bash
payload=$(cat)
printf 'shell:%s' "$payload"
printf 'shell-error' >&2
exit 23
""",
        )
        hook.chmod(0o600)
        result = _invoke(root, hook.name, stdin="payload")
        assert (result.returncode, result.stdout, result.stderr) == (
            23,
            "shell:payload",
            "shell-error",
        )


def test_timeout_is_bounded_and_kills_descendants() -> None:
    """Broken on main: no internal deadline replaces an unbounded hook launch."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ready = root / "ready"
        marker = root / "orphan-ran"
        _write(
            root / "hang.py",
            """import pathlib
import subprocess
import sys
import time

descendant = "import pathlib,sys,time;time.sleep(0.8);pathlib.Path(sys.argv[1]).write_text('ran')"
subprocess.Popen([sys.executable, "-c", descendant, sys.argv[2]])
pathlib.Path(sys.argv[1]).write_text("ready")
time.sleep(10)
""",
        )
        started = time.monotonic()
        result = _invoke(root, "hang.py", str(ready), str(marker), timeout="0.5")
        elapsed = time.monotonic() - started
        assert result.returncode == 124
        assert result.stdout == ""
        assert "hookrun: timed out after 0.5s: hang.py" in result.stderr
        assert elapsed < 2.0
        assert ready.exists(), "hook never spawned the descendant before timeout"
        time.sleep(1.0)
        assert not marker.exists(), (
            "timed-out descendant survived the process-tree kill"
        )


def test_posix_termination_is_forwarded_to_the_child_group() -> None:
    """Broken on main: there is no shim to forward a host termination signal."""
    if os.name == "nt":
        raise PlatformInapplicable("POSIX signal semantics do not exist on Windows")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ready = root / "ready"
        marker = root / "orphan-ran"
        _write(
            root / "wait.py",
            """import pathlib
import subprocess
import sys
import time

descendant = "import pathlib,sys,time;time.sleep(0.8);pathlib.Path(sys.argv[1]).write_text('ran')"
subprocess.Popen([sys.executable, "-c", descendant, sys.argv[2]])
pathlib.Path(sys.argv[1]).write_text("ready")
time.sleep(10)
""",
        )
        process = subprocess.Popen(
            [
                sys.executable,
                str(HOOKRUN),
                "--root",
                str(root),
                "wait.py",
                str(ready),
                str(marker),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            deadline = time.monotonic() + 2
            while not ready.exists() and process.poll() is None:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.02)
            assert ready.exists(), "hook did not reach the signal-ready state"
            process.terminate()
            stdout, stderr = process.communicate(timeout=3)
            assert process.returncode == 143
            assert stdout == ""
            assert stderr == ""
            time.sleep(1.0)
            assert not marker.exists(), (
                "terminated descendant survived signal forwarding"
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def test_cleanup_failure_paths_are_bounded_and_target_the_tree() -> None:
    """Broken on main: no shim bounds retries or cleans up an exited leader's group."""
    hookrun = _load_hookrun()

    class NeverReaps:
        def __init__(self) -> None:
            self.kill_calls = 0
            self.wait_timeouts: list[float] = []

        def wait(self, timeout: float) -> int:
            self.wait_timeouts.append(timeout)
            raise subprocess.TimeoutExpired("never-reaps", timeout)

        def kill(self) -> None:
            self.kill_calls += 1

    process = NeverReaps()
    assert hookrun._reap_after_kill(process) is False
    assert process.wait_timeouts == [5, 1]
    assert process.kill_calls == 1

    if os.name != "nt":

        class ExitedLeader:
            pid = 43210

            def wait(self, timeout: float) -> int:
                assert timeout == 5
                return 0

            def kill(self) -> None:
                raise AssertionError(
                    "group cleanup unexpectedly fell back to leader kill"
                )

        killpg_calls: list[tuple[int, int]] = []
        original_killpg = hookrun.os.killpg
        hookrun.os.killpg = lambda pid, signum: killpg_calls.append((pid, signum))
        try:
            assert hookrun._kill_process_tree(ExitedLeader()) is True
        finally:
            hookrun.os.killpg = original_killpg
        assert killpg_calls == [(ExitedLeader.pid, signal.SIGKILL)]

    class FailedTaskkill:
        pid = 54321

        def __init__(self) -> None:
            self.kill_calls = 0

        def wait(self, timeout: float) -> int:
            assert timeout == 5
            return 0

        def kill(self) -> None:
            self.kill_calls += 1

    taskkill_process = FailedTaskkill()
    original_name = hookrun.os.name
    original_run = hookrun.subprocess.run
    hookrun.os.name = "nt"
    hookrun.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 1
    )
    try:
        assert hookrun._kill_process_tree(taskkill_process) is False
    finally:
        hookrun.subprocess.run = original_run
        hookrun.os.name = original_name
    assert taskkill_process.kill_calls == 1

    if os.name != "nt":
        killpg_failure_process = FailedTaskkill()
        original_killpg = hookrun.os.killpg

        def fail_killpg(_pid: int, _signum: int) -> None:
            raise ProcessLookupError

        hookrun.os.killpg = fail_killpg
        try:
            assert hookrun._kill_process_tree(killpg_failure_process) is False
        finally:
            hookrun.os.killpg = original_killpg
        assert killpg_failure_process.kill_calls == 1


def test_launcher_errors_are_deterministic_and_stay_off_stdout() -> None:
    """Broken on main: missing/unsupported/runtime errors have no launcher contract."""
    hookrun = _load_hookrun()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        missing = _invoke(root, "missing.py")
        assert missing.returncode == 127
        assert missing.stdout == ""
        assert "hookrun: hook not found: missing.py" in missing.stderr

        _write(root / "hook.txt", "not executable\n")
        unsupported = _invoke(root, "hook.txt")
        assert unsupported.returncode == 126
        assert unsupported.stdout == ""
        assert "hookrun: unsupported hook type .txt" in unsupported.stderr

        try:
            hookrun.build_command(Path("hook.js"), [], which=lambda _name: None)
        except hookrun.LaunchError as exc:
            assert exc.exit_code == 127
        else:
            raise AssertionError("missing interpreter was accepted")

        invalid_timeout = subprocess.run(
            [
                sys.executable,
                str(HOOKRUN),
                "--root",
                str(root),
                "--timeout",
                "0",
                "missing.py",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        assert invalid_timeout.returncode == 2
        assert invalid_timeout.stdout == ""
        assert "finite number greater than zero" in invalid_timeout.stderr


CASES = (
    (
        "exact resolver: positive control + bounded containment",
        test_exact_resolver_has_positive_control_and_contains_lookup,
        "hookrun.py is absent, so even known-present completion.py cannot resolve",
    ),
    (
        "explicit interpreter selection",
        test_interpreter_selection_is_explicit,
        "hookrun.py is absent, so no suffix policy exists",
    ),
    (
        "Python argv/stdin/env/cwd/stdout/stderr passthrough",
        test_python_hook_preserves_process_context_and_streams,
        "the absent launcher cannot execute the non-executable fixture",
    ),
    (
        "silent exit 0 passthrough",
        test_silent_success_stays_silent_and_successful,
        "the absent launcher exits nonzero instead of preserving silent success",
    ),
    (
        "native exit 124 is not a launcher timeout",
        test_native_exit_124_is_not_reported_as_a_timeout,
        "the absent launcher cannot preserve the child status without a false diagnostic",
    ),
    (
        "exit 2 + stderr passthrough",
        test_blocking_exit_and_stderr_are_preserved,
        "the absent launcher cannot emit the fixture's unique block reason",
    ),
    (
        "non-executable shell hook via Bash",
        test_non_executable_shell_hook_uses_bash,
        "the absent launcher cannot supply Bash explicitly",
    ),
    (
        "bounded timeout + descendant cleanup",
        test_timeout_is_bounded_and_kills_descendants,
        "the absent launcher provides neither an internal deadline nor cleanup",
    ),
    (
        "POSIX termination forwarding",
        test_posix_termination_is_forwarded_to_the_child_group,
        "the absent launcher cannot forward host termination to a child group",
    ),
    (
        "bounded cleanup failure paths",
        test_cleanup_failure_paths_are_bounded_and_target_the_tree,
        "the absent launcher has no bounded process-tree cleanup path",
    ),
    (
        "deterministic launcher errors",
        test_launcher_errors_are_deterministic_and_stay_off_stdout,
        "the absent launcher has no path/runtime/error contract",
    ),
)


def main() -> int:
    failures = 0
    skipped = 0
    for label, test, known_broken in CASES:
        try:
            test()
        except PlatformInapplicable as exc:
            skipped += 1
            print(f"  -- SKIP {label}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"  XX {label}: {type(exc).__name__}: {exc}")
            print(f"     known-broken main: {known_broken}")
        else:
            print(f"  OK {label}")
    outcome = "ALL PASS" if not failures else f"{failures} FAIL"
    print(f"\nRESULT: {outcome} ({len(CASES)} cases, {skipped} skipped)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
