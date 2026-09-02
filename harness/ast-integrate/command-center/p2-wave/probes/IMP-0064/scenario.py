"""Shared live scenario for IMP-0064 probes (independent of pytest)."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[4] / "tools" / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from exec_policy import (  # noqa: E402
    DENY_EXIT,
    WINDOWS_LIMITATION,
    CountingListener,
    build_policy,
    existing_executable,
    oob_canary_pids,
    oob_path_exists,
    run_script,
    write_canary,
    write_script,
)

SPAWN_DENIED = """
import os, subprocess
subprocess.Popen([os.environ["IMP0064_CANARY"]])
print("UNREACHABLE_SPAWN")
"""

WRITE_DENIED = """
import os
from pathlib import Path
Path(os.environ["IMP0064_FORBIDDEN_FILE"]).write_text("leaked\\n", encoding="utf-8")
print("UNREACHABLE_WRITE")
"""

NET_DENIED = """
import os, socket
socket.create_connection(
    (os.environ["IMP0064_DENY_HOST"], int(os.environ["IMP0064_DENY_PORT"])),
    timeout=2,
)
print("UNREACHABLE_NET")
"""

ALLOWED = """
import os, socket, subprocess
from pathlib import Path
echo = os.environ["IMP0064_ECHO"]
out = subprocess.run([echo, "IMP0064-ALLOWED-SPAWN"], capture_output=True, text=True, check=True)
Path(os.environ["IMP0064_ALLOWED_FILE"]).write_text("ok\\n", encoding="utf-8")
s = socket.create_connection(
    (os.environ["IMP0064_ALLOW_HOST"], int(os.environ["IMP0064_ALLOW_PORT"])),
    timeout=2,
)
s.close()
print(out.stdout.strip())
print("ALLOWED_OK")
"""

SYMLINK = """
import os
from pathlib import Path
Path(os.environ["IMP0064_LINK"]).write_text("escaped\\n", encoding="utf-8")
print("UNREACHABLE_SYMLINK")
"""


class Scenario:
    def __init__(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="imp0064-probe-")
        self.root = Path(self._td.name)
        self.allowed = self.root / "allowed"
        self.forbidden = self.root / "forbidden"
        self.allowed.mkdir()
        self.forbidden.mkdir()
        self.echo = existing_executable("/bin/echo", "/usr/bin/echo", "echo")
        self.canary, self.marker = write_canary(self.root / "canary")
        self.allow_file = self.allowed / "out.txt"
        self.forbid_file = self.forbidden / "leak.txt"
        self.symlink_target = self.forbidden / "via-link.txt"
        self.link = self.allowed / "link-out.txt"
        os.symlink(self.symlink_target, self.link)
        self.allow_l = CountingListener()
        self.deny_l = CountingListener()
        self.allow_l.start()
        self.deny_l.start()
        time.sleep(0.05)
        self.policy = build_policy(
            policy_id="IMP-0064-live",
            allowed_executables=[self.echo],
            allowed_write_roots=[str(self.allowed)],
            network_mode="allowlist",
            endpoints=[self.allow_l.endpoint],
        )
        self.env = {
            "IMP0064_CANARY": str(self.canary),
            "IMP0064_CANARY_MARKER": str(self.marker),
            "IMP0064_ECHO": self.echo,
            "IMP0064_ALLOWED_FILE": str(self.allow_file),
            "IMP0064_FORBIDDEN_FILE": str(self.forbid_file),
            "IMP0064_ALLOW_HOST": self.allow_l.host,
            "IMP0064_ALLOW_PORT": str(self.allow_l.port),
            "IMP0064_DENY_HOST": self.deny_l.host,
            "IMP0064_DENY_PORT": str(self.deny_l.port),
            "IMP0064_LINK": str(self.link),
        }
        self.allowed_script = write_script(self.root / "allowed_all.py", ALLOWED)
        self.spawn_script = write_script(self.root / "deny_spawn.py", SPAWN_DENIED)
        self.write_script_p = write_script(self.root / "deny_write.py", WRITE_DENIED)
        self.net_script = write_script(self.root / "deny_net.py", NET_DENIED)
        self.symlink_script = write_script(self.root / "deny_symlink.py", SYMLINK)

    def close(self) -> None:
        self.allow_l.stop()
        self.deny_l.stop()
        self._td.cleanup()

    def run_allowed(self):
        return run_script(self.policy, self.allowed_script, extra_env=self.env)

    def run_spawn(self):
        return run_script(self.policy, self.spawn_script, extra_env=self.env)

    def run_write(self):
        return run_script(self.policy, self.write_script_p, extra_env=self.env)

    def run_net(self):
        return run_script(self.policy, self.net_script, extra_env=self.env)

    def run_symlink(self):
        return run_script(self.policy, self.symlink_script, extra_env=self.env)
