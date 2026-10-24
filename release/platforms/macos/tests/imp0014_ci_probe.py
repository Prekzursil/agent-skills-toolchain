#!/usr/bin/env python3
"""IMP-0014 CI probe - runs ON a macOS runner, emits two-signal Darwin evidence.

Signal 1: `uname -s` reported by a process the ADAPTER launched (argv spawn,
          capture_uname on). The adapter, not the probe, gathers the sysname.
Signal 2: sys.platform + platform.system() reported by the interpreter the
          adapter resolved (sys.executable of this process), plus the adapter's
          resolved zsh path.

Also executes the real-quarantine round-trip (xattr -w set, xattr -p present,
delete via the adapter's BSD flagset argv, xattr -p absent) and the adapter's
own contract test script. One EVIDENCE: JSON line, then a terminal marker.

Honesty contract: this script must never rewrite a non-Darwin report into
Darwin. If the host is not Darwin it FAILS with the measured values.
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTER_DIR = HERE.parent
sys.path.insert(0, str(ADAPTER_DIR))
import launch_adapter as A  # noqa: E402


def main() -> int:
    sig = A.host_signals()
    adapter = A.MacOSLaunchAdapter(backend=A.SidecarXattrBackend())

    launched = adapter.launch(["/bin/sh", "-c", "uname -s"], capture_uname=True)
    child_uname = (launched.stdout or "").strip()

    interpreter = sys.executable
    plat = {"sys_platform": sys.platform, "platform_system": platform.system()}

    with tempfile.TemporaryDirectory(prefix="imp0014-xattr-") as tmp:
        f = Path(tmp) / "downloaded.bin"
        f.write_bytes(b"imp0014")
        xw = subprocess.run(
            ["xattr", "-w", A.QUARANTINE_ATTR, "0083;imp0014;ci", str(f)],
            capture_output=True, text=True,
        )
        has = subprocess.run(
            ["xattr", "-p", A.QUARANTINE_ATTR, str(f)],
            capture_output=True, text=True,
        )
        del_argv = A.flagset()["xattr_delete"] + [str(f)]
        xd = subprocess.run(del_argv, capture_output=True, text=True)
        gone = subprocess.run(
            ["xattr", "-p", A.QUARANTINE_ATTR, str(f)],
            capture_output=True, text=True,
        )
        xattr_roundtrip = bool(
            xw.returncode == 0
            and has.returncode == 0
            and xd.returncode == 0
            and gone.returncode != 0
        )

    sh = subprocess.run(
        ["bash", str(ADAPTER_DIR / "tests" / "test_launch_adapter.sh")],
        capture_output=True, text=True, cwd=str(ADAPTER_DIR),
    )
    test_sentinel = "SUCCESS:macos-test_launch_adapter" in (sh.stdout or "")

    evidence = {
        "host_signals": sig,
        "signal1_adapter_launched_uname": child_uname,
        "signal1_capture_uname": launched.uname_inside,
        "signal1_launch_rc": launched.returncode,
        "signal2": plat,
        "interpreter": interpreter,
        "zsh_resolved": str(adapter.zsh()),
        "xattr_roundtrip": xattr_roundtrip,
        "xattr_delete_argv": del_argv,
        "test_script_rc": sh.returncode,
        "test_script_sentinel": test_sentinel,
        "test_script_tail": (sh.stdout or "").strip().splitlines()[-3:],
    }
    print("EVIDENCE:" + json.dumps(evidence, sort_keys=True))
    ok = bool(
        child_uname == "Darwin"
        and launched.returncode == 0
        and launched.uname_inside == "Darwin"
        and plat["platform_system"] == "Darwin"
        and plat["sys_platform"] == "darwin"
        and sig["darwin"] is True
        and sig["signals_agree"] is True
        and xattr_roundtrip
        and sh.returncode == 0
        and test_sentinel
    )
    print("SUCCESS:IMP-0014-ci-darwin" if ok else "FAILED:IMP-0014-ci-darwin")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
