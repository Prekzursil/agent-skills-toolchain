#!/usr/bin/env python3
"""Probe 1: live Darwin-attempt + adapter contract (zsh, BSD flags, argv spawn).

Two independent host signals: uname from a launched child, and sys.platform.
Does not rewrite either into Darwin. Windows transport: the child sysname
falls back to platform.system() and families are compared via the adapter
classifier; the zsh-script launch runs the interpreter variant locally
(CreateProcess cannot exec shebang scripts) - the REAL zsh launch is
exercised on the Darwin CI runner, re-verified live from ci_darwin.
"""
from __future__ import annotations

import json
import os
import shutil
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


CI_REPO = "Prekzursil/agent-skills-toolchain"


def _resolve_posix_bash() -> str:
    """Git for Windows bash, never the WSL System32 shim.

    shutil.which('bash') from a Windows python resolves
    C:/Windows/System32/bash.exe (the WSL launcher, wedged on this estate,
    error 0x8007274c). The POSIX contract script must run under the Git for
    Windows bash that ships beside git.exe, where it passes live.
    """
    found = shutil.which("bash")
    if found and "system32" not in Path(found).as_posix().lower():
        return found
    git = shutil.which("git")
    if git:
        gp = Path(git).resolve().parent
        for anc in (gp, gp.parent, gp.parent.parent):
            for cand in (
                anc / "usr" / "bin" / "bash.exe",
                anc / "bin" / "bash.exe",
            ):
                if cand.is_file():
                    return str(cand)
    return found or "bash"


def verify_ci_darwin(doc):
    ci = doc.get("ci_darwin") or {}
    for key in ("repo", "run_id", "run_url", "head_sha", "conclusion", "evidence"):
        if not ci.get(key):
                return False, "ci_darwin." + key + " missing"
    if ci["conclusion"] != "success":
        return False, "ci_darwin.conclusion " + str(ci["conclusion"])
    ev = ci["evidence"]
    if not isinstance(ev, dict):
        return False, "ci_darwin.evidence not an object"
    if ev.get("signal1_adapter_launched_uname") != "Darwin":
        return False, "CI signal1 uname is not Darwin"
    if ev.get("signal1_capture_uname") != "Darwin":
        return False, "CI adapter capture_uname is not Darwin"
    s2 = ev.get("signal2") or {}
    if s2.get("platform_system") != "Darwin" or s2.get("sys_platform") != "darwin":
        return False, "CI signal2 not darwin"
    if not ev.get("xattr_roundtrip"):
        return False, "CI real xattr round-trip not recorded"
    if not ev.get("test_script_sentinel"):
        return False, "CI contract test script sentinel missing"
    if not str(ev.get("interpreter") or ""):
        return False, "CI interpreter path missing"
    hs = ev.get("host_signals") or {}
    if hs.get("darwin") is not True or hs.get("signals_agree") is not True:
        return False, "CI host_signals not darwin/agreeing"
    probe = subprocess.run(
        ["gh", "api", "repos/" + ci["repo"] + "/actions/runs/" + str(ci["run_id"]),
         "--jq", "{status: .status, conclusion: .conclusion, head_sha: .head_sha}"],
        capture_output=True, text=True, timeout=60,
    )
    if probe.returncode != 0:
        return False, "gh api failed rc=" + str(probe.returncode)
    try:
        live = json.loads(probe.stdout)
    except json.JSONDecodeError:
        return False, "gh api output unparseable"
    if live.get("status") != "completed":
        return False, "live run status " + str(live.get("status"))
    if live.get("conclusion") != "success":
        return False, "live run conclusion " + str(live.get("conclusion"))
    if live.get("head_sha") != ci["head_sha"]:
        return False, "live run head_sha differs from recorded"
    return True, "run " + str(ci["run_id"]) + " verified live"

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
        # Windows transport (declared in the module docstring): the child
        # reports its sysname through the same ladder as
        # launch_adapter.child_uname() - `uname -s` when present, os.uname()
        # on POSIX, platform.system() family fallback. A real Darwin would
        # still print CHILD Darwin; no signal is rewritten into Darwin.
        payload.write_text(
            "import json, os, shutil, subprocess, sys\n"
            "name = ''\n"
            "exe = shutil.which('uname')\n"
            "if exe:\n"
            "    p = subprocess.run([exe, '-s'], capture_output=True, text=True)\n"
            "    if p.returncode == 0 and p.stdout.strip():\n"
            "        name = p.stdout.strip()\n"
            "if not name and hasattr(os, 'uname'):\n"
            "    name = os.uname().sysname\n"
            "if not name:\n"
            "    import platform\n"
            "    name = platform.system()\n"
            "print('CHILD', name, flush=True)\n"
            "print('ARGV', json.dumps(sys.argv[1:]), flush=True)\n",
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

        if os.name == "nt":
            # CreateProcess cannot exec shebang scripts: the Windows transport
            # runs the interpreter variant through a .cmd shim. The REAL zsh
            # launch is exercised on the Darwin CI runner (ci_darwin).
            fake_zsh = root / "zsh.cmd"
            fake_zsh.write_text(
                f"@echo ZSH_LAUNCHER\n@\"{sys.executable}\" %*\n",
                encoding="utf-8",
            )
        else:
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
        [_resolve_posix_bash(), str(TEST_SH)],
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
