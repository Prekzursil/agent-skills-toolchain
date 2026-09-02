#!/usr/bin/env python3
"""Probe 1: live Darwin-attempt + adapter contract (zsh, BSD flags, argv spawn).

Two independent host signals: uname from a launched child, and sys.platform.
Does not rewrite either into Darwin.
"""
from __future__ import annotations

import json
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER_DIR = REPO / "release" / "platforms" / "macos"
sys.path.insert(0, str(ADAPTER_DIR))

import launch_adapter as A  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0014.json"
TEST_SH = ADAPTER_DIR / "tests" / "test_launch_adapter.sh"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0014-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0014" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != "IMP-0014":
        return fail(f"unit_id {doc.get('unit_id')}")

    signals = A.host_signals()
    if not signals["signals_agree"]:
        return fail(f"uname disagreement {signals}")
    if signals["darwin"] and signals["signal1_child_uname"] != "Darwin":
        return fail("darwin flag without Darwin uname")
    if (not signals["darwin"]) and signals["signal1_child_uname"] == "Darwin":
        return fail("non-darwin flag with Darwin uname — fabricated")
    if not signals["interpreter"] or not Path(signals["interpreter"]).is_file():
        return fail("interpreter path missing")
    if signals["default_shell"] != "zsh":
        return fail("default shell is not zsh")

    bsd = A.flagset("bsd")
    gnu = A.flagset("gnu")
    if bsd["sed_inplace"] != ["sed", "-i", ""]:
        return fail(f"bsd sed {bsd['sed_inplace']}")
    if gnu["sed_inplace"] != ["sed", "-i"]:
        return fail(f"gnu sed {gnu['sed_inplace']}")
    if not A.flags_differ():
        return fail("BSD and GNU flag sets are identical")
    auto = A.flagset()
    if signals["darwin"] and auto["sed_inplace"] != bsd["sed_inplace"]:
        return fail("Darwin host did not select BSD flags")
    if (not signals["darwin"]) and auto["sed_inplace"] != gnu["sed_inplace"]:
        return fail("non-Darwin host did not select GNU flags")

    adapter = A.MacOSLaunchAdapter(backend=A.SidecarXattrBackend())
    with tempfile.TemporaryDirectory(prefix="imp0014-p1-") as tmp:
        root = Path(tmp)
        payload = root / "child.py"
        payload.write_text(
            "import os, sys\n"
            "print('CHILD', os.uname().sysname, flush=True)\n"
            "print('ARGV', __import__('json').dumps(sys.argv[1:]), flush=True)\n",
            encoding="utf-8",
        )
        launched = adapter.launch(
            [sys.executable, str(payload), "alpha", "beta"],
            capture_uname=True,
        )
        if launched.returncode != 0:
            return fail(f"child launch rc={launched.returncode} {launched.stderr}")
        if f"CHILD {signals['signal1_child_uname']}" not in launched.stdout:
            return fail(f"child uname missing in stdout: {launched.stdout!r}")
        if launched.uname_inside != signals["signal1_child_uname"]:
            return fail("capture_uname disagrees with host signal1")

        fake_zsh = root / "zsh"
        fake_zsh.write_text(
            "#!/bin/sh\necho ZSH_LAUNCHER\nexec python3 \"$@\"\n",
            encoding="utf-8",
        )
        fake_zsh.chmod(fake_zsh.stat().st_mode | stat.S_IEXEC)
        script = root / "script.zsh"
        script.write_text(
            "#!/usr/bin/env python3\nprint('FROM_ZSH', flush=True)\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        zsh_adapter = A.MacOSLaunchAdapter(
            backend=A.SidecarXattrBackend(), zsh_path=str(fake_zsh)
        )
        if zsh_adapter.zsh() != fake_zsh:
            return fail("zsh() did not return configured zsh")
        zrun = zsh_adapter.launch_shell_script(script)
        if zrun.returncode != 0:
            return fail(f"zsh launch rc={zrun.returncode} {zrun.stderr}")
        if "ZSH_LAUNCHER" not in zrun.stdout or "FROM_ZSH" not in zrun.stdout:
            return fail(f"zsh launch stdout {zrun.stdout!r}")

        try:
            adapter.launch([])
            return fail("empty argv did not raise")
        except A.AdapterError as exc:
            if exc.code != A.EMPTY_ARGV:
                return fail(f"empty argv code {exc.code}")

        try:
            A.MacOSLaunchAdapter(
                backend=A.SidecarXattrBackend(), require_darwin=True
            ).launch([sys.executable, "-c", "pass"])
            if not signals["darwin"]:
                return fail("require_darwin did not raise on non-Darwin")
        except A.AdapterError as exc:
            if signals["darwin"]:
                return fail(f"require_darwin raised on Darwin: {exc}")
            if exc.code != A.MACOS_SUBSTRATE_MISSING:
                return fail(f"require_darwin code {exc.code}")

    if not TEST_SH.is_file():
        return fail("test_launch_adapter.sh missing")
    sh = subprocess.run(
        ["bash", str(TEST_SH)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if sh.returncode != 0:
        print((sh.stdout or "")[-1500:])
        print((sh.stderr or "")[-1500:])
        return fail(f"test_launch_adapter.sh rc={sh.returncode}")
    if "SUCCESS:macos-test_launch_adapter" not in (sh.stdout or ""):
        return fail("test script sentinel missing")

    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        return fail("receipt evidence < 2")
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-darwin-launch",
                "unit_id": "IMP-0014",
                "darwin": signals["darwin"],
                "child_uname": signals["signal1_child_uname"],
                "sys_platform": signals["signal2_sys_platform"],
                "interpreter": signals["interpreter"],
                "zsh_default": True,
                "bsd_gnu_flags_differ": True,
                "argv_child_ok": True,
                "test_script_ok": True,
                "fabricated_darwin": False,
            },
            sort_keys=True,
        )
    )
    print(
        f"child_uname={signals['signal1_child_uname']} "
        f"platform={signals['signal2_sys_platform']} "
        f"darwin={signals['darwin']} interpreter={signals['interpreter']}"
    )
    print("SUCCESS:IMP-0014-probe1 live launch contract and host signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
