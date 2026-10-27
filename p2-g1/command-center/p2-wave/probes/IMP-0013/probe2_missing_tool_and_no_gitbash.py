#!/usr/bin/env python3
"""IMP-0013 probe 2: missing-tool named error + no Git-Bash launch path.

Mechanically different from probe 1 (source region scan + negative control +
the catalog test module), not a re-run of the .cmd shim launch.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER_DIR = REPO / "release" / "platforms" / "windows"
sys.path.insert(0, str(ADAPTER_DIR))

from launch_adapter import LaunchAdapterError, launch  # noqa: E402

PY = ADAPTER_DIR / "launch_adapter.py"
PS1 = ADAPTER_DIR / "Launch-Adapter.ps1"
TEST_PY = ADAPTER_DIR / "tests" / "test_launch_adapter.py"
TEST_PS1 = ADAPTER_DIR / "tests" / "test_launch_adapter.ps1"

FORBIDDEN_LAUNCH = (
    "bash.exe",
    "git-bash",
    "Git/bin/bash",
    "Git\\bin\\bash",
    "posix_which(",
    "posix_command_v_live(",
    "shell=True",
    "command -v",
    "which.exe",
    "UseShellExecute = $true",
    "UseShellExecute=$true",
)


def launch_region(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"# LAUNCH-PATH-BEGIN.*?# LAUNCH-PATH-END", text, re.S)
    if not m:
        raise AssertionError(f"launch-path markers missing in {path}")
    return m.group(0)


def main() -> int:
    for p in (PY, PS1, TEST_PY, TEST_PS1):
        if not p.is_file() or p.stat().st_size < 100:
            print(f"FAILED:IMP-0013-probe2 missing {p.relative_to(REPO)}")
            return 1

    # Negative control: missing tool is a named error, not a stack dump.
    with tempfile.TemporaryDirectory(prefix="imp0013-p2-") as tmp:
        try:
            launch("nosuch-imp0013-tool", path_dirs=[tmp])
            print("FAILED:IMP-0013-probe2 missing tool did not raise")
            return 1
        except LaunchAdapterError as err:
            text = err.to_user_text()
            fired_on_bad = err.code == "TOOL_NOT_FOUND" and text.startswith(
                "ERROR:TOOL_NOT_FOUND"
            )
            stack_in_user = "Traceback" in text or 'File "' in text
            actionable = "PATH" in text and "action:" in text
            if not fired_on_bad or stack_in_user or not actionable:
                print("FAILED:IMP-0013-probe2 negative control")
                print(f"  code={err.code} stack_in_user={stack_in_user}")
                print(text)
                return 1
            # Control: traceback exists in the except frame, but must not be
            # the user-facing string.
            _ = traceback.format_exc()
        else:  # pragma: no cover
            print("FAILED:IMP-0013-probe2 unreachable")
            return 1

        # Silent on good: an existing PATHEXT-less executable launches.
        good = Path(tmp) / "present-tool"
        good.write_text(
            "#!/usr/bin/env python3\nprint('IMP-0013-PRESENT')\n", encoding="utf-8"
        )
        good.chmod(good.stat().st_mode | 0o111)
        try:
            _res, proc = launch("present-tool", path_dirs=[tmp])
        except LaunchAdapterError as err:
            print("FAILED:IMP-0013-probe2 good-state raised", err.to_user_text())
            return 1
        silent_on_good = proc.returncode == 0 and "IMP-0013-PRESENT" in proc.stdout
        if not silent_on_good:
            print(f"FAILED:IMP-0013-probe2 good-state rc={proc.returncode}")
            return 1

    py_region = launch_region(PY)
    ps_region = launch_region(PS1)
    hits = []
    for label, region in (("python", py_region), ("pwsh", ps_region)):
        for tok in FORBIDDEN_LAUNCH:
            if tok in region:
                hits.append(f"{label}:{tok}")
    if hits:
        print("FAILED:IMP-0013-probe2 Git-Bash/shell tokens in launch path", hits)
        return 1
    if "shell=False" not in py_region:
        print("FAILED:IMP-0013-probe2 python spawn does not pin shell=False")
        return 1
    if "UseShellExecute = $false" not in ps_region:
        print("FAILED:IMP-0013-probe2 pwsh spawn does not pin UseShellExecute=false")
        return 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    test = subprocess.run(
        [sys.executable, "-B", str(TEST_PY)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    combined = (test.stdout or "") + (test.stderr or "")
    if test.returncode != 0 or "SUCCESS:IMP-0013-test_launch_adapter" not in combined:
        print("FAILED:IMP-0013-probe2 test_launch_adapter.py")
        print(combined[-4000:])
        return 1

    print(
        "fired_on_bad=True silent_on_good=True gitbash_launch_hits=0 "
        f"test_py_rc={test.returncode}"
    )
    print("SUCCESS:IMP-0013-probe2 missing-tool named error and no Git-Bash launch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
