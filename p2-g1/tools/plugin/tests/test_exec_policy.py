#!/usr/bin/env python3
"""Four live controls for exec_policy userspace intercept."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
from exec_policy import (  # noqa: E402
    DENY_EXIT,
    CountingListener,
    build_policy,
    existing_executable,
    run_script,
    write_script,
)


def main() -> int:
    echo = existing_executable("/bin/echo", "/usr/bin/echo", "echo")
    with tempfile.TemporaryDirectory(prefix="imp0064-test-") as raw:
        root = Path(raw)
        allowed = root / "ok"
        forbidden = root / "no"
        allowed.mkdir()
        forbidden.mkdir()
        allow_l = CountingListener()
        deny_l = CountingListener()
        allow_l.start()
        deny_l.start()
        policy = build_policy(
            "t",
            [echo],
            [str(allowed)],
            network_mode="allowlist",
            endpoints=[allow_l.endpoint],
        )
        try:
            ok = write_script(
                root / "ok.py",
                "print('ALLOWED_OK')\n",
            )
            spawn = write_script(
                root / "spawn.py",
                "import os, subprocess\n"
                "subprocess.Popen(['/bin/definitely-not-allowed-imp0064'])\n"
                "print('UNREACHABLE_SPAWN')\n",
            )
            write = write_script(
                root / "write.py",
                "from pathlib import Path\n"
                f"Path(r'{forbidden / 'leak.txt'}').write_text('x')\n"
                "print('UNREACHABLE_WRITE')\n",
            )
            net = write_script(
                root / "net.py",
                "import socket\n"
                f"socket.create_connection(('127.0.0.1', {deny_l.port}), timeout=1)\n"
                "print('UNREACHABLE_NET')\n",
            )
            r_ok = run_script(policy, ok)
            r_sp = run_script(policy, spawn)
            r_wr = run_script(policy, write)
            r_nt = run_script(policy, net)
        finally:
            allow_l.stop()
            deny_l.stop()
    assert r_ok.exit_code == 0 and "ALLOWED_OK" in r_ok.stdout
    assert r_sp.refused and r_sp.exit_code == DENY_EXIT and "FORBIDDEN_SPAWN" in r_sp.codes()
    assert r_wr.refused and r_wr.exit_code == DENY_EXIT and "FORBIDDEN_WRITE" in r_wr.codes()
    assert r_nt.refused and r_nt.exit_code == DENY_EXIT and "FORBIDDEN_NETWORK" in r_nt.codes()
    print("SUCCESS:test_exec_policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
